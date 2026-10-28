#!/bin/bash
# Bluetooth LE keyboards, mice and gamepads: build the kernel's own uhid driver (uhid.ko), which
# ROCKNIX's kernel leaves out (# CONFIG_UHID is not set). BlueZ passes HID-over-GATT (HoG)
# devices to the kernel through /dev/uhid; without it every LE input device connects but no
# input device appears ("input-hog profile accept failed"). Classic Bluetooth HID uses hidp and
# was not affected. See docs/kernel.md.
#
# Needs the ROCKNIX kernel tree built by 06b-cedrus.sh (same tree, so symbol versions match).
# uhid.c is built unchanged, out of tree (ROCKNIX's .config stays as it is).
set -euo pipefail
source "$(dirname "$0")/config.sh"
source "$(dirname "$0")/lib/chroot.sh"
trap chroot_umount EXIT
assert_rootfs

K="$WORK/kernel"
T="$K/linux-$LINUX_VERSION-rocknix-$ROCKNIX_VERSION"
export ARCH=arm64 CROSS_COMPILE="$K/gcc15/bin/aarch64-none-linux-gnu-"
[ -f "$T/Module.symvers" ] || die "kernel tree $T not built: run 06b-cedrus.sh first"
[ -f "$K/rocknix.versions" ] || die "$K/rocknix.versions missing: run 06b-cedrus.sh first"
grep -q "^# CONFIG_UHID is not set" "$K/rocknix.config" \
  || die "ROCKNIX's kernel config changed for UHID: check whether uhid is now built in or a module"

M="$K/uhid"
mkdir -p "$M"
cp "$T/drivers/hid/uhid.c" "$M/uhid.c"
echo "obj-m := uhid.o" > "$M/Makefile"
make -C "$T" -s M="$M" modules
KO="$M/uhid.ko"

# Every imported symbol version that ROCKNIX's modules also use must match (as for the others);
# a mismatch in the rest would make the kernel refuse to load it, which the device test shows.
bad=$(/sbin/modprobe --dump-modversions "$KO" | awk 'NR==FNR{r[$2]=$1; next} ($2 in r) && r[$2]!=$1' "$K/rocknix.versions" -)
[ -z "$bad" ] || die "symbol version mismatch against the ROCKNIX kernel:\n$bad"
[ "$(/sbin/modinfo -F vermagic "$KO")" = "$(/sbin/modinfo -F vermagic "$(find "$ROCKNIX_EX/modules/$KVER" -name '*.ko*' | head -1)")" ] \
  || die "vermagic mismatch"

# Loaded on demand: depmod lists its "devname:uhid" alias, systemd creates /dev/uhid as a static
# node at boot (kmod-static-nodes) and the first open (bluetoothd) loads the module.
install -D -m644 "$KO" "$ROOTFS/usr/lib/modules/$KVER/extra/uhid.ko"
chroot_mount
in_chroot "depmod -a $KVER"
grep -q "^uhid uhid" "$ROOTFS/usr/lib/modules/$KVER/modules.devname" || die "uhid missing from modules.devname"
echo "uhid module installed ($(/sbin/modinfo -F vermagic "$KO"))."
