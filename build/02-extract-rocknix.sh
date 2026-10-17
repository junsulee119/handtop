#!/bin/bash
# Extract the hardware layer from the ROCKNIX image into $ROCKNIX_EX:
#   boot/        KERNEL, extlinux.conf, device_trees/, overlays/
#   bootloader/  u-boot-sunxi-with-spl.bin (DDR4 or DDR3, see RAM_TYPE), bl31.bin
#   modules/     lib/modules/<kver>
#   firmware/    lib/firmware (Wi-Fi/BT, panels, regulatory.db)
#   quirks/      ROCKNIX H700 platform quirk scripts (reference for porting)
#   system/      selected reference files (alsa, udev, controller DB)
set -euo pipefail
source "$(dirname "$0")/config.sh"

IMG_GZ="$ROCKNIX_DL/$ROCKNIX_IMAGE"
TMP="$WORK/tmp-extract"
for d in "$ROCKNIX_EX" "$TMP"; do [ -e "$d" ] && safe_rm -r "$d"; done
mkdir -p "$ROCKNIX_EX"/{boot,bootloader,modules,firmware,quirks,system} "$TMP"

echo "Decompressing image..."
gunzip -c "$IMG_GZ" > "$TMP/rocknix.img"

# Partition 1 (FAT boot) offset from the partition table.
P1_START=$(sfdisk -d "$TMP/rocknix.img" | awk -F'[=,]' '/img1/ {gsub(/ /,"",$2); print $2}')
FAT="$TMP/rocknix.img@@$((P1_START * 512))"
export MTOOLS_SKIP_CHECK=1

echo "Copying boot files..."
mcopy -s -n -i "$FAT" ::/KERNEL ::/extlinux ::/device_trees ::/overlays "$ROCKNIX_EX/boot/"
mcopy -n -i "$FAT" ::/SYSTEM "$TMP/SYSTEM"

echo "Extracting from SYSTEM squashfs..."
unsquashfs -q -n -d "$TMP/sys" "$TMP/SYSTEM" \
  usr/share/bootloader \
  usr/lib/kernel-overlays/base/lib \
  usr/lib/autostart/quirks/platforms/H700 \
  usr/share/alsa usr/lib/udev/rules.d etc/asound.conf \
  usr/config/SDL-GameControllerDB \
  usr/lib/autostart/common/050-audio usr/lib/autostart/common/020-rumble \
  usr/lib/autostart/common/055-hdmi-check usr/bin/rocknix-fake-suspend >/dev/null || true

cp "$TMP/sys/usr/share/bootloader/H700_${RAM_TYPE}_u-boot-sunxi-with-spl.bin" "$ROCKNIX_EX/bootloader/u-boot-sunxi-with-spl.bin"
cp "$TMP/sys/usr/share/bootloader/bl31.bin" "$ROCKNIX_EX/bootloader/" 2>/dev/null || true
cp -a "$TMP/sys/usr/lib/kernel-overlays/base/lib/modules/." "$ROCKNIX_EX/modules/"
cp -a "$TMP/sys/usr/lib/kernel-overlays/base/lib/firmware/." "$ROCKNIX_EX/firmware/"
cp -a "$TMP/sys/usr/lib/autostart/quirks/platforms/H700/." "$ROCKNIX_EX/quirks/"
for p in usr/share/alsa usr/lib/udev/rules.d etc/asound.conf usr/config/SDL-GameControllerDB \
         usr/lib/autostart/common usr/bin/rocknix-fake-suspend; do
  [ -e "$TMP/sys/$p" ] && mkdir -p "$ROCKNIX_EX/system/$(dirname "$p")" && cp -a "$TMP/sys/$p" "$ROCKNIX_EX/system/$p"
done

# Sanity check: the bootloader file must match what the image has at 8 KiB.
BL="$ROCKNIX_EX/bootloader/u-boot-sunxi-with-spl.bin"
if cmp -s "$BL" <(dd if="$TMP/rocknix.img" bs=1024 skip=8 count=$(( ($(stat -c%s "$BL") + 1023) / 1024 )) 2>/dev/null | head -c "$(stat -c%s "$BL")"); then
  echo "Bootloader matches image at 8 KiB offset."
else
  echo "WARNING: bootloader file differs from image's 8 KiB area; saving raw copy." >&2
  dd if="$TMP/rocknix.img" of="$ROCKNIX_EX/bootloader/raw-8k-16m.bin" bs=1024 skip=8 count=$((16*1024-8)) 2>/dev/null
fi

KVER=$(ls "$ROCKNIX_EX/modules")
echo "Kernel modules version: $KVER"
safe_rm -r "$TMP"
echo "Done: $ROCKNIX_EX"
