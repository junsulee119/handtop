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
if git -C "$TOP" describe --exact-match --tags HEAD 2>/dev/null | grep -qx "v$RELEASE_VERSION"; then
  PKG_VERSION="$RELEASE_VERSION"
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

chroot_mount
mkdir -p "$ROOTFS/tmp/handtop-pkg"
cp "$PKG_OUT"/handtop*.deb "$ROOTFS/tmp/handtop-pkg/"
# Debian's own copy of each file Handtop diverts (diversions.txt) goes next to it as <path>.debian,
# from the owner's package at the installed version: the overlay has already replaced the file, and
# the preinst only saves the copy on disk when it is still Debian's (review 2026-11-19 #8).
mkdir -p "$ROOTFS/tmp/handtop-pkg/debian"
grep -v '^[[:space:]]*#' "$TOP/build/pkg/diversions.txt" | while read -r _pkg path owner; do
  [ -n "$path" ] || continue
  in_chroot "cd /tmp/handtop-pkg/debian && apt-get download -qq $owner=\$(dpkg-query -W -f='\${Version}' $owner)" ||
    die "can't download $owner for Debian's copy of $path"
  deb=$(ls "$ROOTFS/tmp/handtop-pkg/debian/${owner}_"*.deb)
  dpkg-deb --fsys-tarfile "$deb" | tar -xO ".$path" > "$ROOTFS$path.debian" || die "no $path in $deb"
  want=$(in_chroot "dpkg-query -W -f='\${Conffiles}\n' $owner" | awk -v p="$path" '$1 == p { print $2 }')
  [ "$(md5sum < "$ROOTFS$path.debian" | cut -d' ' -f1)" = "$want" ] || die "$path.debian is not the file dpkg recorded for $owner"
  chmod 644 "$ROOTFS$path.debian"
  safe_rm "$deb"
done
in_chroot "dpkg -i --force-confdef --force-confold /tmp/handtop-pkg/handtop*.deb"
for path in $(grep -v '^[[:space:]]*#' "$TOP/build/pkg/diversions.txt" | awk '{print $2}'); do
  [ -f "$ROOTFS$path.debian" ] && in_chroot "dpkg-divert --listpackage $path" | grep -q '^handtop-' ||
    die "$path: no Handtop diversion with Debian's copy next to it"
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
