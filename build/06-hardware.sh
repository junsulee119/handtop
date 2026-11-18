#!/bin/bash
# Install the ROCKNIX hardware layer pieces that live in the root filesystem:
# kernel modules, firmware, and our ported hardware-init service.
set -euo pipefail
source "$(dirname "$0")/config.sh"
source "$(dirname "$0")/lib/chroot.sh"
trap chroot_umount EXIT

[ -d "$ROCKNIX_EX/modules/$KVER" ] || { echo "Run 02-extract-rocknix.sh first." >&2; exit 1; }

mkdir -p "$ROOTFS/usr/lib/modules" "$ROOTFS/usr/lib/firmware"
rsync -a --delete "$ROCKNIX_EX/modules/$KVER/" "$ROOTFS/usr/lib/modules/$KVER/"
rsync -a "$ROCKNIX_EX/firmware/" "$ROOTFS/usr/lib/firmware/"

# Which kernel this rootfs is built for. The kernel lives on the boot partition and changes only
# by reflashing; packages built for it (handtop-modules-*) refuse to install on a card whose
# kernel differs. ROCKNIX's DDR3 and DDR4 images carry the same KERNEL (checked 2026-11-18).
mkdir -p "$ROOTFS/etc/handtop"
{
  echo "platform=h700"
  echo "rocknix=$ROCKNIX_VERSION"
  echo "kernel=$KVER"
  echo "kernel_sha256=$(sha256sum "$ROCKNIX_EX/boot/KERNEL" | cut -d' ' -f1)"
} > "$ROOTFS/etc/handtop/boot-abi"
chmod 644 "$ROOTFS/etc/handtop/boot-abi"

chroot_mount
in_chroot "depmod -a $KVER"
in_chroot "systemctl enable rg35xxh-hwinit.service"
echo "Hardware layer installed: $(find "$ROOTFS/usr/lib/modules/$KVER" -name '*.ko*' | wc -l) modules."
