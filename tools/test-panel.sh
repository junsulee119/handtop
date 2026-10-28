#!/bin/bash
# Tests rg35xxh-panel with a fake boot partition and a fake PE6 reading (no GPIO, no reboot).
# Uses work/test-panel/.
set -euo pipefail
source "$(dirname "$(realpath "$0")")/../build/config.sh"
T="$WORK/test-panel"; [ -e "$T" ] && safe_rm -r "$T"; mkdir -p "$T/boot"
S="$TOP/overlay/usr/local/sbin/rg35xxh-panel"
fail=0
check() { if eval "$2"; then echo "ok    $1"; else echo "FAIL  $1"; fail=1; fi; }
run() {   # run <PE6> -> output in $T/out.txt
  RG35XXH_PANEL_BOOT="$T/boot" RG35XXH_PANEL_STATE="$T/state" RG35XXH_PANEL_TEST_PE6="$1" \
    RG35XXH_PANEL_DRYRUN=1 python3 "$S" > "$T/out.txt" 2>&1 || true
}
printf 'regular' > "$T/boot/dtb-regular.img"
printf 'rev6'    > "$T/boot/dtb-rev6.img"
cp "$T/boot/dtb-regular.img" "$T/boot/dtb.img"
is() { cmp -s "$T/boot/dtb.img" "$T/boot/dtb-$1.img"; }

run 1
check "regular board, regular dtb: nothing" "is regular && grep -q 'matches' '$T/out.txt' && [ ! -e '$T/boot/logs/panel.txt' ]"
run 0
check "rev6 board: switched to rev6" "is rev6 && grep -q 'switching to dtb-rev6.img' '$T/out.txt'"
check "switch logged on the boot partition" "grep -q 'switching to dtb-rev6.img' '$T/boot/logs/panel.txt'"
check "log has CRLF line ends" "grep -q \$'\\r\$' '$T/boot/logs/panel.txt'"
check "switch remembered" "grep -qx rev6 '$T/state'"
check "no temporary file left" "[ ! -e '$T/boot/dtb.img.new' ]"
run 0
check "next boot matches, memory cleared" "is rev6 && [ ! -e '$T/state' ]"
run 1
check "card moved to a regular board: back to regular" "is regular"
run 0
check "pin flips right after a switch: not switched again (no restart loop)" "is regular && grep -q 'not switching again' '$T/out.txt' && grep -q 'not switching again' '$T/boot/logs/panel.txt'"
run 1
check "matches again: loop guard released" "is regular && [ ! -e '$T/state' ]"
run 0
check "a later rev6 reading switches again" "is rev6"
printf '\xEF\xBB\xBF# comment\r\nregular  # forced\r\n' > "$T/boot/panel.txt"
run 0
check "panel.txt regular overrides the pin" "is regular && grep -q 'panel.txt says regular' '$T/out.txt' && [ ! -e '$T/state' ]"
printf 'rev6\n' > "$T/boot/panel.txt"
run ""
check "panel.txt rev6 works without a pin reading" "is rev6"
printf 'bogus\n' > "$T/boot/panel.txt"
run 1
check "unknown panel.txt value falls back to auto" "is regular && grep -q 'unknown value' '$T/out.txt'"
printf 'auto\n' > "$T/boot/panel.txt"
printf 'custom' > "$T/boot/dtb.img"
run 0
check "hand-changed dtb.img left alone" "[ \"\$(cat '$T/boot/dtb.img')\" = custom ] && grep -q 'left alone' '$T/out.txt'"
cp "$T/boot/dtb-regular.img" "$T/boot/dtb.img"
run x
check "unreadable pin: nothing changed" "is regular"
printf 'stale' > "$T/boot/dtb.img.new"
run 0
check "leftover dtb.img.new from a power cut: switch still works" "is rev6 && [ ! -e '$T/boot/dtb.img.new' ]"
run 0
: > "$T/boot/dtb-regular.img"
run 1
check "empty source file: dtb.img unchanged" "is rev6"
printf 'regular' > "$T/boot/dtb-regular.img"; cp "$T/boot/dtb-regular.img" "$T/boot/dtb.img"
rm "$T/boot/dtb-rev6.img"
run 0
check "rev6 file missing: nothing changed" "is regular && grep -q missing '$T/out.txt'"
[ "$fail" = 0 ] && echo "all panel tests passed" || { echo "panel tests FAILED"; exit 1; }
