#!/bin/bash
# Handtop's own files become packages (updates without reflashing, project doc update-system.md).
# build/pkg/build-debs.py copies every file classes.txt gives to handtop-core / handtop-desktop out
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
python3 "$TOP/build/pkg/build-debs.py" "$ROOTFS" "$PKG_OUT" "$PKG_VERSION"

chroot_mount
mkdir -p "$ROOTFS/tmp/handtop-pkg"
cp "$PKG_OUT"/handtop-*.deb "$ROOTFS/tmp/handtop-pkg/"
in_chroot "dpkg -i --force-confdef --force-confold /tmp/handtop-pkg/handtop-core_*.deb /tmp/handtop-pkg/handtop-desktop_*.deb"
safe_rm -r "$ROOTFS/tmp/handtop-pkg"
in_chroot "dpkg-query -W handtop-core handtop-desktop"

# Nothing of handtop-core / handtop-desktop may stay unowned.
left=$(python3 "$TOP/build/pkg/audit-unowned.py" "$ROOTFS" --list handtop-core; python3 "$TOP/build/pkg/audit-unowned.py" "$ROOTFS" --list handtop-desktop)
[ -z "$left" ] || die "files still not owned by a Handtop package: $left"
echo "Handtop packages $PKG_VERSION built in $PKG_OUT and installed."
