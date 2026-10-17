#!/bin/bash
# Assemble the flashable SD card image from the rootfs and the ROCKNIX boot files.
# No loop devices or mounts: partitions are built as files (mkfs.vfat + mtools, mkfs.ext4 -d)
# and written into the image at their offsets.
set -euo pipefail
source "$(dirname "$(realpath "$0")")/config.sh"
source "$(dirname "$(realpath "$0")")/lib/chroot.sh"
assert_rootfs
for m in proc sys dev run; do
  mountpoint -q "$ROOTFS/$m" && die "$ROOTFS/$m is still mounted"
done

VER="$(date +%Y%m%d)-$(git -C "$TOP" rev-parse --short HEAD 2>/dev/null || echo "v$RELEASE_VERSION")"
[ "$RAM_TYPE" != "DDR4" ] && VER="$VER-$RAM_TYPE"
OUT="$WORK/out"; mkdir -p "$OUT"
IMG="$OUT/$IMAGE_NAME-$VER.img"
P="$WORK/image-parts"; [ -e "$P" ] && safe_rm -r "$P"; mkdir -p "$P"

# --- per-device identity must not ship in the image
: > "$ROOTFS/etc/machine-id"                       # systemd generates one on first boot
for k in "$ROOTFS"/etc/ssh/ssh_host_*; do [ -e "$k" ] && safe_rm "$k"; done   # regenerated on first boot

# --- user home: fresh from /etc/skel (test runs in the build leave state behind)
H="$ROOTFS/home/$USER_NAME"
[ -e "$H" ] && safe_rm -r "$H"
cp -a "$ROOTFS/etc/skel" "$H"
mkdir -p "$H"/.cache "$H"/.config "$H"/.local/share "$H"/.local/state
chroot "$ROOTFS" chown -R "$USER_NAME:$USER_NAME" "/home/$USER_NAME"
chmod 700 "$H"

# --- sizes
ROOT_USED_MIB=$(du -smx "$ROOTFS" | cut -f1)
ROOT_SIZE_MIB=$(( (ROOT_USED_MIB * 125 / 100 + 300 + 63) / 64 * 64 ))   # +25 % +300 MiB headroom
TOTAL_MIB=$(( BOOT_START_MIB + BOOT_SIZE_MIB + ROOT_SIZE_MIB + 1 ))
echo "rootfs ${ROOT_USED_MIB} MiB -> root partition ${ROOT_SIZE_MIB} MiB, image ${TOTAL_MIB} MiB"

# --- boot partition (FAT32)
BOOTDIR="$P/boot"; mkdir -p "$BOOTDIR/extlinux" "$BOOTDIR/device_trees" "$BOOTDIR/logs"
cp "$ROCKNIX_EX/boot/KERNEL" "$BOOTDIR/KERNEL"
cp "$ROCKNIX_EX"/boot/device_trees/sun50i-h700-anbernic-rg35xx-h*.dtb "$BOOTDIR/device_trees/"
cp "$ROCKNIX_EX/boot/device_trees/$DEFAULT_DTB" "$BOOTDIR/dtb-rocknix.img"   # original, as fallback
# Add the video engine (hardware video decoding, docs/video-decode.md) to the ROCKNIX DTB.
dtc -q -@ -I dts -O dtb -o "$P/video-engine.dtbo" "$TOP/build/dts/rg35xxh-video-engine.dtso"
fdtoverlay -i "$BOOTDIR/dtb-rocknix.img" -o "$BOOTDIR/dtb.img" "$P/video-engine.dtbo"
PARTUUID_ROOT="$(printf '%08x' "$DISK_ID")-02"
# ROCKNIX's built-in initramfs has no /root directory, which the kernel needs to mount root=
# itself (error -2). rootfix.cpio only adds that directory; see docs/boot-method.md.
RF="$P/rootfix"; mkdir -m 0700 -p "$RF/root"
(cd "$RF" && echo root | cpio -o -H newc -R 0:0 --quiet) > "$BOOTDIR/rootfix.cpio"
cat > "$BOOTDIR/extlinux/extlinux.conf" <<X
LABEL rg35xxh
  LINUX /KERNEL
  INITRD /rootfix.cpio
  FDT /dtb.img
  APPEND root=PARTUUID=$PARTUUID_ROOT rootwait rootfstype=ext4 ro rdinit=/nonexistent console=ttyS0,115200 console=tty0 loglevel=4 cma=$CMA_SIZE
X
cp "$TOP/boot-files/wifi.txt" "$TOP/boot-files/README.txt" "$BOOTDIR/"
sed 's/$/\r/' "$TOP/overlay/etc/rg35xxh/input.conf" > "$BOOTDIR/rg35xxh-input.conf"
mkfs.vfat -F 32 -n "$BOOT_LABEL" -C "$P/boot.vfat" $(( BOOT_SIZE_MIB * 1024 )) >/dev/null
MTOOLS_SKIP_CHECK=1 mcopy -s -i "$P/boot.vfat" "$BOOTDIR"/* ::/

# --- root partition (ext4, populated directly from the rootfs directory)
mkfs.ext4 -q -F -L "$ROOT_LABEL" -d "$ROOTFS" -E root_owner=0:0 "$P/root.ext4" "${ROOT_SIZE_MIB}M"
e2fsck -fn "$P/root.ext4" >/dev/null

# --- assemble
truncate -s "${TOTAL_MIB}M" "$IMG.part"
sfdisk -q "$IMG.part" <<S
label: dos
label-id: $DISK_ID
start=$(( BOOT_START_MIB * 2048 )), size=$(( BOOT_SIZE_MIB * 2048 )), type=c, bootable
start=$(( (BOOT_START_MIB + BOOT_SIZE_MIB) * 2048 )), size=$(( ROOT_SIZE_MIB * 2048 )), type=83
S
dd if="$ROCKNIX_EX/bootloader/u-boot-sunxi-with-spl.bin" of="$IMG.part" bs=1024 seek=8 conv=notrunc status=none
dd if="$P/boot.vfat" of="$IMG.part" bs=1M seek="$BOOT_START_MIB" conv=notrunc,sparse status=none
dd if="$P/root.ext4" of="$IMG.part" bs=1M seek=$(( BOOT_START_MIB + BOOT_SIZE_MIB )) conv=notrunc,sparse status=none
mv "$IMG.part" "$IMG"
safe_rm -r "$P"

echo "Compressing..."
xz -T0 -6 -k -f "$IMG"
( cd "$OUT" && sha256sum "$(basename "$IMG").xz" > "$(basename "$IMG").xz.sha256" )
sfdisk -l "$IMG" | tail -3
ls -la "$OUT"
