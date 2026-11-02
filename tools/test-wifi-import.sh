#!/bin/bash
# Tests rg35xxh-wifi-import with a fake nmcli (no network changes). Uses work/test-wifi/.
set -euo pipefail
source "$(dirname "$(realpath "$0")")/../build/config.sh"
T="$WORK/test-wifi"; [ -e "$T" ] && safe_rm -r "$T"; mkdir -p "$T"
cat > "$T/nmcli" <<'N'
#!/bin/sh
# Fake nmcli: logs each call, keeps connection names in "cons" (one per line).
# FAIL_ADD=1: "connection add" fails, like NetworkManager refusing a short password.
d="$(dirname "$0")"; echo "nmcli $*" >> "$d/calls.log"; touch "$d/cons"
case "$*" in
  "-t -f NAME connection show") cat "$d/cons" ;;
  "connection add "*)
    [ -n "${FAIL_ADD:-}" ] && exit 4
    while [ $# -gt 0 ]; do [ "$1" = con-name ] && { echo "$2" >> "$d/cons"; break; }; shift; done ;;
  "connection delete id "*) grep -vFx "$4" "$d/cons" > "$d/cons.new"; mv "$d/cons.new" "$d/cons" ;;
  "connection modify id "*) grep -Fxq "$4" "$d/cons" || exit 10
    { grep -vFx "$4" "$d/cons"; echo "$6"; } > "$d/cons.new"; mv "$d/cons.new" "$d/cons" ;;
esac
exit 0
N
chmod +x "$T/nmcli"
S="$TOP/overlay/usr/local/sbin/rg35xxh-wifi-import"
fail=0
check() { if eval "$2"; then echo "ok    $1"; else echo "FAIL  $1"; fail=1; fi; }

# 1. Windows file (BOM + CRLF), password with spaces and '='
printf '\xEF\xBB\xBF# comment\r\nSSID=My Home 5G\r\nPASSWORD= p@ss w=rd \r\nCOUNTRY=DE\r\n' > "$T/wifi.txt"
WIFI_FILE="$T/wifi.txt" NMCLI="$T/nmcli" IW=true bash "$S" > "$T/out1.txt"
check "adds WPA connection" "grep -q 'connection add type wifi con-name wifi-My Home 5G (importing) ssid My Home 5G wifi-sec.key-mgmt wpa-psk wifi-sec.psk p@ss w=rd connection.autoconnect yes' '$T/calls.log'"
check "password blanked" "grep -qx 'PASSWORD=' '$T/wifi.txt'"
check "secret gone from file" "! grep -q 'p@ss' '$T/wifi.txt'"
check "SSID kept" "grep -qx 'SSID=My Home 5G' '$T/wifi.txt'"
check "marked imported" "grep -q '^# imported ' '$T/wifi.txt'"
check "CR/BOM removed" "! grep -q \$'\\r' '$T/wifi.txt' && ! head -c3 '$T/wifi.txt' | grep -q \$'\\xEF'"

# 2. Second boot: nothing re-imported
: > "$T/calls.log"
WIFI_FILE="$T/wifi.txt" NMCLI="$T/nmcli" IW=true bash "$S" > "$T/out2.txt"
check "no re-import on next boot" "! grep -q 'connection add' '$T/calls.log'"

# 3. Existing connection replaced, only after the new one was added; open network
printf 'SSID=OldNet\nPASSWORD=\n' > "$T/wifi2.txt"
: > "$T/calls.log"; echo wifi-OldNet > "$T/cons"
WIFI_FILE="$T/wifi2.txt" NMCLI="$T/nmcli" IW=true bash "$S" > "$T/out3.txt"
check "open network without psk" "grep -q 'connection add type wifi con-name wifi-OldNet (importing) ssid OldNet connection.autoconnect yes' '$T/calls.log' && ! grep -q psk '$T/calls.log'"
check "old connection deleted after the add" "[ \"\$(grep -n 'connection add' '$T/calls.log' | cut -d: -f1)\" -lt \"\$(grep -n 'connection delete id wifi-OldNet\$' '$T/calls.log' | cut -d: -f1)\" ]"
check "new connection renamed" "[ \"\$(cat '$T/cons')\" = wifi-OldNet ] && grep -q 'connection modify id wifi-OldNet (importing) connection.id wifi-OldNet' '$T/calls.log'"

# 3b. NetworkManager refuses the new settings: the old connection stays, the password stays
printf 'SSID=OldNet\nPASSWORD=short\n' > "$T/wifi2b.txt"
: > "$T/calls.log"; echo wifi-OldNet > "$T/cons"
rc=0; WIFI_FILE="$T/wifi2b.txt" NMCLI="$T/nmcli" IW=true FAIL_ADD=1 bash "$S" > "$T/out3b.txt" || rc=$?
check "refused add exits 1" "[ $rc = 1 ]"
check "old connection kept when the add fails" "! grep -q 'connection delete' '$T/calls.log' && [ \"\$(cat '$T/cons')\" = wifi-OldNet ]"
check "password kept for another try" "grep -qx 'PASSWORD=short' '$T/wifi2b.txt'"

# 3c. A temporary profile left by an interrupted run is replaced, not duplicated
printf 'SSID=OldNet\nPASSWORD=longenough\n' > "$T/wifi2c.txt"
: > "$T/calls.log"; printf 'wifi-OldNet\nwifi-OldNet (importing)\n' > "$T/cons"
WIFI_FILE="$T/wifi2c.txt" NMCLI="$T/nmcli" IW=true bash "$S" > "$T/out3c.txt"
check "leftover temporary profile removed" "[ \"\$(cat '$T/cons')\" = wifi-OldNet ]"
: > "$T/cons"

# 4. Empty template: no-op
cp "$TOP/boot-files/wifi.txt" "$T/wifi3.txt"; : > "$T/calls.log"
WIFI_FILE="$T/wifi3.txt" NMCLI="$T/nmcli" IW=true bash "$S" > "$T/out4.txt"
check "empty template does nothing" "! grep -q 'connection' '$T/calls.log' && cmp -s '$T/wifi3.txt' '$TOP/boot-files/wifi.txt'"
# 5. Quoted values are accepted (quotes removed)
printf 'SSID="Cafe Net"\nPASSWORD="pa ss"\n' > "$T/wifi5.txt"; : > "$T/calls.log"
WIFI_FILE="$T/wifi5.txt" NMCLI="$T/nmcli" IW=true bash "$S" > "$T/out5.txt"
check "quotes stripped" "grep -q 'con-name wifi-Cafe Net (importing) ssid Cafe Net wifi-sec.key-mgmt wpa-psk wifi-sec.psk pa ss ' '$T/calls.log'"
safe_rm -r "$T"
exit $fail
