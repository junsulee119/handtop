#!/bin/bash
# Cross-build sofus13/libva-v4l2_request (master, pinned) — the VA-API backend driver
# over the V4L2 stateless Request API — inside a qemu chroot of the image
# rootfs, so the .so is ready to push the moment the device is reachable.
# (On-device compile costs ~an hour on 1 GB of RAM; this takes ~a minute.)
#
# Context: docs/video-decode.md ("Watching video with VLC", "Chromium").
# Bases on upstream master (f54d8d2: one CAPTURE buffer per surface, queued
# with V4L2_MEMORY_DMABUF, so a surface's memory is stable from creation - which
# is what Chromium needs) plus build/patches/libva-v4l2-request-fixes.patch:
#
#  1. single-planar support. Master dropped the dual-planar code in 4cb4bde
#     ("require multiplane support", -183/+69) because its author's SoCs
#     (RK3399/RK3588) are multiplanar. Cedrus exposes V4L2_CAP_VIDEO_M2M only,
#     so master refuses it ("no V4L2 Request API decoder found"). This restores
#     the single-planar fallback; prefer sending it upstream over converting
#     cedrus to multiplanar (~300-400 lines in a shared kernel API).
#  2. vaAcquireBufferHandle(): a stub upstream. VLC 3 probes its dmabuf path
#     with DeriveImage + DRM_PRIME before it accepts the GL converter.
#  3. NV12/P010 export one plane per layer even when the client passes flags=0
#     (VLC 3 rejects a composite layer, which shows as a green window).
#
# The artifact is staged at work/va-driver/v4l2_request_drv_video.so; --ship
# installs it into the rootfs, and tools/test-va-v4l2request.sh runs the checks
# on the device. With LIBVA_DRIVER_NAME=v4l2_request exported for the session it
# is the VA-API driver every client finds, so Chromium decodes on the VPU with no
# flags; mpv is unaffected (it uses the FFmpeg hwaccels, not VA-API).
#
# Needs qemu-aarch64 binfmt and root. Run from anywhere:
#
#   sudo tools/build-va-v4l2request.sh [--ship]
#
# --ship additionally installs the driver into $ROOTFS (future images).
set -euo pipefail
TOP="$(cd "$(dirname "$(realpath "${BASH_SOURCE[0]}")")/.." && pwd)"
source "$TOP/build/config.sh"
source "$TOP/build/lib/chroot.sh"
trap chroot_umount EXIT

VA_TAG="f54d8d2c36433b38ba9b8633ac10eec444ac9cf1"   # master: surface: simplify backing
VA_URL="https://github.com/sofus13/libva-v4l2_request.git"
SRC="$WORK/src/libva-v4l2_request"
OUT="$WORK/va-driver"
DEV_PKGS="meson ninja-build pkg-config libva-dev libdrm-dev"

# Fresh pinned checkout on the host side (network here, not in the chroot).
[ -e "$SRC" ] && safe_rm -r "$SRC"
mkdir -p "$SRC"
git init -q "$SRC"
(cd "$SRC" && git remote add origin "$VA_URL" && git fetch -q --depth 1 origin "$VA_TAG" && git checkout -q FETCH_HEAD)
grep -q "v4l2_request" "$SRC/meson.build" || die "unexpected checkout at $VA_TAG"

# Single-planar support + the two VA-API interop fixes (see the header).
patch -d "$SRC" -p1 -s --forward < "$TOP/build/patches/libva-v4l2-request-fixes.patch" \
  || die "the driver fixes patch did not apply"
for sym in "buf_info->mem_size = v4l2r_buffer_bytes(buffer)" \
           "v4l2r_format_pixelformat" "V4L2_CAP_VIDEO_M2M)" ; do
  grep -rq "$sym" "$SRC/src" || die "the driver fixes patch did not apply ($sym)"
done

chroot_mount
in_chroot "apt-get update -qq && apt-get install -y -qq --no-install-recommends $DEV_PKGS"

# Build inside the chroot (arm64 via binfmt). Source goes in without .git.
in_chroot "mkdir -p /opt/va-build"
tar -C "$SRC" --exclude=.git -cf - . | tar -C "$ROOTFS/opt/va-build" -xf -
in_chroot "cd /opt/va-build && meson setup build >/dev/null && ninja -C build"
# the build tools must not stay in the image (same rule as 04c)
in_chroot "apt-get purge -y -qq $DEV_PKGS && apt-get autoremove -y -qq --purge && apt-get clean"
safe_rm -r "$ROOTFS"/var/lib/apt/lists/*          # the index is ~40 MB; 04c keeps it out too
mkdir -p "$ROOTFS/var/lib/apt/lists/partial"

mkdir -p "$OUT"
cp "$ROOTFS/opt/va-build/build/src/v4l2_request_drv_video.so" "$OUT/"
in_chroot "test -f /opt/va-build/build/src/v4l2_request_drv_video.so"
safe_rm -r "$ROOTFS/opt/va-build"

SO="$OUT/v4l2_request_drv_video.so"
[ -f "$SO" ] || die "driver .so not found under $OUT"
file "$SO" | grep -q "ARM aarch64" || die "driver is not arm64"

if [ "${1:-}" = "--ship" ]; then
  install -m755 "$SO" "$ROOTFS/usr/lib/aarch64-linux-gnu/dri/"
  echo "shipped to $ROOTFS/usr/lib/aarch64-linux-gnu/dri/"
fi
echo "artifact: $SO ($(stat -c%s "$SO") bytes, tag $VA_TAG)"
