#!/bin/bash
# Test moving a released v0.4.x card onto packages (tools/apt/handtop-migrate and the update worker's
# migrate plan) in a chroot copy of the release image's root filesystem, against the test archive
# tools/update-device-archive.sh built (release 1 = this checkout's packages). Debian's sources stay
# on: a v0.4.0 card needs new Debian packages (python3-mpv, ristretto, tumbler).
# Before migrating, the test changes one config file (must stay, with the package's version next
# to it) and one other Handtop file (must be backed up, then replaced). After: every Handtop package
# installed, dpkg clean, unchanged config files at the package's version, identity files, the boot
# partition's recovery.txt (and on v0.4.0 the rescue input file), the result, a second run refused.
#
#   sudo tools/migrate-test.sh <handtop-...-v0.4.x.img.xz>   (in a second checkout or worktree, after
#   tools/update-device-archive.sh; its work/rootfs is overwritten)
set -euo pipefail
source "$(dirname "$(realpath "$0")")/../build/config.sh"
source "$TOP/build/lib/chroot.sh"
IMG=$(realpath "${1:?usage: migrate-test.sh <image.img.xz>}")
ARCH_DIR="$WORK/device-archive/r1"
[ -f "$ARCH_DIR/Packages" ] || die "no test archive in $ARCH_DIR: run tools/update-device-archive.sh first"
MNT="$WORK/migrate-mnt"; LOOP=""
cleanup() {
  mountpoint -q "$ROOTFS/boot/firmware" && umount "$ROOTFS/boot/firmware"
  chroot_umount
  mountpoint -q "$MNT" && umount "$MNT"
  [ -n "$LOOP" ] && losetup -d "$LOOP"
  [ -e "$WORK/migrate.img" ] && safe_rm "$WORK/migrate.img"
  return 0
}
trap cleanup EXIT
mkdir -p "$WORK" "$MNT"
echo "== $(basename "$IMG"): root filesystem and boot partition"
xz -dc "$IMG" > "$WORK/migrate.img"
LOOP=$(losetup -P --show -f "$WORK/migrate.img")
assert_no_mounts "$ROOTFS"
mount -o ro "${LOOP}p2" "$MNT"
rsync -aHAXx --delete --numeric-ids "$MNT/" "$ROOTFS/"
umount "$MNT"
FATCOPY="$WORK/migrate-fat"; [ -e "$FATCOPY" ] && safe_rm -r "$FATCOPY"; mkdir -p "$FATCOPY"
mount -o ro "${LOOP}p1" "$MNT"
cp -a "$MNT/." "$FATCOPY/"
umount "$MNT"
losetup -d "$LOOP"; LOOP=""
safe_rm "$WORK/migrate.img"
mkdir -p "$ROOTFS/boot/firmware"
mount -t tmpfs -o size=64m handtop-test-fat "$ROOTFS/boot/firmware"
cp -a "$FATCOPY/." "$ROOTFS/boot/firmware/"
REL=$(basename "$IMG" | grep -o 'v0\.4\.[0-9]*')

R="$ROOTFS/srv/handtop-test"; [ -e "$R" ] && safe_rm -r "$R"; mkdir -p "$R"
cp "$ARCH_DIR"/* "$R/"
mkdir -p "$ROOTFS/root/m"
cp "$TOP/tools/apt/handtop-migrate" "$TOP/overlay/usr/share/keyrings/handtop-archive.asc" "$ROOTFS/root/m/"
chroot_mount

pass=0; fail=0
ok()  { echo "PASS: $*"; pass=$((pass+1)); }
bad() { echo "FAIL: $*"; fail=$((fail+1)); }
ver() { chroot "$ROOTFS" dpkg-query -W -f '${Version}' "$1" 2>/dev/null || true; }
js()  { python3 -c "import json,sys
try:
    d=json.load(sys.stdin); print($1)
except Exception as e:
    print('ERR', e)"; }
ENVV=(env HANDTOP_UPDATE_NO_POWER_ACTION=1 HANDTOP_UPDATE_CHROOT=1)
migrate() { chroot "$ROOTFS" "${ENVV[@]}" HANDTOP_MIGRATE_SOURCE=$'URIs: copy:/srv/handtop-test\nSuites: ./' \
              HANDTOP_MIGRATE_YES=1 HANDTOP_MIGRATE_NO_RESTART=1 bash /root/m/handtop-migrate; }

echo "== the user's changes before migrating"
CONF=/etc/rg35xxh/power.conf; OTHER=/usr/local/bin/rg35xxh-theme
echo "# changed by the user (migrate-test)" >> "$ROOTFS$CONF"
echo "# changed by the user (migrate-test)" >> "$ROOTFS$OTHER"
V1=$(sed -n 's/^Version: //p' "$ARCH_DIR"/Packages | grep -v '^7:' | sort -u | grep -m1 '+')

echo "== handtop-migrate (plan, download, schedule)"
if out=$(migrate 2>&1); then ok "handtop-migrate scheduled"; else bad "handtop-migrate failed: $(echo "$out" | tail -5)"; fi
echo "$out" | tail -12
grep -q "This card: Handtop $REL" <<<"$out" && ok "card named $REL" || bad "card not named $REL"
grep -q "kept, you changed it: $CONF" <<<"$out" && ok "changed config file announced" || bad "changed config not announced"
grep -q "you changed $OTHER" <<<"$out" && ok "changed Handtop file announced" || bad "changed file not announced"
[ "$(readlink "$ROOTFS/system-update")" = /var/lib/handtop-update ] && ok "maintenance boot scheduled" || bad "no marker"
[ -z "$(ver handtop)" ] && ok "nothing installed before the restart" || bad "handtop installed before the restart"

echo "== maintenance boot (apply)"
chroot "$ROOTFS" "${ENVV[@]}" /usr/local/sbin/handtop-update apply > "$WORK/migrate-apply.out" 2>&1 || true
tail -3 "$WORK/migrate-apply.out"
st=$(chroot "$ROOTFS" "${ENVV[@]}" /usr/local/sbin/handtop-update status)
[ "$(echo "$st" | js 'd["last_result"]["ok"] and d["last_result"]["migrated_from"]')" = "$REL" ] &&
  ok "result: moved from $REL" || bad "result: $(echo "$st" | js 'd["last_result"]')"
for p in handtop handtop-core handtop-desktop handtop-video handtop-keyring handtop-platform-h700 "handtop-modules-h700-$KVER"; do
  [ "$(ver "$p")" = "$V1" ] || bad "$p is '$(ver "$p")', expected $V1"
done
[ "$(ver handtop)" = "$V1" ] && ok "Handtop's packages at $V1"
[ "$(ver libavcodec61)" = "$FFMPEG_HANDTOP_VERSION" ] && ok "FFmpeg at Handtop's build" || bad "libavcodec61 is $(ver libavcodec61)"
[ -z "$(chroot "$ROOTFS" apt-mark showhold)" ] && ok "no holds left" || bad "holds: $(chroot "$ROOTFS" apt-mark showhold | tr '\n' ' ')"
[ -z "$(chroot "$ROOTFS" dpkg --audit)" ] && ok "dpkg --audit clean" || bad "dpkg --audit: $(chroot "$ROOTFS" dpkg --audit | head -3)"
# Allowed: the test's own config change, and the source file the test pointed at its archive.
v=$(chroot "$ROOTFS" dpkg --verify handtop-core handtop-desktop handtop-video handtop-keyring 2>&1 |
    grep -v -e " $CONF\$" -e " /etc/apt/sources.list.d/handtop.sources\$" || true)
[ -z "$v" ] && ok "dpkg --verify clean (but the test's changes)" || bad "dpkg --verify: $v"
grep -q "changed by the user" "$ROOTFS$CONF" && [ -f "$ROOTFS$CONF.dpkg-dist" ] && ok "changed config kept, package's next to it" || bad "changed config not kept"
grep -q "changed by the user" "$ROOTFS/var/backups/handtop-migrate$OTHER" && ! grep -q "changed by the user" "$ROOTFS$OTHER" &&
  ok "changed Handtop file backed up and replaced" || bad "changed Handtop file: backup or replace missing"
grep -q "^ram=DDR4$" "$ROOTFS/etc/handtop/model" && grep -q "^kernel_sha256=" "$ROOTFS/etc/handtop/boot-abi" &&
  ok "/etc/handtop/model and boot-abi written" || bad "identity files"
[ -f "$ROOTFS/boot/firmware/recovery.txt" ] && ok "recovery.txt on the boot partition" || bad "no recovery.txt"
if [ "$REL" = v0.4.0 ]; then
  grep -q '^\[rescue\]' "$ROOTFS/boot/firmware/rg35xxh-input.conf" && [ -f "$ROOTFS/boot/firmware/rg35xxh-input.conf.v0.4.0" ] &&
    ok "v0.4.0 input file is the rescue template, old one kept" || bad "v0.4.0 input file not replaced"
fi
[ ! -L "$ROOTFS/system-update" ] && ok "marker removed" || bad "marker still there"
[ -f "$ROOTFS/usr/local/lib/rg35xxh-update/handtop_update/app.py" ] && ok "Update app installed" || bad "no Update app"
[ "$(cat "$ROOTFS/usr/sbin/policy-rc.d" 2>/dev/null)" = "$(printf '#!/bin/sh\nexit 101')" ] && ok "policy-rc.d as before" || bad "policy-rc.d changed"

echo "== a second run is refused"
out=$(migrate 2>&1 || true)
grep -q "has Handtop's packages already" <<<"$out" && ok "second run refused" || bad "second run: $(echo "$out" | tail -2)"
echo "== the Update app's check works afterwards"
st=$(chroot "$ROOTFS" "${ENVV[@]}" /usr/local/sbin/handtop-update check || true)
[ "$(echo "$st" | js 'd["ok"]')" = True ] && ok "check after the move" || bad "check: $(echo "$st" | head -c 300)"

echo "$REL: $pass passed, $fail failed"
[ "$fail" = 0 ]
