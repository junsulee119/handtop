#!/bin/bash
# Ship the VA-API driver that puts Chromium and VLC on the VPU.
#
# libva talks to the kernel's V4L2 stateless (request API) decoder through
# sofus13/libva-v4l2_request. Nothing selects it by default on arm64 (libva has
# no usable built-in default driver), so the desktop session exports
# LIBVA_DRIVER_NAME=v4l2_request (overlay/etc/profile.d/zz-rg35xxh-session.sh).
# With that in place VLC's own default avcodec-hw=any picks VA-API and Chromium
# enables VaapiVideoDecoder; no per-app flags are needed.
#
# The driver is built and patched by tools/build-va-v4l2request.sh (upstream
# master + build/patches/libva-v4l2-request-fixes.patch: single-planar support
# for cedrus, vaAcquireBufferHandle(), per-layer NV12 export for VLC 3). This
# step only makes sure the artifact lands in the image.
set -euo pipefail
TOP="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$TOP/build/config.sh"

"$TOP/tools/build-va-v4l2request.sh" --ship

SO="$ROOTFS/usr/lib/aarch64-linux-gnu/dri/v4l2_request_drv_video.so"
[ -f "$SO" ] || die "VA-API driver is not in the image"
file "$SO" | grep -q "ARM aarch64" || die "VA-API driver is not arm64"
echo "VA-API driver shipped: $(stat -c%s "$SO") bytes"
