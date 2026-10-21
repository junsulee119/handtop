#!/bin/bash
# Cross-compile the volume / brightness pop-up (src/osd, plain C Wayland client) for arm64 on the
# build host, using the rootfs as sysroot. Needs: gcc-aarch64-linux-gnu, pkg-config and
# wayland-scanner (libwayland-bin) on the host.
set -euo pipefail
source "$(dirname "$0")/config.sh"
source "$(dirname "$0")/lib/chroot.sh"
trap chroot_umount EXIT

DEV_PKGS="libc6-dev libwayland-dev wayland-protocols"   # libc6-dev: headers + crt files for linking
OUT="$WORK/src/osd"

# Temporary build dependencies inside the rootfs (removed again at the end).
chroot_mount
in_chroot "apt-get update -qq && apt-get install -y -qq --no-install-recommends $DEV_PKGS"
chroot_umount

[ -e "$OUT" ] && safe_rm -r "$OUT"
mkdir -p "$OUT"
rsync -a --exclude gen --exclude rg35xxh-osd "$TOP/src/osd/" "$OUT/"
make -C "$OUT" -s CC=aarch64-linux-gnu-gcc SYSROOT="$ROOTFS" LDFLAGS=-s
file "$OUT/rg35xxh-osd" | grep -q 'ARM aarch64' || { echo "Build did not produce an arm64 binary" >&2; exit 1; }
install -Dm755 "$OUT/rg35xxh-osd" "$ROOTFS/usr/local/bin/rg35xxh-osd"

chroot_mount
in_chroot "apt-get purge -y -qq $DEV_PKGS && apt-get autoremove -y -qq --purge && apt-get clean"
safe_rm -r "$ROOTFS"/var/lib/apt/lists/*
mkdir -p "$ROOTFS/var/lib/apt/lists/partial"
in_chroot "ldd /usr/local/bin/rg35xxh-osd | grep -q 'not found' && exit 1 || true"
echo "rg35xxh-osd installed."
