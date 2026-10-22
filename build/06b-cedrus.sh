#!/bin/bash
# Hardware video decoding: build the Cedrus V4L2 stateless decoder (sunxi-cedrus.ko) for the
# ROCKNIX kernel and install it into the root filesystem. See docs/video-decode.md.
#
# The ROCKNIX kernel already has everything Cedrus needs built in (media controller + request
# API, videobuf2-dma-contig, v4l2-mem2mem); only the driver is not enabled. We rebuild the exact
# ROCKNIX kernel tree (linux $LINUX_VERSION + ROCKNIX patches at tag $ROCKNIX_VERSION, ROCKNIX's
# own .config extracted from KERNEL, GCC 15 like ROCKNIX) so the module's symbol versions match,
# then check every symbol version against ROCKNIX's own modules before installing.
set -euo pipefail
source "$(dirname "$0")/config.sh"
source "$(dirname "$0")/lib/chroot.sh"
trap chroot_umount EXIT
assert_rootfs

K="$WORK/kernel"; mkdir -p "$K"
T="$K/linux-$LINUX_VERSION-rocknix-$ROCKNIX_VERSION"   # one tree per ROCKNIX release
export ARCH=arm64 CROSS_COMPILE="$K/gcc15/bin/aarch64-none-linux-gnu-"
fetch() {  # url file sha256
  local f="$K/$2"
  [ -f "$f" ] || { curl -sSfL -o "$f.part" "$1"; mv "$f.part" "$f"; }
  echo "$3  $f" | sha256sum -c --quiet - || die "checksum mismatch: $2"
}

# 1. Sources and toolchain (pinned checksums in config.sh)
fetch "$LINUX_URL" "linux-$LINUX_VERSION.tar.xz" "$LINUX_SHA256"
fetch "$KTOOLCHAIN_URL" gcc15.tar.xz "$KTOOLCHAIN_SHA256"
[ -x "${CROSS_COMPILE}gcc" ] || { mkdir -p "$K/gcc15"; tar xf "$K/gcc15.tar.xz" -C "$K/gcc15" --strip-components=1; }
if [ ! -d "$K/rocknix-src/.git" ]; then
  git clone -q --filter=blob:none --no-checkout https://github.com/ROCKNIX/distribution.git "$K/rocknix-src"
fi
git -C "$K/rocknix-src" sparse-checkout set --no-cone /projects/ROCKNIX/packages/linux /projects/ROCKNIX/devices/H700/patches
git -C "$K/rocknix-src" checkout -q "$ROCKNIX_VERSION"

# 2. Kernel tree = linux + ROCKNIX patches (same order as ROCKNIX's package.mk) + Cedrus H616
if [ ! -f "$T/.rg35xxh-patched" ]; then
  [ ! -e "$T" ] || die "$T exists but is not fully patched; remove it (safe_rm) and rerun"
  [ ! -e "$K/linux-$LINUX_VERSION" ] || die "$K/linux-$LINUX_VERSION is in the way"
  tar xf "$K/linux-$LINUX_VERSION.tar.xz" -C "$K" && mv "$K/linux-$LINUX_VERSION" "$T"
  P="$K/rocknix-src/projects/ROCKNIX"
  for d in "$P/packages/linux/patches/$LINUX_VERSION" "$P/packages/linux/patches/mainline" \
           "$P/devices/H700/patches/linux" "$P/packages/linux/patches/default"; do
    [ -d "$d" ] || continue
    for f in $(ls "$d"/*.patch 2>/dev/null | sort); do patch -d "$T" -p1 -s --forward < "$f"; done
  done
  for f in "$TOP"/build/kernel/*.patch; do patch -d "$T" -p1 -s --forward < "$f"; done
  touch "$T/.rg35xxh-patched"
fi

# The 64-byte stride is what lets the GPU import the decoded picture
# (docs/video-decode.md, "The blue video"): a 16-byte stride leaves panfrost
# refusing every frame whose width is not a multiple of 64.
grep -q "bytesperline = ALIGN(width, 64)" \
  "$T/drivers/staging/media/sunxi/cedrus/cedrus_video.c" \
  || die "the 64-byte stride patch did not apply (build/kernel/0002-cedrus-64-byte-stride.patch)"

# 3. ROCKNIX's .config (from the KERNEL image) + the decoder as a module
"$T/scripts/extract-ikconfig" "$ROCKNIX_EX/boot/KERNEL" > "$K/rocknix.config"
cp "$K/rocknix.config" "$T/.config"
"$T/scripts/config" --file "$T/.config" --enable VIDEO_SUNXI --module VIDEO_SUNXI_CEDRUS \
  --set-str INITRAMFS_SOURCE "" --set-str EXTRA_FIRMWARE ""
make -C "$T" -s olddefconfig
make -C "$T" -s -j"$(nproc)" vmlinux modules

# 4. Every symbol version the module imports must match ROCKNIX's own modules
KO="$T/drivers/staging/media/sunxi/cedrus/sunxi-cedrus.ko"
for m in $(find "$ROCKNIX_EX/modules/$KVER" -name '*.ko*'); do /sbin/modprobe --dump-modversions "$m" 2>/dev/null; done \
  | sort -u -k2 > "$K/rocknix.versions"
bad=$(/sbin/modprobe --dump-modversions "$KO" | awk 'NR==FNR{r[$2]=$1; next} ($2 in r) && r[$2]!=$1' "$K/rocknix.versions" -)
[ -z "$bad" ] || die "symbol version mismatch against the ROCKNIX kernel:\n$bad"
[ "$(/sbin/modinfo -F vermagic "$KO")" = "$(/sbin/modinfo -F vermagic "$(find "$ROCKNIX_EX/modules/$KVER" -name '*.ko*' | head -1)")" ] \
  || die "vermagic mismatch"

# 5. Install
install -D -m644 "$KO" "$ROOTFS/usr/lib/modules/$KVER/extra/sunxi-cedrus.ko"
chroot_mount
in_chroot "depmod -a $KVER"
echo "Cedrus decoder module installed ($(/sbin/modinfo -F vermagic "$KO"))."
