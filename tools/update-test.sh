#!/bin/bash
# Test the update worker (handtop-update) in a chroot copy of a finished build's root filesystem:
# check, download, schedule, apply from a local test archive with a newer build of every Handtop
# package, then recovery.txt (joypad=previous/current, handtop=previous), a broken download and
# the attempt limit. No restart happens (HANDTOP_UPDATE_NO_POWER_ACTION). The maintenance boot
# itself (systemd, console) is tested in QEMU and on the device (docs/services/update.md).
#
#   sudo SRC_WORK=/path/to/finished/work tools/update-test.sh   (in a second checkout or worktree:
#   its own work/ is the scratch copy; SRC_WORK is only read)
set -euo pipefail
source "$(dirname "$(realpath "$0")")/../build/config.sh"
source "$TOP/build/lib/chroot.sh"
SRC_WORK="$(realpath "${SRC_WORK:?SRC_WORK: the work directory of a finished build}")"
[ "$(realpath -m "$WORK")" != "$SRC_WORK" ] || die "WORK must be a scratch directory, not SRC_WORK"
[ -d "$SRC_WORK/rootfs/usr" ] || die "no finished rootfs in $SRC_WORK"
trap chroot_umount EXIT
mkdir -p "$WORK"
echo "== copy of $SRC_WORK/rootfs"
rsync -aHAX --delete --numeric-ids "$SRC_WORK/rootfs/" "$ROOTFS/"
ln -sfn "$SRC_WORK/rocknix" "$ROCKNIX_EX"
# What 05 does with the overlay (the rootfs may be older than this checkout).
rsync -a --chown=root:root --chmod=D755,F644 "$TOP/overlay/" "$ROOTFS/"
chmod 755 "$ROOTFS"/usr/local/sbin/* "$ROOTFS"/usr/local/bin/*
chmod 0440 "$ROOTFS"/etc/sudoers.d/rg35xxh-*

echo "== release 1: the packages 09b builds and installs"
"$TOP/build/09b-packages.sh"
V1=$(chroot "$ROOTFS" dpkg-query -W -f '${Version}' handtop)

echo "== release 2: same files plus one changed script, newer version"
F=/usr/local/sbin/rg35xxh-bootlog
cp -a "$ROOTFS$F" "$WORK/bootlog.orig"
echo "# update-test release 2" >> "$ROOTFS$F"
V2="$V1+t2"
P2="$WORK/pkg2"; [ -e "$P2" ] && safe_rm -r "$P2"
HANDTOP_FFMPEG_VERSION="$FFMPEG_HANDTOP_VERSION" python3 "$TOP/build/pkg/build-debs.py" "$ROOTFS" "$P2" "$V2"
KSHA=$(sed -n 's/^kernel_sha256=//p' "$ROOTFS/etc/handtop/boot-abi")
python3 "$TOP/build/pkg/build-platform-debs.py" "$ROOTFS" "$P2" "$V2" "$KVER" "$KSHA"
cp -a "$WORK/bootlog.orig" "$ROOTFS$F"          # the card still has release 1
# The test archive goes into the rootfs only now: build-debs.py would refuse its files.
R="$ROOTFS/srv/handtop-test"; [ -e "$R" ] && safe_rm -r "$R"; mkdir -p "$R"
cp "$WORK"/pkg/*.deb "$P2"/*.deb "$R/"
(cd "$R" && dpkg-scanpackages -m . /dev/null > Packages 2>/dev/null &&
  apt-ftparchive -o APT::FTPArchive::Release::Origin=Handtop -o APT::FTPArchive::Release::Label=Handtop \
    -o APT::FTPArchive::Release::Suite=trixie-stable release . > "$WORK/Release" && mv "$WORK/Release" Release)

# Offline: only the test archive (flat, trusted; copy: so apt fills its cache as with https) as the Handtop source; Debian's sources off.
mkdir -p "$WORK/sources-off"
mv "$ROOTFS"/etc/apt/sources.list "$ROOTFS"/etc/apt/sources.list.d/*.list "$WORK/sources-off/" 2>/dev/null || true
printf 'Types: deb\nURIs: copy:/srv/handtop-test\nSuites: ./\nTrusted: yes\n' > "$ROOTFS/etc/apt/sources.list.d/handtop.sources"

chroot_mount
pass=0; fail=0
ok()   { echo "PASS: $*"; pass=$((pass+1)); }
bad()  { echo "FAIL: $*"; fail=$((fail+1)); }
hu()   { chroot "$ROOTFS" env HANDTOP_UPDATE_NO_POWER_ACTION=1 /usr/local/sbin/handtop-update "$@"; }
ver()  { chroot "$ROOTFS" dpkg-query -W -f '${Version}' "$1"; }
js()   { python3 -c "import json,sys
try:
    d=json.load(sys.stdin); print($1)
except Exception as e:
    print('ERR', e)"; }
expect_versions() {
  local want=$1 p v
  for p in handtop handtop-core handtop-desktop handtop-video handtop-keyring handtop-platform-h700 "handtop-modules-h700-$KVER"; do
    v=$(ver "$p"); [ "$v" = "$want" ] || { bad "$p is $v, expected $want"; return; }
  done
  ok "all Handtop packages at $want"
}
clean_dpkg() {
  [ -z "$(chroot "$ROOTFS" dpkg --audit)" ] && ok "dpkg --audit clean ($1)" || bad "dpkg --audit not clean ($1)"
  chroot "$ROOTFS" dpkg --verify handtop-core handtop-desktop handtop-video >/dev/null &&
    ok "dpkg --verify clean ($1)" || bad "dpkg --verify reports changes ($1)"
}

echo "== FFmpeg holds released (09b)"
[ -z "$(chroot "$ROOTFS" apt-mark showhold)" ] && ok "no holds left" || bad "holds: $(chroot "$ROOTFS" apt-mark showhold | xargs)"

echo "== check"
out=$(hu check || true); echo "$out" | head -40
[ "$(echo "$out" | js 'len(d["handtop"])')" = 7 ] && ok "check lists 7 Handtop updates" || bad "check: $(echo "$out" | js 'd.get("handtop")')"
echo "== download"
out=$(hu download || true); echo "$out"
[ "$(echo "$out" | js 'd["ok"] and d["previous_kept"]')" = True ] && ok "download, previous release kept" || bad "download"
echo "== schedule"
out=$(hu schedule || true); echo "$out"
[ -L "$ROOTFS/system-update" ] && ok "marker set" || bad "no marker"
echo "== apply"
hu apply || true
expect_versions "$V2"
grep -q "update-test release 2" "$ROOTFS$F" && ok "changed file installed" || bad "changed file not installed"
[ ! -e "$ROOTFS/system-update" ] && ok "marker removed" || bad "marker still there"
[ -e "$ROOTFS/usr/sbin/policy-rc.d" ] && ! grep -q handtop-update "$ROOTFS/usr/sbin/policy-rc.d" && ok "policy-rc.d not left behind" || bad "policy-rc.d"
[ "$(hu status | js 'd["last_result"]["ok"]')" = True ] && ok "result recorded" || bad "result"
[ -f "$ROOTFS/var/lib/handtop/modules/rocknix-singleadc-joypad.ko.previous" ] && ok "previous joypad driver kept" || bad "no previous joypad driver"
clean_dpkg "after the update"

echo "== recovery.txt: joypad=previous, handtop=previous"
mkdir -p "$ROOTFS/boot/firmware"
printf 'joypad=previous\r\nhandtop=previous\r\n' > "$ROOTFS/boot/firmware/recovery.txt"
hu recovery || true
grep -q '^joypad=none' "$ROOTFS/boot/firmware/recovery.txt" && ok "recovery.txt reset" || bad "recovery.txt not reset"
modpath=$(chroot "$ROOTFS" modinfo -k "$KVER" -n rocknix-singleadc-joypad || true)
[[ "$modpath" == */updates/handtop-recovery/* ]] && ok "joypad override used ($modpath)" || bad "joypad resolves to $modpath"
[ -L "$ROOTFS/system-update" ] && [ "$(hu status | js 'd["kind"]')" = recovery ] && ok "recovery plan scheduled" || bad "no recovery plan"
hu apply || true
expect_versions "$V1"
grep -q "update-test release 2" "$ROOTFS$F" && bad "release 2 file still there" || ok "release 1 file back"
clean_dpkg "after going back"
printf 'joypad=current\n' > "$ROOTFS/boot/firmware/recovery.txt"
hu recovery || true
modpath=$(chroot "$ROOTFS" modinfo -k "$KVER" -n rocknix-singleadc-joypad || true)
[[ "$modpath" != */updates/* ]] && ok "joypad=current: packaged driver again" || bad "joypad still $modpath"
printf 'joypad=none\nhandtop=none\n' > "$ROOTFS/boot/firmware/recovery.txt"
hu recovery || true; [ ! -L "$ROOTFS/system-update" ] && ok "none: nothing done" || bad "none scheduled something"

echo "== a broken download: install fails, the card stays on release 1, the marker goes"
hu download || true; hu schedule || true
deb=$(ls "$ROOTFS"/var/lib/handtop-update/cache/handtop-desktop_*.deb || true)
[ -n "$deb" ] && truncate -s 4096 "$deb" || bad "nothing downloaded for the broken-download test"
hu apply || true
expect_versions "$V1"
[ ! -e "$ROOTFS/system-update" ] && ok "marker removed after the failure" || bad "marker left after failure"
[ "$(hu status | js 'd["last_result"]["ok"]')" = False ] && ok "failure recorded" || bad "failure not recorded"
clean_dpkg "after the failed install"

echo "== attempt limit"
hu cancel >/dev/null || true; hu download >/dev/null || true; hu schedule || true
echo 3 > "$ROOTFS/var/lib/handtop-update/attempts"
hu apply || true
expect_versions "$V1"
[ ! -e "$ROOTFS/system-update" ] && ok "gives up after 3 attempts" || bad "still scheduled after 3 attempts"

echo "== power cut during the install: some packages unpacked at the new version, the rest old"
hu download >/dev/null || true; hu schedule || true
for p in handtop handtop-desktop; do
  chroot "$ROOTFS" dpkg --unpack "$(ls "$ROOTFS"/var/lib/handtop-update/cache/${p}_*.deb | sed "s|^$ROOTFS||")" >/dev/null 2>&1 || true
done
[ -n "$(chroot "$ROOTFS" dpkg --audit)" ] && ok "half-installed state made" || bad "could not make a half-installed state"
hu apply || true
expect_versions "$V2"
clean_dpkg "after resuming"
echo "== back to release 1 for the next test (dpkg keeps the edited handtop.sources)"
SRCF=/etc/apt/sources.list.d/handtop.sources
edited=$(md5sum < "$ROOTFS$SRCF" | cut -d' ' -f1)
printf 'handtop=previous\n' > "$ROOTFS/boot/firmware/recovery.txt"
hu recovery || true; hu apply || true
expect_versions "$V1"
[ "$(md5sum < "$ROOTFS$SRCF" | cut -d' ' -f1)" = "$edited" ] && ok "edited handtop.sources kept" || bad "edited handtop.sources replaced"

echo "== then a normal update still works (install and power off)"
hu download >/dev/null || true; hu schedule poweroff || true
[ "$(hu status | js 'd["after"]')" = poweroff ] && ok "power off chosen" || bad "after: $(hu status | js 'd["after"]')"
out=$(hu apply || true); echo "$out"
echo "$out" | grep -q "would poweroff" && ok "powers off after the install" || bad "did not power off"
[ ! -e "$ROOTFS/var/lib/handtop-update/after" ] && ok "choice cleared" || bad "choice left behind"
expect_versions "$V2"
clean_dpkg "final"

echo "== channel"
hu channel testing >/dev/null || true
grep -q "^Suites: trixie-testing" "$ROOTFS/etc/apt/sources.list.d/handtop-testing.sources" 2>/dev/null && ok "testing: own sources file" || bad "no testing sources file"
[ "$(hu status | js 'd["channel"]')" = testing ] && ok "status says testing" || bad "status channel"
hu channel stable >/dev/null || true
[ ! -e "$ROOTFS/etc/apt/sources.list.d/handtop-testing.sources" ] && ok "stable: file removed" || bad "testing file left"

echo; echo "update-test: $pass passed, $fail failed"
[ "$fail" = 0 ]
