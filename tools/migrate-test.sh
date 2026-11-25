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
ARCH_DIR="${HANDTOP_TEST_ARCHIVE:-$WORK/device-archive/r1}"   # run.sh: shared by parallel runs with their own WORK
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
assert_build_paths
[ -z "$(losetup -j "$WORK/migrate.img" 2>/dev/null)" ] || die "$WORK/migrate.img is still attached to a loop device (a killed run?): losetup -d it first"
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
migrate_ask() { chroot "$ROOTFS" "${ENVV[@]}" HANDTOP_MIGRATE_SOURCE=$'URIs: copy:/srv/handtop-test\nSuites: ./' \
              HANDTOP_MIGRATE_NO_RESTART=1 bash /root/m/handtop-migrate; }
hu() { chroot "$ROOTFS" "${ENVV[@]}" /usr/local/sbin/handtop-update "$@"; }
SD=/var/lib/handtop-update
nothing_left() { [ ! -e "$ROOTFS/etc/apt/sources.list.d/handtop.sources" ] && [ ! -e "$ROOTFS/etc/systemd/system/handtop-update-apply.service" ] &&
  [ ! -e "$ROOTFS$SD/plan.json" ] && [ ! -e "$ROOTFS$SD/migrate-undo" ] && [ "$(chroot "$ROOTFS" apt-mark showhold | sort | xargs)" = "$holds0" ]; }

echo "== the user's changes before migrating"
CONF=/etc/rg35xxh/power.conf; OTHER=/usr/local/bin/rg35xxh-theme
echo "# changed by the user (migrate-test)" >> "$ROOTFS$CONF"
echo "# changed by the user (migrate-test)" >> "$ROOTFS$OTHER"
MODEF=/usr/local/bin/rg35xxh-battery; chmod 700 "$ROOTFS$MODEF"     # permissions only (review #44)
OLDH=/usr/include/libavutil/avutil.h; KEEPH=/usr/include/libavutil/common.h   # v0.4.x's own FFmpeg (#42)
echo "/* changed by the user (migrate-test) */" >> "$ROOTFS$KEEPH"
chroot "$ROOTFS" apt-mark hold nano >/dev/null                       # the user's own hold
chroot "$ROOTFS" systemctl disable rg35xxh-bootlog.timer >/dev/null 2>&1   # a service the user turned off
holds0=$(chroot "$ROOTFS" apt-mark showhold | sort | xargs)

echo "== answering No puts everything back"
out=$(echo n | chroot "$ROOTFS" "${ENVV[@]}" HANDTOP_MIGRATE_SOURCE=$'URIs: copy:/srv/handtop-test\nSuites: ./' \
        HANDTOP_MIGRATE_NO_RESTART=1 bash /root/m/handtop-migrate 2>&1 || true)
grep -q "cancelled: nothing installed" <<<"$out" && ok "No: cancelled" || bad "No: $(echo "$out" | tail -3)"
[ ! -e "$ROOTFS/etc/apt/sources.list.d/handtop.sources" ] && [ ! -e "$ROOTFS/etc/systemd/system/handtop-update-apply.service" ] &&
  [ ! -e "$ROOTFS/var/lib/handtop-update/plan.json" ] && ok "No: source, apply unit and plan gone" || bad "No: leftovers"
[ "$(chroot "$ROOTFS" apt-mark showhold | sort | xargs)" = "$holds0" ] && ok "No: holds as before ($holds0)" ||
  bad "No: holds $(chroot "$ROOTFS" apt-mark showhold | sort | xargs), were $holds0"

echo "== no rootfix.cpio on the boot partition: refused, nothing changed (review 2026-11-26 #65)"
mv "$ROOTFS/boot/firmware/rootfix.cpio" "$WORK/rootfix.keep"
out=$(migrate 2>&1 || true)
grep -q "no rootfix.cpio to recognise it by" <<<"$out" && nothing_left && ok "missing rootfix.cpio refused, everything put back" ||
  bad "missing rootfix.cpio: $(echo "$out" | tail -2)"
mv "$WORK/rootfix.keep" "$ROOTFS/boot/firmware/rootfix.cpio"

echo "== a run killed before the answer (power cut): the next run puts it back first (review 2026-11-26 #73)"
L="$ROOTFS/var/log/handtop-migrate.log"; n0=$(stat -c %s "$L" 2>/dev/null || echo 0)
# The answer comes from a FIFO this test holds open (no answer: it waits). Only processes whose root
# is this test's ROOTFS are killed: another test may run the same script in its own chroot.
ANS="$WORK/migrate-answer"; [ -e "$ANS" ] && safe_rm "$ANS"; mkfifo "$ANS"
migrate_ask < "$ANS" >/dev/null 2>&1 & MP=$!
exec 7> "$ANS"
for _ in $(seq 900); do tail -c +$((n0 + 1)) "$L" 2>/dev/null | grep "4/4 Install at the next start" >/dev/null &&
  [ -e "$ROOTFS$SD/plan.json" ] && break; sleep 1; done
RR=$(realpath "$ROOTFS")
for p in $(pgrep -f "bash /root/m/handtop-migrate" || true); do
  [ "$(readlink "/proc/$p/root" 2>/dev/null)" = "$RR" ] && kill -9 "$p" 2>/dev/null
done
exec 7>&-; wait "$MP" 2>/dev/null || true; safe_rm "$ANS"
[ -d "$ROOTFS$SD/migrate-undo" ] && [ -e "$ROOTFS/etc/apt/sources.list.d/handtop.sources" ] &&
  ok "killed while asking: changes and their undo record are on the card" || bad "killed run left no undo record"
out=$(echo n | migrate_ask 2>&1 || true)
grep -q "An earlier run stopped before the move was scheduled" <<<"$out" && nothing_left &&
  ok "next run put the killed run's changes back (source, unit, plan, holds)" || bad "after a killed run: $(echo "$out" | tail -3)"

# The metapackage's version in the test archive (a release build's is a bare 0.5.0; review #81).
V1=$(awk '/^Package: /{p=$2} /^Version: /{if (p == "handtop") print $2}' "$ARCH_DIR"/Packages | sort -V | tail -1)
[ -n "$V1" ] || { echo "no handtop package in $ARCH_DIR/Packages" >&2; exit 1; }

echo "== handtop-migrate (plan, download, schedule)"
if out=$(migrate 2>&1); then ok "handtop-migrate scheduled"; else bad "handtop-migrate failed: $(echo "$out" | tail -5)"; fi
echo "$out" | tail -12
grep -q "This card: Handtop $REL" <<<"$out" && ok "card named $REL" || bad "card not named $REL"
grep -q "kept, you changed it: $CONF" <<<"$out" && ok "changed config file announced" || bad "changed config not announced"
grep -q "you changed $OTHER" <<<"$out" && ok "changed Handtop file announced" || bad "changed file not announced"
[ "$(readlink "$ROOTFS/system-update")" = /var/lib/handtop-update ] && ok "maintenance boot scheduled" || bad "no marker"
[ -z "$(ver handtop)" ] && ok "nothing installed before the restart" || bad "handtop installed before the restart"

echo "== the move stops after its attempts: kept, the app can't replace it, the command resumes it (#63, #73)"
python3 - "$ROOTFS$SD/schedule.json" <<'PY'
import json, sys
d = json.load(open(sys.argv[1])); d["attempts"] = 3; json.dump(d, open(sys.argv[1], "w"))
PY
hu apply >/dev/null 2>&1 || true
st=$(hu status)
[ "$(echo "$st" | js 'd["migration_kept"] and d["kind"]')" = migrate ] && ok "plan kept after the attempt limit" || bad "status: $st"
chroot "$ROOTFS" apt-mark showhold | grep -x libavcodec61 >/dev/null && ok "FFmpeg held again meanwhile" ||
  bad "holds after the failed move: $(chroot "$ROOTFS" apt-mark showhold | xargs)"
out=$(hu download 2>&1 || true); grep -q "hasn't finished" <<<"$out" && ok "download refused while the move is kept" || bad "download: $out"
out=$(hu channel testing 2>&1 || true); grep -q "hasn't finished" <<<"$out" && ok "channel switch refused while the move is kept" || bad "channel: $out"
pid=$(echo "$st" | js 'd["plan"]')
deb=$(ls "$ROOTFS$SD"/cache/handtop-desktop_*.deb); printf 'XXXX' | dd of="$deb" bs=1 seek=2000 conv=notrunc status=none
out=$(migrate 2>&1 || true)
grep -q "didn't finish" <<<"$out" && [ "$(hu status | js 'd["scheduled"] and d["plan"]')" = "$pid" ] &&
  ok "the command resumed the same plan (a damaged file fetched again)" || bad "resume: $(echo "$out" | tail -3)"
! chroot "$ROOTFS" apt-mark showhold | grep -x libavcodec61 >/dev/null && ok "holds released again for the install" || bad "still held"

echo "== files changed after the plan keep the user's version (decision 2026-11-25, #64)"
CONF2=/etc/rg35xxh/lowpower.conf; OTHER2=/usr/local/bin/rg35xxh-autosleep
echo "# changed after the plan (migrate-test)" >> "$ROOTFS$CONF2"
echo "# changed after the plan (migrate-test)" >> "$ROOTFS$OTHER2"

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
[ "$(chroot "$ROOTFS" apt-mark showhold | xargs)" = nano ] && ok "v0.4.x's FFmpeg holds released, the user's own kept" ||
  bad "holds: $(chroot "$ROOTFS" apt-mark showhold | xargs)"
[ "$(chroot "$ROOTFS" systemctl is-enabled rg35xxh-bootlog.timer 2>/dev/null)" = disabled ] && ok "a service the user disabled stays disabled" ||
  bad "rg35xxh-bootlog.timer: $(chroot "$ROOTFS" systemctl is-enabled rg35xxh-bootlog.timer 2>&1)"
[ "$(chroot "$ROOTFS" systemctl is-enabled handtop-update-boot-check.service 2>/dev/null)" = enabled ] && ok "new units enabled" ||
  bad "boot-check unit not enabled"
[ -z "$(chroot "$ROOTFS" dpkg --audit)" ] && ok "dpkg --audit clean" || bad "dpkg --audit: $(chroot "$ROOTFS" dpkg --audit | head -3)"
# Allowed: the test's own config change, and the source file the test pointed at its archive.
v=$(chroot "$ROOTFS" dpkg --verify handtop-core handtop-desktop handtop-video handtop-keyring 2>&1 |
    grep -v -e " $CONF\$" -e " $CONF2\$" -e " /etc/apt/sources.list.d/handtop.sources\$" || true)
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
grep -q "\"$MODEF\": \"700\"" "$ROOTFS/var/backups/handtop-migrate/modes.json" 2>/dev/null &&
  [ "$(stat -c %a "$ROOTFS$MODEF")" = 755 ] && ok "changed permissions noted, Handtop's back" ||
  bad "permissions: $(stat -c %a "$ROOTFS$MODEF"), modes.json: $(cat "$ROOTFS/var/backups/handtop-migrate/modes.json" 2>&1)"
[ ! -e "$ROOTFS$OLDH" ] && grep -q "changed by the user" "$ROOTFS$KEEPH" &&
  grep -q "removed [0-9]* unchanged file(s) of v0.4.x's own FFmpeg" "$WORK/migrate-apply.out" "$ROOTFS"/var/log/handtop-update/*.log 2>/dev/null &&
  ok "old FFmpeg leftovers removed, the user's changed one kept" ||
  bad "old FFmpeg files: $OLDH $([ -e "$ROOTFS$OLDH" ] && echo still there || echo gone), $KEEPH $(grep -c "changed by the user" "$ROOTFS$KEEPH" 2>&1)"
grep -q "changed after the plan" "$ROOTFS$CONF2" && ok "config file changed after the plan: the user's version stays" ||
  bad "$CONF2 replaced"
grep -q "changed after the plan" "$ROOTFS/var/backups/handtop-migrate$OTHER2.changed-after-plan" 2>/dev/null &&
  ! grep -q "changed after the plan" "$ROOTFS$OTHER2" && ok "other file changed after the plan: saved, then Handtop's" ||
  bad "$OTHER2: no .changed-after-plan backup"
grep -q "after the move was planned" <<<"$st" && ok "the result lists them" || bad "not in the result"
for u in handtop-recovery.service handtop-update-boot-check.service; do
  [ "$(chroot "$ROOTFS" systemctl is-enabled "$u" 2>/dev/null)" = enabled ] && ok "$u enabled (#83)" || bad "$u not enabled"
done
lnk=/usr/lib/aarch64-linux-gnu/libavcodec.so
[ ! -L "$ROOTFS$lnk" ] || chroot "$ROOTFS" dpkg -S "$lnk" >/dev/null 2>&1 &&
  ok "v0.4.x's unversioned FFmpeg link gone or a package's (#75)" || bad "$lnk left, no package owns it"
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
