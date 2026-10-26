#!/bin/bash
# Patched ffmpeg with V4L2 request-API decode (Cedrus VPU).
#
# Debian trixie ships vanilla ffmpeg 7.1, which has the mainline `drm` hwaccel
# but none of the stateless V4L2 request-API hwaccels that Cedrus needs, so we
# cross-compile Kwiboo's FFmpeg -- the V4L2 Request API patchset (upstream PR
# 20847, branch "v4l2request-v3") -- and install over the system libs
# (--libdir=triplet dir). This replaces dpkg-owned files; intentional on an
# appliance image. The replaced packages are held further down, so an upgrade
# cannot silently undo the VPU path.
#
# Why this tree: Moonlight's working 1080p60 HEVC decode comes from the same
# code. Its binary embeds libavutil/hwcontext_v4l2request.c and the
# h264/hevc/av1_v4l2request hwaccels, i.e. a `v4l2request` hwdevice plus
# per-codec stateless hwaccels. mpv builds its --hwdec values from FFmpeg's
# per-codec hw configs via av_hwdevice_get_type_name(), so
# `--hwdec=v4l2request[-copy]` becomes usable with no mpv patch.
#
# One local patch rides on top (build/patches/ffmpeg-v4l2request-drm.patch):
# the same stateless decoders are also registered under the `drm` device type and
# accept the DRM device a render API hands them, so mpv's existing dmabuf (DRM
# PRIME) interop renders those frames zero-copy via --hwdec=drm. Without it mpv
# has no interop for the v4l2request hwdevice and only the copy path works, which
# caps 1080p below real time. See docs/video-decode.md ("Zero-copy").
#
# Branch v4l2-request-n7.1.3 is rebased on FFmpeg n7.1.3 and reports
# libavutil 59.39.100 / libavcodec 61.19.101: the same soname ABI as Debian's
# ffmpeg 7.1.5 that this rootfs' mpv 0.40 was built against, so nothing else is
# rebuilt (libplacebo and friends stay as built).
#
# Debian's ffmpeg is built against ~60 external libraries; a build with only
# drm/udev/dav1d would drop most of them -- no gnutls, so libavformat has no
# https and mpv cannot play URLs; no x264/lame/opus/vorbis/vpx encoders; no
# libass, so no subtitle rendering. The configure line below therefore enables
# the same set the distro build has for those features, and the runtime side of
# each is installed into the image.
#
# The checks below prove the decoders exist AND are wired into mpv. They cannot
# prove a frame decodes: only a device with /dev/video0 can, see
# tools/check-video-decode.sh. Gating on CONFIG_*_V4L2REQUEST_HWACCEL or on
# `mpv --hwdec=help` alone is not enough -- an earlier image passed those and
# still segfaulted on every HEVC file (docs/video-decode.md).
#
# Not rpi-ffmpeg (jc-kynesim/rpi-ffmpeg@6dbf87a): its hevc_v4l2request is a
# hwaccel bound to AV_HWDEVICE_TYPE_DRM and segfaults against Cedrus on this
# kernel.
set -euo pipefail
source "$(dirname "$0")/config.sh"
source "$(dirname "$0")/lib/chroot.sh"
trap chroot_umount EXIT

KWIBOO_PIN="$FFMPEG_V4L2REQ_PIN"      # pinned in config.sh
KWIBOO_URL="$FFMPEG_V4L2REQ_URL"
SRC="$WORK/src/kwiboo-ffmpeg"

# Build-time headers.
DEV_PKGS=(libdrm-dev libudev-dev zlib1g-dev libdav1d-dev
          libgnutls28-dev libx264-dev libmp3lame-dev libopus-dev
          libvorbis-dev libvpx-dev libass-dev libfreetype6-dev libxml2-dev)

# Runtime side of the same features. The replacement libav* link against these,
# so they have to be in the image; installing them explicitly also keeps them
# there (the ones that only Debian's libav* pulled in would otherwise be
# candidates for autoremove).
RUNTIME_PKGS=(libgnutls30t64 libx264-164 libmp3lame0 libopus0 libvorbis0a
               libvpx9 libass9 libfreetype6 libxml2 libunibreak6)

# dpkg-owned libraries we overwrite. Holding them keeps an upgrade from
# replacing them and silently dropping the VPU path again.
HOLD_PKGS=(libavcodec61 libavdevice61 libavfilter10 libavformat61
           libavutil59 libpostproc58 libswresample5 libswscale8)

chroot_mount
in_chroot "apt-get update -qq && apt-get install -y -qq --no-install-recommends ${DEV_PKGS[*]} ${RUNTIME_PKGS[*]}"
chroot_umount

[ -e "$SRC" ] && safe_rm -r "$SRC"
mkdir -p "$SRC"
git init -q "$SRC"
(cd "$SRC" && git remote add origin "$KWIBOO_URL" && git fetch -q --depth 1 origin "$KWIBOO_PIN" && git checkout -q FETCH_HEAD)
[ "$(cd "$SRC" && git rev-parse HEAD)" = "$KWIBOO_PIN" ] || die "kwiboo-ffmpeg checkout mismatch"

# Local patch: register the decoders under the DRM device type as well, and
# accept the DRM device a render API's dmabuf interop hands over.
FF_PATCH="$TOP/build/patches/ffmpeg-v4l2request-drm.patch"
[ -f "$FF_PATCH" ] || die "missing patch: $FF_PATCH"
(cd "$SRC" && git apply "$FF_PATCH") || die "failed to apply $FF_PATCH"
grep -q "HWACCEL_DRM_V4L2REQUEST" "$SRC/libavcodec/hwconfig.h" || die "DRM-registration patch did not apply"

export PKG_CONFIG_SYSROOT_DIR="$ROOTFS"
export PKG_CONFIG_LIBDIR="$ROOTFS/usr/lib/aarch64-linux-gnu/pkgconfig:$ROOTFS/usr/share/pkgconfig"
(cd "$SRC" && ./configure --arch=aarch64 --target-os=linux --enable-cross-compile --cross-prefix=aarch64-linux-gnu- --sysroot="$ROOTFS" --pkg-config=pkg-config --prefix=/usr --libdir=/usr/lib/aarch64-linux-gnu --enable-shared --disable-static --disable-doc --disable-debug --enable-gpl --enable-neon --enable-libdrm --enable-libudev --enable-libdav1d --enable-v4l2-request --enable-gnutls --enable-libx264 --enable-libmp3lame --enable-libopus --enable-libvorbis --enable-libvpx --enable-libass --enable-libfreetype --enable-libxml2 > "$WORK/ffmpeg-config.log" 2>&1)
(cd "$SRC" && make -j"$(nproc)" > "$WORK/ffmpeg-build.log" 2>&1)

(cd "$SRC" && make DESTDIR="$ROOTFS" install >> "$WORK/ffmpeg-build.log" 2>&1)

file "$ROOTFS/usr/bin/ffmpeg" | grep -q "ARM aarch64" || die "ffmpeg is not arm64"
grep -q "#define CONFIG_V4L2_REQUEST 1" "$SRC/config.h" || die "v4l2_request not compiled in"
for c in H264 HEVC AV1 VP8 VP9 MPEG2; do
  grep -q "#define CONFIG_${c}_V4L2REQUEST_HWACCEL 1" "$SRC/config_components.h" \
    || die "${c}_v4l2request hwaccel not compiled in"
done

# AV1 has no Cedrus VPU decoder, so playback relies on software: this build must
# carry dav1d, because the native av1 decoder fails to pick a pixel format once
# av1 advertises the drm/v4l2request hw devices (renders black). See
# docs/video-decode.md.
grep -q "#define CONFIG_LIBDAV1D 1" "$SRC/config.h" || die "dav1d not compiled in"

chroot_mount
in_chroot "ldconfig"
[[ "$(in_chroot "command -v ffmpeg")" == "/usr/bin/ffmpeg" ]] || die "ffmpeg in PATH is not /usr/bin/ffmpeg"
[[ "$(in_chroot "ffmpeg -version")" == *"${KWIBOO_PIN:0:7}"* ]] || die "patched ffmpeg is not the installed one"
in_chroot "ffmpeg -hide_banner -hwaccels" | grep -qw v4l2request || die "installed ffmpeg has no v4l2request hwaccel"
in_chroot "ffmpeg -hide_banner -decoders" | grep -qw libdav1d || die "installed ffmpeg has no dav1d decoder"

# The distro build has these; without them the replacement is a downgrade
# (no https in libavformat, no common encoders, no subtitle rendering).
in_chroot "ffmpeg -hide_banner -protocols" | grep -qw https || die "installed ffmpeg has no https protocol (gnutls)"
for enc in libx264 libmp3lame libopus libvorbis libvpx; do
  in_chroot "ffmpeg -hide_banner -encoders" | grep -qw "$enc" || die "installed ffmpeg has no $enc encoder"
done
in_chroot "ffmpeg -hide_banner -filters" | grep -qw ass || die "installed ffmpeg has no ass filter (libass)"

# -init_hw_device alone just prints the usage screen; give it something to do.
# An unregistered type fails with "unknown device type" (exit 234).
in_chroot "ffmpeg -hide_banner -v error -init_hw_device v4l2request -f lavfi -i nullsrc=s=16x16:r=1:d=1 -f null -" >/dev/null \
  || die "cannot create the v4l2request hwdevice"
[[ "$(in_chroot "mpv --hwdec=help")" == *"v4l2request"* ]] || die "mpv does not offer the v4l2request hwdec"
# mpv builds its --hwdec list from libavcodec's hwconfigs, and libavcodec was
# replaced a moment ago: refresh the loader cache and allow for a stale read
# before failing. Dump diagnostics if it really is missing.
drm_ok=0
for _ in 1 2 3; do
  in_chroot "ldconfig"
  if in_chroot "mpv --hwdec=help" | grep -qw drm; then drm_ok=1; break; fi
  sleep 1
done
if [ "$drm_ok" != 1 ]; then
  ls -la "$ROOTFS/usr/lib/aarch64-linux-gnu/libavcodec.so.61"* >&2
  in_chroot "ldconfig -p | grep libavcodec" >&2
  in_chroot "mpv --hwdec=help" >&2 | head -20
  die "mpv does not offer the drm hwdec (DRM-registration patch missing?)"
fi

# Hold the libraries we replace: without this an upgrade reinstalls Debian's
# ones and the VPU path disappears without a word.
hold=""
for p in "${HOLD_PKGS[@]}"; do
  in_chroot "dpkg -s $p >/dev/null 2>&1" && hold="$hold $p"
done
[ -n "$hold" ] || die "none of the libav packages are installed, cannot hold them"
in_chroot "apt-mark hold $hold"
for p in $hold; do
  in_chroot "apt-mark showhold" | grep -qw "$p" || die "apt-mark hold did not take for $p"
done

in_chroot "apt-get purge -y -qq ${DEV_PKGS[*]} && apt-get autoremove -y -qq --purge && apt-get clean"
safe_rm -r "$ROOTFS"/var/lib/apt/lists/*
mkdir -p "$ROOTFS/var/lib/apt/lists/partial"
echo "kwiboo-ffmpeg $KWIBOO_PIN installed to /usr."
