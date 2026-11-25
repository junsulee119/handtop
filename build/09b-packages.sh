#!/bin/bash
# Handtop's own files become packages (updates without reflashing, project doc update-system.md).
# build/pkg/build-debs.py copies every file classes.txt gives to handtop-core / -desktop / -video /
# -keyring out
# of the finished rootfs into .deb files (work/pkg/), and they are installed straight back with
# dpkg: no file changes, but dpkg now owns them, so later versions can replace them on a card.
# The audit then checks that no file of those packages is left unowned.
set -euo pipefail
source "$(dirname "$(realpath "$0")")/config.sh"
source "$(dirname "$(realpath "$0")")/lib/chroot.sh"
trap chroot_umount EXIT
assert_rootfs

# Version: the release itself when HEAD is its tag, otherwise a dev version that sorts after the
# last release and before the next one (0.4.1+202611181930.gabc1234).
# HANDTOP_RELEASE=1 (release builds, docs/release-checklist.md): HEAD must carry the tag, so the tested
# packages are the released ones; a dev version (0.5.0+...) sorts above 0.5.0 (review 2026-11-26 #81).
if git -C "$TOP" describe --exact-match --tags HEAD 2>/dev/null | grep -qx "v$RELEASE_VERSION"; then
  PKG_VERSION="$RELEASE_VERSION"
elif [ "${HANDTOP_RELEASE:-0}" = 1 ]; then
  die "HANDTOP_RELEASE=1 but HEAD is not tagged v$RELEASE_VERSION: tag the release commit first (git tag v$RELEASE_VERSION)"
else
  sha=$(git -C "$TOP" rev-parse --short=7 HEAD 2>/dev/null || echo nogit)
  PKG_VERSION="${RELEASE_VERSION}+$(date -u +%Y%m%d%H%M).g$sha"
fi
PKG_OUT="$WORK/pkg"
[ -d "$PKG_OUT" ] && safe_rm -r "$PKG_OUT"
HANDTOP_FFMPEG_VERSION="$FFMPEG_HANDTOP_VERSION" python3 "$TOP/build/pkg/build-debs.py" "$ROOTFS" "$PKG_OUT" "$PKG_VERSION"
# Kernel modules (refuse a card with another kernel) and the metapackages.
[ -f "$ROOTFS/etc/handtop/boot-abi" ] || die "no /etc/handtop/boot-abi (06-hardware.sh writes it)"
KSHA=$(sha256sum "$ROCKNIX_EX/boot/KERNEL" | cut -d' ' -f1)
grep -qx "kernel_sha256=$KSHA" "$ROOTFS/etc/handtop/boot-abi" || die "/etc/handtop/boot-abi does not name this build's KERNEL ($KSHA)"
HANDTOP_RELEASE_VERSION="$RELEASE_VERSION" python3 "$TOP/build/pkg/build-platform-debs.py" "$ROOTFS" "$PKG_OUT" "$PKG_VERSION" "$KVER" "$KSHA"

for d in "$PKG_OUT"/handtop*.deb; do
  [ "$(dpkg-deb -f "$d" Version)" = "$PKG_VERSION" ] || die "$d is not version $PKG_VERSION"
done
# With the image: exactly which packages it was built from (Handtop's and Handtop's FFmpeg build), as
# "package version architecture sha256"; tools/apt/client-test.sh checks the published ones against it.
FFMPEG_PKGS="${HANDTOP_FFMPEG_PKGS:-$WORK/pkg-ffmpeg}"   # the test harnesses use their source build's
ls "$FFMPEG_PKGS"/*.deb >/dev/null 2>&1 || die "no FFmpeg packages in $FFMPEG_PKGS (04c builds them)"
for d in "$PKG_OUT"/*.deb "$FFMPEG_PKGS"/*.deb; do
  echo "$(dpkg-deb -f "$d" Package Version Architecture | cut -d' ' -f2 | xargs) $(sha256sum < "$d" | cut -d' ' -f1)"
done > "$PKG_OUT/packages.txt"
echo "packages $PKG_VERSION: $PKG_OUT/packages.txt ($(wc -l < "$PKG_OUT/packages.txt") packages)"
chroot_mount
mkdir -p "$ROOTFS/tmp/handtop-pkg"
cp "$PKG_OUT"/handtop*.deb "$ROOTFS/tmp/handtop-pkg/"
# Debian's own copy of each file Handtop diverts (diversions.txt) goes next to it as <path>.debian,
# from the owner's package at the installed version: the overlay has already replaced the file, and
# the preinst only saves the copy on disk when it is still Debian's (review 2026-11-19 #8). 07c has
# emptied apt's lists, so they are fetched again here and emptied afterwards (review 2026-11-26 #62);
# the version installed earlier in this build is still on the mirror unless Debian published a point
# release during the build (then the build stops: run it again).
in_chroot "apt-get update -qq" || die "apt-get update failed (needed for Debian's copies of the diverted files)"
grep -v '^[[:space:]]*#' "$TOP/build/pkg/diversions.txt" | while read -r _pkg path owner; do
  [ -n "$path" ] || continue
  dl="$ROOTFS/tmp/handtop-pkg/debian-$owner"
  [ -d "$dl" ] && safe_rm -r "$dl"
  mkdir -p "$dl"
  ver=$(in_chroot "dpkg-query -W -f='\${Version}' $owner") || die "$owner is not installed"
  in_chroot "cd /tmp/handtop-pkg/debian-$owner && apt-get download -qq $owner=$ver" ||
    die "can't download $owner $ver for Debian's copy of $path (a Debian point release during the build? build again)"
  debs=("$dl"/*.deb); [ "${#debs[@]}" = 1 ] && [ -f "${debs[0]}" ] || die "expected one $owner package in $dl"
  [ "$(dpkg-deb -f "${debs[0]}" Package Version | xargs)" = "Package: $owner Version: $ver" ] ||
    die "${debs[0]} is not $owner $ver"
  mkdir -p "$dl/x"
  dpkg-deb --fsys-tarfile "${debs[0]}" | tar -x -C "$dl/x" ".$path" || die "no $path in ${debs[0]}"
  want=$(in_chroot "dpkg-query -W -f='\${Conffiles}\n' $owner" | awk -v p="$path" '$1 == p { print $2 }')
  [ -n "$want" ] && [ "$(md5sum < "$dl/x$path" | cut -d' ' -f1)" = "$want" ] ||
    die "$path in ${debs[0]} is not the file dpkg recorded for $owner"
  cp -p "$dl/x$path" "$ROOTFS$path.debian.tmp" && sync -f "$ROOTFS$path.debian.tmp" &&
    mv -f "$ROOTFS$path.debian.tmp" "$ROOTFS$path.debian" || die "can't write $path.debian"
  safe_rm -r "$dl"
done
safe_rm -r "$ROOTFS"/var/lib/apt/lists/*
mkdir -p "$ROOTFS/var/lib/apt/lists/partial"
in_chroot "dpkg -i --force-confdef --force-confold /tmp/handtop-pkg/handtop*.deb"
# Each diversion: Handtop's package, to <path>.debian, and that copy is Debian's file.
grep -v '^[[:space:]]*#' "$TOP/build/pkg/diversions.txt" | while read -r pkg path owner; do
  [ -n "$path" ] || continue
  [ "$(in_chroot "dpkg-divert --list $path")" = "diversion of $path to $path.debian by $pkg" ] ||
    die "$path: not diverted by $pkg to $path.debian"
  want=$(in_chroot "dpkg-query -W -f='\${Conffiles}\n' $owner" | awk -v p="$path" '$1 == p { print $2 }')
  [ "$(md5sum < "$ROOTFS$path.debian" | cut -d' ' -f1)" = "$want" ] || die "$path.debian is not $owner's file"
done
safe_rm -r "$ROOTFS/tmp/handtop-pkg"
# handtop-keyring's pin now keeps Debian's FFmpeg out; 04c's holds would keep FFmpeg updates back.
# (Not in its postinst: apt-mark can't run while dpkg holds its lock. Cards: handtop-update.)
in_chroot "apt-mark unhold ffmpeg libavcodec61 libavdevice61 libavfilter10 libavformat61 libavutil59 libpostproc58 libswresample5 libswscale8 >/dev/null"
[ -z "$(in_chroot "apt-mark showhold")" ] || die "packages still held: $(in_chroot "apt-mark showhold" | xargs)"
in_chroot "dpkg-query -W 'handtop*'" | grep -q '^handtop\s' || die "the handtop metapackage is not installed"
in_chroot "dpkg-query -W 'handtop*'"
while read -r m _; do
  case "$m" in ""|\#*) continue ;; esac
  in_chroot "dpkg -S /usr/lib/modules/$KVER/$m" | grep -q "^handtop-modules-h700-$KVER:" || die "$m is not owned by the modules package"
done < "$TOP/build/pkg/modules.txt"

# Nothing classed as Handtop's may stay unowned (FFmpeg's files belong to its packages from 04c).
left=$(for c in handtop-core handtop-desktop handtop-video handtop-keyring; do python3 "$TOP/build/pkg/audit-unowned.py" "$ROOTFS" --list "$c"; done)
[ -z "$left" ] || die "files still not owned by a package: $left"
echo "Handtop packages $PKG_VERSION built in $PKG_OUT and installed."
