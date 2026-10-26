#!/bin/bash
# Cross-compile the animated boot screen (src/bootsplash, plain C, libc only) for arm64 on the build
# host, using the rootfs as sysroot. Needs gcc-aarch64-linux-gnu on the host (as 07b-osd.sh).
set -euo pipefail
source "$(dirname "$0")/config.sh"
source "$(dirname "$0")/lib/chroot.sh"
trap chroot_umount EXIT

DEV_PKGS="libc6-dev"   # headers + crt files for linking
OUT="$WORK/src/bootsplash"

chroot_mount
in_chroot "apt-get update -qq && apt-get install -y -qq --no-install-recommends $DEV_PKGS"
chroot_umount

[ -e "$OUT" ] && safe_rm -r "$OUT"
mkdir -p "$OUT"
rsync -a --exclude rg35xxh-bootsplash "$TOP/src/bootsplash/" "$OUT/"
make -C "$OUT" -s CC=aarch64-linux-gnu-gcc SYSROOT="$ROOTFS" LDFLAGS=-s
file "$OUT/rg35xxh-bootsplash" | grep -q 'ARM aarch64' || { echo "Build did not produce an arm64 binary" >&2; exit 1; }
install -Dm755 "$OUT/rg35xxh-bootsplash" "$ROOTFS/usr/local/bin/rg35xxh-bootsplash"

chroot_mount
in_chroot "apt-get purge -y -qq $DEV_PKGS && apt-get autoremove -y -qq --purge && apt-get clean"
safe_rm -r "$ROOTFS"/var/lib/apt/lists/*
mkdir -p "$ROOTFS/var/lib/apt/lists/partial"
in_chroot "ldd /usr/local/bin/rg35xxh-bootsplash | grep -q 'not found' && exit 1 || true"
echo "rg35xxh-bootsplash installed."
