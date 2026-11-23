#!/bin/bash
# Test the update worker (handtop-update) and handtop-recovery in a chroot copy of a finished build's
# root filesystem, against a local test archive with a newer build of every Handtop package and of
# Handtop's FFmpeg. Covers: check / download / schedule / apply, frozen package lists, recovery.txt
# both ways (FFmpeg taken back too, keyring not), damaged downloads, the attempt limit, a power cut
# while installing, a cut after the result was written, a stopped maintenance boot, a foreign
# /system-update, battery readings, the new-image check, the channel switch and the last-known-good
# tool copies. No restart happens (HANDTOP_UPDATE_NO_POWER_ACTION). The maintenance boot itself
# (systemd, console) is tested in QEMU and on the device (docs/services/update.md).
#
#   sudo SRC_WORK=/path/to/finished/work tools/update-test.sh   (in a second checkout or worktree:
#   its own work/ is the scratch copy; SRC_WORK is only read)
set -euo pipefail
source "$(dirname "$(realpath "$0")")/../build/config.sh"
source "$TOP/build/lib/chroot.sh"
SRC_WORK="$(realpath "${SRC_WORK:?SRC_WORK: the work directory of a finished build}")"
[ "$(realpath -m "$WORK")" != "$SRC_WORK" ] || die "WORK must be a scratch directory, not SRC_WORK"
[ -d "$SRC_WORK/rootfs/usr" ] || die "no finished rootfs in $SRC_WORK"
ls "$SRC_WORK"/pkg-ffmpeg/*.deb >/dev/null || die "no FFmpeg packages in $SRC_WORK/pkg-ffmpeg"
trap 'mountpoint -q "$ROOTFS/boot/firmware" && umount "$ROOTFS/boot/firmware"; chroot_umount' EXIT
mkdir -p "$WORK"
echo "== copy of $SRC_WORK/rootfs"
assert_no_mounts "$SRC_WORK/rootfs" "$ROOTFS"
rsync -aHAXx --delete --numeric-ids "$SRC_WORK/rootfs/" "$ROOTFS/"
ln -sfn "$SRC_WORK/rocknix" "$ROCKNIX_EX"
# What 05 does with the overlay (the rootfs may be older than this checkout).
rsync -a --chown=root:root --chmod=D755,F644 "$TOP/overlay/" "$ROOTFS/"
chmod 755 "$ROOTFS"/usr/local/sbin/* "$ROOTFS"/usr/local/bin/*
chmod 0440 "$ROOTFS"/etc/sudoers.d/rg35xxh-*

echo "== release 1: the packages 09b builds and installs"
"$TOP/build/09b-packages.sh"
V1=$(chroot "$ROOTFS" dpkg-query -W -f '${Version}' handtop)
FF1="$FFMPEG_HANDTOP_VERSION"
FF2="${FF1%+handtop1}+handtop2"

echo "== FFmpeg $FF2: the same build repacked under a newer version"
FFD="$WORK/ff2"; [ -e "$FFD" ] && safe_rm -r "$FFD"; mkdir -p "$FFD/x"
for d in "$SRC_WORK"/pkg-ffmpeg/*.deb; do
  x="$FFD/x/$(basename "$d" .deb)"
  dpkg-deb -R "$d" "$x"
  for c in control shlibs; do   # literal string replacement (\Q..\E): versions contain . and +
    if [ -f "$x/DEBIAN/$c" ]; then FF1="$FF1" FF2="$FF2" perl -pi -e 's/\Q$ENV{FF1}\E/$ENV{FF2}/g' "$x/DEBIAN/$c"; fi
  done
  grep -q "^Version: $FF2\$" "$x/DEBIAN/control" || die "repack of $(basename "$d") failed"
  dpkg-deb --root-owner-group -b "$x" "$FFD/" >/dev/null
done
safe_rm -r "$FFD/x"

echo "== release 2: one changed script, newer version, depends on FFmpeg $FF2"
F=/usr/local/sbin/rg35xxh-bootlog
cp -a "$ROOTFS$F" "$WORK/bootlog.orig"
echo "# update-test release 2" >> "$ROOTFS$F"
V2="$V1+t2"
P2="$WORK/pkg2"; [ -e "$P2" ] && safe_rm -r "$P2"
HANDTOP_FFMPEG_VERSION="$FF2" python3 "$TOP/build/pkg/build-debs.py" "$ROOTFS" "$P2" "$V2"
KSHA=$(sed -n 's/^kernel_sha256=//p' "$ROOTFS/etc/handtop/boot-abi")
python3 "$TOP/build/pkg/build-platform-debs.py" "$ROOTFS" "$P2" "$V2" "$KVER" "$KSHA"
cp -a "$WORK/bootlog.orig" "$ROOTFS$F"          # the card still has release 1
# The test archive goes into the rootfs only now: build-debs.py would refuse its files.
R="$ROOTFS/srv/handtop-test"; [ -e "$R" ] && safe_rm -r "$R"; mkdir -p "$R"
cp "$WORK"/pkg/*.deb "$P2"/*.deb "$SRC_WORK"/pkg-ffmpeg/*.deb "$FFD"/*.deb "$R/"
index() {   # index [exclude-glob]: Packages + Release of the test archive (Origin Handtop)
  local T="$ROOTFS/srv/idx-tmp" f
  [ -e "$T" ] && safe_rm -r "$T"; mkdir -p "$T"
  for f in "$R"/*.deb; do
    # shellcheck disable=SC2254  # the argument is a glob on purpose
    case "$(basename "$f")" in ${1:-__none__}) ;; *) ln -s "../handtop-test/$(basename "$f")" "$T/" ;; esac
  done
  (cd "$ROOTFS/srv" && dpkg-scanpackages -m idx-tmp /dev/null 2>/dev/null | sed 's|^Filename: idx-tmp/|Filename: ./|' > "$R/Packages")
  (cd "$R" && apt-ftparchive -o APT::FTPArchive::Release::Origin=Handtop -o APT::FTPArchive::Release::Label=Handtop \
      -o APT::FTPArchive::Release::Suite=trixie-stable release . > "$WORK/Release" && mv "$WORK/Release" Release)
}
index

# Offline: only the test archive (flat, trusted; copy: so apt fills its cache as with https) as the Handtop source; Debian's sources off.
mkdir -p "$WORK/sources-off"
mv "$ROOTFS"/etc/apt/sources.list "$ROOTFS"/etc/apt/sources.list.d/*.list "$WORK/sources-off/" 2>/dev/null || true
printf 'Types: deb\nURIs: copy:/srv/handtop-test\nSuites: ./\nTrusted: yes\n' > "$ROOTFS/etc/apt/sources.list.d/handtop.sources"
SRCF=/etc/apt/sources.list.d/handtop.sources
edited=$(md5sum < "$ROOTFS$SRCF" | cut -d' ' -f1)

chroot_mount
# The real dpkg settings: no build-time unsafe I/O for these tests.
safe_rm "$ROOTFS/etc/dpkg/dpkg.cfg.d/99build-unsafe-io"
BUILD_POLICY=$(cat "$ROOTFS/usr/sbin/policy-rc.d")
pass=0; fail=0
ok()   { echo "PASS: $*"; pass=$((pass+1)); }
bad()  { echo "FAIL: $*"; fail=$((fail+1)); }
hu()   { chroot "$ROOTFS" env HANDTOP_UPDATE_NO_POWER_ACTION=1 HANDTOP_UPDATE_CHROOT=1 ${HU_ENV:-} /usr/local/sbin/handtop-update "$@"; }
hr()   { chroot "$ROOTFS" env HANDTOP_UPDATE_NO_POWER_ACTION=1 /usr/local/sbin/handtop-recovery; }
ver()  { chroot "$ROOTFS" dpkg-query -W -f '${Version}' "$1" 2>/dev/null || echo none; }
js()   { python3 -c "import json,sys
try:
    d=json.load(sys.stdin); print($1)
except Exception as e:
    print('ERR', e)"; }
S=/var/lib/handtop-update
expect_versions() {   # expect_versions <handtop version> <ffmpeg version>
  local p v
  for p in handtop handtop-core handtop-desktop handtop-video handtop-platform-h700 "handtop-modules-h700-$KVER"; do
    v=$(ver "$p"); [ "$v" = "$1" ] || { bad "$p is $v, expected $1"; return; }
  done
  v=$(ver libavcodec61); [ "$v" = "$2" ] || { bad "libavcodec61 is $v, expected $2"; return; }
  ok "Handtop at $1, FFmpeg at $2"
}
clean_dpkg() {
  [ -z "$(chroot "$ROOTFS" dpkg --audit)" ] && ok "dpkg --audit clean ($1)" || bad "dpkg --audit not clean ($1)"
  # dpkg --verify exits 0 even when files differ: read what it prints. Only the test's own edit is allowed.
  local v; v=$(chroot "$ROOTFS" dpkg --verify handtop-core handtop-desktop handtop-video handtop-keyring 2>&1 | grep -v " $SRCF\$" || true)
  [ -z "$v" ] && ok "dpkg --verify clean ($1)" || bad "dpkg --verify ($1): $v"
}
no_marker() { [ ! -L "$ROOTFS/system-update" ] && [ ! -e "$ROOTFS/system-update" ]; }
policy_back() { [ "$(cat "$ROOTFS/usr/sbin/policy-rc.d" 2>/dev/null)" = "$BUILD_POLICY" ] && [ ! -e "$ROOTFS/usr/sbin/policy-rc.d.handtop-saved" ]; }
dl() { hu check >/dev/null || true; hu download; }
# The boot partition: recovery reads recovery.txt only from a mounted filesystem.
fat_on()  { mkdir -p "$ROOTFS/boot/firmware"; mount -t tmpfs -o size=4m handtop-test-fat "$ROOTFS/boot/firmware"; }
fat_off() { umount "$ROOTFS/boot/firmware"; }

echo "== FFmpeg holds released (09b), units"
[ -z "$(chroot "$ROOTFS" apt-mark showhold)" ] && ok "no holds left" || bad "holds: $(chroot "$ROOTFS" apt-mark showhold | xargs)"
for u in handtop-update-apply handtop-update-boot-check handtop-recovery; do
  grep -qx "$u.service" "$ROOTFS/var/lib/handtop/units-enabled" && ok "$u enabled once" || bad "$u not in units-enabled"
done
hu download >/dev/null 2>&1 && bad "download without a check" || ok "download needs a check first"

echo "== check"
out=$(hu check || true); echo "$out" | head -20
for p in handtop handtop-core handtop-desktop handtop-video handtop-keyring handtop-platform-h700 "handtop-modules-h700-$KVER"; do
  names=$(echo "$out" | js "[u['name'] for u in d['updates']]"); grep -q "'$p'" <<<"$names" || bad "check misses $p"
done
[ "$(echo "$out" | js "[u['new'] for u in d['updates'] if u['name']=='libavcodec61'][0]")" = "$FF2" ] && ok "check lists Handtop and FFmpeg $FF2" || bad "check: $out"
[ "$(echo "$out" | js 'd["new_image_needed"]')" = "[]" ] && ok "no new image needed" || bad "new image: $(echo "$out" | js 'd["new_image_needed"]')"

echo "== download"
chroot "$ROOTFS" apt-mark auto libavutil59 >/dev/null    # a dependency: must stay automatic
out=$(dl || true); echo "$out"
[ "$(echo "$out" | js 'd["ok"] and d["rollback"]["possible"]')" = True ] && ok "download; going back possible" || bad "download: $out"
[ -f "$ROOTFS$S/previous.next/manifest.json" ] && ok "release 1 staged as previous.next" || bad "nothing staged"
[ ! -e "$ROOTFS$S/previous" ] && ok "previous/ untouched until the install starts" || bad "previous/ changed at download"
grep -q libavcodec61 "$ROOTFS$S/previous.next/manifest.json" && ok "FFmpeg $FF1 kept for going back" || bad "FFmpeg not kept"
grep -q '"handtop-keyring"' "$ROOTFS$S/previous.next/manifest.json" && bad "keyring kept for going back" || ok "keyring not kept (never taken back)"

echo "== the package lists change after the download (release 2 leaves the index): the plan still holds"
index 'handtop*t2*'
chroot "$ROOTFS" apt-get update -qq >/dev/null 2>&1 || true
out=$(hu schedule || true); echo "$out"
[ -L "$ROOTFS/system-update" ] && ok "marker set" || bad "no marker"
out2=$(hu schedule || true)
[ "$(echo "$out2" | js 'd["ok"]')" = True ] && ok "scheduling the same plan again is harmless" || bad "reschedule: $out2"
hu download >/dev/null 2>&1 && bad "download replaced a scheduled plan" || ok "download refused while scheduled"

echo "== apply"
hu apply || true
# (captured first: with pipefail, grep -q closing the pipe early would fail the pipeline)
autos=$(chroot "$ROOTFS" apt-mark showauto)
grep -qx libavutil59 <<<"$autos" && ok "a dependency stays marked automatic" || bad "libavutil59 became manual"
expect_versions "$V2" "$FF2"
grep -q "update-test release 2" "$ROOTFS$F" && ok "changed file installed" || bad "changed file not installed"
no_marker && ok "marker removed" || bad "marker still there"
policy_back && ok "build's policy-rc.d put back, ours gone" || bad "policy-rc.d: $(cat "$ROOTFS/usr/sbin/policy-rc.d" 2>/dev/null)"
st=$(hu status)
[ "$(echo "$st" | js 'd["last_result"]["ok"] and d["last_result"]["rollback_available"]')" = True ] && ok "result: ok, going back available" || bad "result: $st"
[ "$(echo "$st" | js 'd["previous_release"]')" = "$V1" ] && ok "previous/ is release 1 now" || bad "previous: $(echo "$st" | js 'd["previous_release"]')"
[ "$(md5sum < "$ROOTFS$SRCF" | cut -d' ' -f1)" = "$edited" ] && ok "edited handtop.sources kept" || bad "edited handtop.sources replaced"
clean_dpkg "after the update"
index
chroot "$ROOTFS" apt-get update -qq >/dev/null 2>&1 || true

echo "== recovery.txt: joypad=previous, handtop=previous (FFmpeg goes back too, the keyring doesn't)"
fat_on
printf '\xef\xbb\xbfJoypad=Previous\r\nhandtop=previous\r\n' > "$ROOTFS/boot/firmware/recovery.txt"
hr || true
grep -q '^joypad=none' "$ROOTFS/boot/firmware/recovery.txt" && ok "recovery.txt reset" || bad "recovery.txt not reset"
[ ! -e "$ROOTFS$S/recovery-request.json" ] && ok "saved request done" || bad "saved request left"
modpath=$(chroot "$ROOTFS" modinfo -k "$KVER" -n rocknix-singleadc-joypad || true)
[[ "$modpath" == */updates/handtop-recovery/* ]] && ok "joypad override used" || bad "joypad resolves to $modpath"
[ -L "$ROOTFS/system-update" ] && [ "$(hu status | js 'd["kind"]')" = recovery ] && ok "going back scheduled" || bad "no recovery plan"
hu apply || true
expect_versions "$V1" "$FF1"
[ "$(ver handtop-keyring)" = "$V2" ] && ok "keyring stays at release 2" || bad "keyring is $(ver handtop-keyring)"
grep -q "update-test release 2" "$ROOTFS$F" && bad "release 2 file still there" || ok "release 1 file back"
[ "$(md5sum < "$ROOTFS$SRCF" | cut -d' ' -f1)" = "$edited" ] && ok "edited handtop.sources kept" || bad "edited handtop.sources replaced"
clean_dpkg "after going back"

echo "== a cut after the request was saved: the next start finishes it (joypad=current)"
printf 'joypad=none\r\nhandtop=none\r\n' > "$ROOTFS/boot/firmware/recovery.txt"
printf '{"joypad": "current", "handtop": "none"}' > "$ROOTFS$S/recovery-request.json"
hr || true
modpath=$(chroot "$ROOTFS" modinfo -k "$KVER" -n rocknix-singleadc-joypad || true)
[[ "$modpath" != */updates/* ]] && ok "joypad=current finished from the saved request" || bad "joypad still $modpath"
printf 'joypad=current\n' > "$ROOTFS/boot/firmware/recovery.txt"
hr || true
modpath=$(chroot "$ROOTFS" modinfo -k "$KVER" -n rocknix-singleadc-joypad || true)
[[ "$modpath" != */updates/* ]] && ok "joypad=current again: re-indexed, still the packaged driver" || bad "joypad $modpath"
head -c 70000 /dev/zero | tr '\0' 'x' > "$ROOTFS/boot/firmware/recovery.txt"
hr || true; no_marker && ok "oversized recovery.txt ignored" || bad "oversized recovery.txt acted on"
fat_off

echo "== damaged download, same size"
out=$(dl || true)
deb=$(ls "$ROOTFS$S"/cache/handtop-desktop_*.deb)
printf 'XXXX' | dd of="$deb" bs=1 seek=2000 conv=notrunc status=none
out=$(hu schedule || true)
grep -q damaged <<<"$out" && ok "schedule refuses a damaged file" || bad "schedule: $out"
hu cancel >/dev/null; out=$(dl || true); hu schedule >/dev/null || true
deb=$(ls "$ROOTFS$S"/cache/handtop-desktop_*.deb)
printf 'XXXX' | dd of="$deb" bs=1 seek=2000 conv=notrunc status=none
hu apply || true
expect_versions "$V1" "$FF1"
no_marker && ok "marker removed after the refusal" || bad "marker left"
[ "$(hu status | js 'd["last_result"]["ok"]')" = False ] && ok "refusal recorded" || bad "refusal not recorded"
clean_dpkg "after the refused install"

echo "== attempt limit"
hu cancel >/dev/null || true; dl >/dev/null || true; hu schedule >/dev/null || true
python3 - "$ROOTFS$S/schedule.json" <<'P'
import json, sys; p = sys.argv[1]; d = json.load(open(p)); d["attempts"] = 3; json.dump(d, open(p, "w"))
P
hu apply || true
expect_versions "$V1" "$FF1"
no_marker && ok "gives up after 3 attempts" || bad "still scheduled after 3 attempts"

echo "== power cut while installing: some packages unpacked at the new version"
dl >/dev/null || true; hu schedule >/dev/null || true
for p in handtop handtop-desktop libavcodec61; do
  chroot "$ROOTFS" dpkg --unpack "$(ls "$ROOTFS$S"/cache/${p}_*.deb | sed "s|^$ROOTFS||")" >/dev/null 2>&1 || true
done
[ -n "$(chroot "$ROOTFS" dpkg --audit)" ] && ok "half-installed state made" || bad "could not make a half-installed state"
hu apply || true
expect_versions "$V2" "$FF2"
clean_dpkg "after resuming"

echo "== a cut after the result was written: the next maintenance boot only finishes"
fat_on; printf 'handtop=previous\n' > "$ROOTFS/boot/firmware/recovery.txt"; hr >/dev/null || true; fat_off
pid=$(hu status | js 'd["plan"]')
python3 - "$ROOTFS$S/last-result.json" "$pid" <<'P'
import json, sys; json.dump({"plan": sys.argv[2], "ok": True, "final": True, "action": "reboot", "message": "test"}, open(sys.argv[1], "w"))
P
out=$(hu apply || true)
expect_versions "$V2" "$FF2"
no_marker && [ ! -e "$ROOTFS$S/plan.json" ] && ok "finished without installing again" || bad "re-ran after a recorded result"

echo "== the maintenance boot was stopped (time-out): the next normal boot reports it"
printf '{"plan": "x", "attempt": 1, "started": 0}' > "$ROOTFS$S/in-progress.json"
mv "$ROOTFS/usr/sbin/policy-rc.d" "$ROOTFS/usr/sbin/policy-rc.d.handtop-saved"
printf '#!/bin/sh\n# handtop-update: no service starts during the maintenance boot\nexit 101\n' > "$ROOTFS/usr/sbin/policy-rc.d"
hu boot-check || true
[ "$(hu status | js 'd["last_result"].get("interrupted")')" = True ] && ok "interruption reported" || bad "not reported"
policy_back && ok "stale policy-rc.d removed, build's put back" || bad "policy-rc.d after boot-check"
[ -x "$ROOTFS$S/lkg/handtop-update" ] && [ -x "$ROOTFS$S/lkg/handtop-recovery" ] && ok "working copies kept" || bad "no lkg copies"

echo "== back to release 1 for the next tests"
fat_on; printf 'handtop=previous\n' > "$ROOTFS/boot/firmware/recovery.txt"
hr >/dev/null || true; fat_off; hu apply >/dev/null || true
expect_versions "$V1" "$FF1"

echo "== a broken handtop-recovery: handtop-run uses the working copy"
cp -a "$ROOTFS/usr/local/sbin/handtop-recovery" "$WORK/hr.orig"
echo "this is not python" > "$ROOTFS/usr/local/sbin/handtop-recovery"
err=$(chroot "$ROOTFS" /usr/local/sbin/handtop-run handtop-recovery 2>&1 >/dev/null || true)
grep -q "last copy that worked" <<<"$err" && ok "fallback to the last working copy" || bad "no fallback: $err"
cp -a "$WORK/hr.orig" "$ROOTFS/usr/local/sbin/handtop-recovery"

echo "== someone else's /system-update"
ln -s /var/lib/other-updater "$ROOTFS/system-update"
dl >/dev/null || true
out=$(hu schedule || true); grep -q "another offline update" <<<"$out" && ok "schedule refuses" || bad "schedule: $out"
hu apply >/dev/null 2>&1 || true
[ "$(readlink "$ROOTFS/system-update")" = /var/lib/other-updater ] && ok "apply leaves it alone" || bad "foreign marker touched"
rm "$ROOTFS/system-update"; hu cancel >/dev/null || true

echo "== battery readings (fake sysfs)"
FS="$ROOTFS/tmp/fakesys/class/power_supply"; mkdir -p "$FS/battery" "$FS/axp20x-usb"
echo 0 > "$FS/axp20x-usb/online"
dl >/dev/null || true
for c in 30 abc 50; do
  echo "$c" > "$FS/battery/capacity"
  out=$(HU_ENV=HANDTOP_UPDATE_SYSFS=/tmp/fakesys hu schedule || true)
  case "$c" in
    50) [ "$(echo "$out" | js 'd["ok"]')" = True ] && ok "battery 50%: scheduled" || bad "battery 50%: $out" ;;
    *)  [ "$(echo "$out" | js 'd["ok"]')" = False ] && ok "battery '$c': refused" || bad "battery '$c': $out" ;;
  esac
done
hu cancel >/dev/null || true

echo "== a different KERNEL: Handtop's part waits for a new image, Debian's would still come"
cp -a "$ROOTFS/etc/handtop/boot-abi" "$WORK/boot-abi.orig"
sed -i 's/^kernel_sha256=.*/kernel_sha256=0000/' "$ROOTFS/etc/handtop/boot-abi"
out=$(hu check || true)
[ "$(echo "$out" | js 'd["handtop_held"] and len(d["new_image_needed"]) > 0')" = True ] && ok "new image needed; Handtop held back" || bad "new image: $out"
[ "$(echo "$out" | js 'len([u for u in d["updates"] if u["name"].startswith("handtop")])')" = 0 ] && ok "no Handtop package planned" || bad "Handtop still planned"
cp -a "$WORK/boot-abi.orig" "$ROOTFS/etc/handtop/boot-abi"

echo "== channel switching cancels a downloaded update"
dl >/dev/null || true
out=$(hu channel testing || true)
[ "$(echo "$out" | js 'd["cancelled_update"]')" = True ] && [ ! -e "$ROOTFS$S/plan.json" ] && ok "testing: downloaded update cancelled" || bad "channel: $out"
grep -q "^Suites: trixie-testing" "$ROOTFS/etc/apt/sources.list.d/handtop-testing.sources" && ok "testing: own sources file" || bad "no testing sources file"
[ "$(md5sum < "$ROOTFS$SRCF" | cut -d' ' -f1)" = "$edited" ] && ok "handtop.sources untouched" || bad "handtop.sources changed"
hu channel stable >/dev/null || true
[ ! -e "$ROOTFS/etc/apt/sources.list.d/handtop-testing.sources" ] && ok "stable: file removed" || bad "testing file left"

echo "== then a normal update still works (install and power off)"
dl >/dev/null || true; hu schedule poweroff >/dev/null || true
[ "$(hu status | js 'd["after"]')" = poweroff ] && ok "power off chosen" || bad "after: $(hu status | js 'd["after"]')"
out=$(hu apply || true); echo "$out" | tail -3
grep -q "would poweroff" <<<"$out" && ok "powers off after the install" || bad "did not power off"
expect_versions "$V2" "$FF2"
clean_dpkg "final"

echo; echo "update-test: $pass passed, $fail failed"
[ "$fail" = 0 ]
