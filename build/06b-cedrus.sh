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

# 1. Sources and toolchain (pinned checksums in config.sh). The compiler is the build for this
# host (x86_64 or arm64; codebase audit 2026-10-30, M13), kept per host in case work/ is shared.
[ -n "$KTOOLCHAIN_SHA256" ] || die "no Arm GCC build for host '$KTOOLCHAIN_HOST' (x86_64 or aarch64 only)"
fetch "$LINUX_URL" "linux-$LINUX_VERSION.tar.xz" "$LINUX_SHA256"
fetch "$KTOOLCHAIN_URL" "gcc-$KTOOLCHAIN_VERSION-$KTOOLCHAIN_HOST.tar.xz" "$KTOOLCHAIN_SHA256"
if [ ! -x "${CROSS_COMPILE}gcc" ] || [ "$(cat "$K/gcc15/.host" 2>/dev/null)" != "$KTOOLCHAIN_HOST-$KTOOLCHAIN_SHA256" ]; then
  [ ! -e "$K/gcc15" ] || safe_rm -r "$K/gcc15"
  mkdir -p "$K/gcc15"
  tar xf "$K/gcc-$KTOOLCHAIN_VERSION-$KTOOLCHAIN_HOST.tar.xz" -C "$K/gcc15" --strip-components=1
  echo "$KTOOLCHAIN_HOST-$KTOOLCHAIN_SHA256" > "$K/gcc15/.host"
fi
"${CROSS_COMPILE}gcc" --version | head -n1
if [ ! -d "$K/rocknix-src/.git" ]; then
  git clone -q --filter=blob:none --no-checkout https://github.com/ROCKNIX/distribution.git "$K/rocknix-src"
fi
git -C "$K/rocknix-src" sparse-checkout set --no-cone /projects/ROCKNIX/packages/linux /projects/ROCKNIX/devices/H700/patches
git -C "$K/rocknix-src" checkout -q "$ROCKNIX_VERSION"

# 2. Kernel tree = linux + ROCKNIX patches (same order as ROCKNIX's package.mk) + our patches
# (build/kernel/). The marker holds a hash of everything that went into the tree: the Linux
# tarball, every patch file (names and contents, in order), the compiler and the build host's
# architecture (the tree's own tools, scripts/*, are host programs). When any of them
# changes, the tree is built again from scratch; a tree from before the hash (empty marker) too.
# Before, only the marker's presence was checked, so an edited patch in build/kernel/ was
# silently left out of the next build (codebase audit 2026-10-30, L02).
P="$K/rocknix-src/projects/ROCKNIX"
PATCHES=()
for d in "$P/packages/linux/patches/$LINUX_VERSION" "$P/packages/linux/patches/mainline" \
         "$P/devices/H700/patches/linux" "$P/packages/linux/patches/default"; do
  [ -d "$d" ] || continue
  while IFS= read -r f; do PATCHES+=("$f"); done < <(find "$d" -maxdepth 1 -name '*.patch' | sort)
done
PATCHES+=("$TOP"/build/kernel/*.patch)
# Then the LibreELEC cedrus series (provenance: build/kernel/libreelec/README.md).
# Inside PATCHES so that editing or re-syncing one of them rebuilds the tree.
while IFS= read -r f; do PATCHES+=("$f"); done < <(find "$TOP/build/kernel/libreelec" -maxdepth 1 -name '*.patch' | sort)
INPUTS="$( { echo "linux $LINUX_SHA256 rocknix $ROCKNIX_VERSION gcc $KTOOLCHAIN_VERSION host $KTOOLCHAIN_HOST"
             for f in "${PATCHES[@]}"; do
               n="${f#"$K/"}"; echo "${n#"$TOP/"} $(sha256sum < "$f" | cut -d' ' -f1)"
             done
           } | sha256sum | cut -d' ' -f1)"
if [ "$(cat "$T/.rg35xxh-patched" 2>/dev/null)" != "$INPUTS" ]; then
  if [ -e "$T" ]; then
    echo "Kernel tree $T is out of date (or was not fully patched): building it again."
    safe_rm -r "$T"
  fi
  [ ! -e "$K/linux-$LINUX_VERSION" ] || die "$K/linux-$LINUX_VERSION is in the way"
  tar xf "$K/linux-$LINUX_VERSION.tar.xz" -C "$K" && mv "$K/linux-$LINUX_VERSION" "$T"
  for f in "${PATCHES[@]}"; do
    # Our patches (build/kernel/ and the series it carries) must apply exactly:
    # the series is a snapshot of someone else's tree, so a context line that
    # moved since has to stop the build instead of landing one line off.
    # ROCKNIX's own patches keep patch's default fuzz.
    case "$f" in
      "$TOP"/build/kernel/*) patch -d "$T" -p1 -s --forward --fuzz=0 < "$f" ;;
      *) patch -d "$T" -p1 -s --forward < "$f" ;;
    esac
  done
  echo "$INPUTS" > "$T/.rg35xxh-patched"
fi

# The 64-byte stride is what lets the GPU import the decoded picture
# (docs/video-decode.md, "The blue video"): a 16-byte stride leaves panfrost
# refusing every frame whose width is not a multiple of 64.
grep -q "bytesperline = ALIGN(width, 64)" \
  "$T/drivers/staging/media/sunxi/cedrus/cedrus_video.c" \
  || die "the 64-byte stride patch did not apply (build/kernel/0002-cedrus-64-byte-stride.patch)"
# Same for the VP9 backend and the padding fix: a patch that quietly stopped
# applying would leave the image without the codec and with a visible artefact.
[ -s "$T/drivers/staging/media/sunxi/cedrus/cedrus_vp9.c" ] \
  || die "the VP9 backend is missing (0411 in build/kernel/libreelec/)"
grep -q "cedrus_clear_padding" "$T/drivers/staging/media/sunxi/cedrus/cedrus_dec.c" \
  || die "the padding fix did not apply (0901 in build/kernel/libreelec/)"

# 3. ROCKNIX's .config (from the KERNEL image) + the decoder as a module
"$T/scripts/extract-ikconfig" "$ROCKNIX_EX/boot/KERNEL" > "$K/rocknix.config"
cp "$K/rocknix.config" "$T/.config"
"$T/scripts/config" --file "$T/.config" --enable VIDEO_SUNXI --module VIDEO_SUNXI_CEDRUS \
  --set-str INITRAMFS_SOURCE "" --set-str EXTRA_FIRMWARE ""
make -C "$T" -s olddefconfig
make -C "$T" -s -j"$(nproc)" vmlinux modules

# 4. Every symbol version the module imports must match ROCKNIX's own modules.
# cedrus now also needs the v4l2-vp9 helper module (VP9 probability adaptation),
# which ROCKNIX does not ship, so it is built and installed with it.
KO="$T/drivers/staging/media/sunxi/cedrus/sunxi-cedrus.ko"
VKO="$T/drivers/media/v4l2-core/v4l2-vp9.ko"
# shellcheck disable=SC2044  # module paths never contain spaces
for m in $(find "$ROCKNIX_EX/modules/$KVER" -name '*.ko*'); do /sbin/modprobe --dump-modversions "$m" 2>/dev/null; done \
  | sort -u -k2 > "$K/rocknix.versions"
bad=$(/sbin/modprobe --dump-modversions "$KO" "$VKO" | awk 'NR==FNR{r[$2]=$1; next} ($2 in r) && r[$2]!=$1' "$K/rocknix.versions" -)
[ -z "$bad" ] || die "symbol version mismatch against the ROCKNIX kernel:\n$bad"
[ "$(/sbin/modinfo -F vermagic "$KO")" = "$(/sbin/modinfo -F vermagic "$(find "$ROCKNIX_EX/modules/$KVER" -name '*.ko*' | head -1)")" ] \
  || die "vermagic mismatch"

# 5. Install
install -D -m644 "$KO" "$ROOTFS/usr/lib/modules/$KVER/extra/sunxi-cedrus.ko"
install -D -m644 "$VKO" "$ROOTFS/usr/lib/modules/$KVER/kernel/drivers/media/v4l2-core/v4l2-vp9.ko"
chroot_mount
in_chroot "depmod -a $KVER"
echo "Cedrus decoder module installed ($(/sbin/modinfo -F vermagic "$KO"))."
