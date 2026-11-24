#!/bin/bash
# Test archive for trying updates on a handheld: two releases built from this checkout, served from
# the build server over HTTP on the LAN (docs/services/update.md, "Device test").
#   release 1: the packages 09b builds (install it on the card first)
#   release 2: newer, one changed script, release notes from a test changelog (the update to try)
# Output in work/device-archive: r1/ and r2/ (flat, Origin Handtop, suite trixie-stable) and the link
# current -> r1. Serve it unprivileged and switch releases with the link:
#   python3 -m http.server 8088 --directory work/device-archive
#   ln -sfn r2 work/device-archive/current
# The card's source (Trusted: yes, test only): URIs: http://<server>:8088/current/  Suites: ./
#
#   sudo SRC_WORK=/path/to/finished/work tools/update-device-archive.sh   (in a second checkout or worktree)
set -euo pipefail
source "$(dirname "$(realpath "$0")")/../build/config.sh"
source "$TOP/build/lib/chroot.sh"
SRC_WORK="$(realpath "${SRC_WORK:?SRC_WORK: the work directory of a finished build}")"
[ "$(realpath -m "$WORK")" != "$SRC_WORK" ] || die "WORK must be a scratch directory, not SRC_WORK"
[ -d "$SRC_WORK/rootfs/usr" ] || die "no finished rootfs in $SRC_WORK"
ls "$SRC_WORK"/pkg-ffmpeg/*.deb >/dev/null || die "no FFmpeg packages in $SRC_WORK/pkg-ffmpeg"
trap chroot_umount EXIT
mkdir -p "$WORK"
assert_no_mounts "$SRC_WORK/rootfs" "$ROOTFS"
rsync -aHAXx --delete --numeric-ids "$SRC_WORK/rootfs/" "$ROOTFS/"
ln -sfn "$SRC_WORK/rocknix" "$ROCKNIX_EX"
rsync -a --chown=root:root --chmod=D755,F644 "$TOP/overlay/" "$ROOTFS/"
chmod 755 "$ROOTFS"/usr/local/sbin/* "$ROOTFS"/usr/local/bin/*
chmod 0440 "$ROOTFS"/etc/sudoers.d/rg35xxh-*
# The steps that install from src/ and changed since the update system started (the finished build
# may be older than this checkout): the theme system and its icons, and the Update app.
"$TOP/build/07d-theme.sh" >/dev/null
"$TOP/build/07f-update-app.sh" >/dev/null

echo "== release 1"
"$TOP/build/09b-packages.sh"
V1=$(chroot "$ROOTFS" dpkg-query -W -f '${Version}' handtop)
# The listing first: grep -q stopping early would break dpkg-deb's pipe and fail under pipefail.
DESK=$(dpkg-deb -c "$WORK"/pkg/handtop-desktop_*.deb)
grep -q '/usr/local/lib/rg35xxh-update/handtop_update/app.py' <<< "$DESK" || die "handtop-desktop has no Update app"

echo "== release 2"
V2="$V1+t2"
echo "# device test release 2" >> "$ROOTFS/usr/local/sbin/rg35xxh-bootlog"
P2="$WORK/pkg2"; [ -e "$P2" ] && safe_rm -r "$P2"
HANDTOP_FFMPEG_VERSION="$FFMPEG_HANDTOP_VERSION" python3 "$TOP/build/pkg/build-debs.py" "$ROOTFS" "$P2" "$V2"
KSHA=$(sed -n 's/^kernel_sha256=//p' "$ROOTFS/etc/handtop/boot-abi")
CL="$WORK/test-changelog.md"
cat > "$CL" <<'C'
# Handtop changelog

## v0.5.0-test
A test release for the update system.

- **New: updates without reflashing**, with an Update app.
- **Fixed: nothing really**; one script changed.
- A plain line without a bold lead.
C
HANDTOP_RELEASE_VERSION=0.5.0-test HANDTOP_CHANGELOG="$CL" \
  python3 "$TOP/build/pkg/build-platform-debs.py" "$ROOTFS" "$P2" "$V2" "$KVER" "$KSHA"

A="$WORK/device-archive"; [ -e "$A" ] && safe_rm -r "$A"; mkdir -p "$A/r1" "$A/r2"
cp "$WORK"/pkg/*.deb "$SRC_WORK"/pkg-ffmpeg/*.deb "$A/r1/"
cp "$A"/r1/*.deb "$P2"/*.deb "$A/r2/"
for r in r1 r2; do
  sleep 1.1   # r2's index must be newer than r1's: apt asks "modified since?" and the server compares seconds
  (cd "$A/$r" && dpkg-scanpackages -m . /dev/null 2>/dev/null > Packages &&
   apt-ftparchive -o APT::FTPArchive::Release::Origin=Handtop -o APT::FTPArchive::Release::Label=Handtop \
     -o APT::FTPArchive::Release::Suite=trixie-stable release . > ../Release.tmp && mv ../Release.tmp Release)
done
ln -sfn r1 "$A/current"
[ -n "${SUDO_USER:-}" ] && chown -R "$SUDO_USER:" "$A"
echo "release 1: $V1"
echo "release 2: $V2"
ls "$A/r2" | wc -l
