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
# Source = Debian's own ffmpeg source package (FFMPEG_DEBIAN_VERSION: upstream FFMPEG_VERSION,
# now 7.1.5, plus any patches Debian carries; 7.1.5-0+deb13u1 carries none) + Kwiboo's
# patchset, applied as one diff (KWIBOO_BASE..KWIBOO_PIN: his branch
# v4l2-request-n7.1.3 minus n7.1.3 itself). Up to v0.3.5 the build used Kwiboo's
# branch as is, i.e. FFmpeg n7.1.3: about 388 upstream commits behind Debian's
# 7.1.5, two CVE fixes among them, while dpkg still showed Debian's version (codebase
# audit 2026-10-30, H01). The same release as Debian keeps its security fixes and
# its soname ABI (libavutil 59.39.100 / libavcodec 61.19.101), which this rootfs'
# mpv 0.40, Chromium and VLC were built against, so nothing else is rebuilt.
# How to bump it: docs/video-decode.md, "Updating FFmpeg".
#
# The build installs into a staging folder; build/pkg/build-ffmpeg-debs.py turns that into
# packages with Debian's names (libavcodec61, ..., ffmpeg, the -dev packages) and version
# FFMPEG_HANDTOP_VERSION (Debian's + "+handtop<rev>"), split and described like Debian's own .debs of
# the same version, and dpkg installs them over Debian's (updates without reflashing, step 3).
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

SRC="$WORK/src/ffmpeg"                # FFMPEG_* and KWIBOO_* are pinned in config.sh
STAGE="$WORK/stage/ffmpeg"            # make install goes here, then into the rootfs
FF_VERSION="${FFMPEG_VERSION}-handtop-v4l2request-${KWIBOO_PIN:0:7}"   # what ffmpeg -version prints

# Security fixes the base must contain: "CVE|file|a line of the fix". The base
# version is what really carries them; these guard against going back to an older
# base by mistake (codebase audit 2026-10-30, H01).
SECURITY_FIXES=(
  "CVE-2026-8461|libavcodec/magicyuv.c|if (1 + interlaced < height)"
  "CVE-2026-38347|libswscale/alphablend.c|int subsample_row = y_subsample &&"
)

# Build-time headers.
DEV_PKGS=(libdrm-dev libudev-dev zlib1g-dev libdav1d-dev
          libgnutls28-dev libx264-dev libmp3lame-dev libopus-dev
          libvorbis-dev libvpx-dev libass-dev libfreetype6-dev libxml2-dev
          libva-dev libvdpau-dev)

# Runtime side of the same features. The replacement libav* link against these,
# so they have to be in the image; installing them explicitly also keeps them
# there (the ones that only Debian's libav* pulled in would otherwise be
# candidates for autoremove).
RUNTIME_PKGS=(libgnutls30t64 libx264-164 libmp3lame0 libopus0 libvorbis0a
               libvpx9 libass9 libfreetype6 libxml2 libunibreak6 libva2 libvdpau1)

# Our packages under Debian's names. Held until the image has Handtop's apt source (then a pin
# to Handtop's repository replaces the hold, project doc update-system.md): otherwise Debian's
# next security version would replace them and silently drop the VPU path.
HOLD_PKGS=(libavcodec61 libavdevice61 libavfilter10 libavformat61
           libavutil59 libpostproc58 libswresample5 libswscale8 ffmpeg)
# Debian's binary packages of the same version: the reference for how files split into packages,
# their control fields, shlibs / symbols, copyright and changelogs.
REF_PKGS=(ffmpeg libavcodec61 libavdevice61 libavfilter10 libavformat61 libavutil59 libpostproc58
          libswresample5 libswscale8 libavcodec-dev libavdevice-dev libavfilter-dev libavformat-dev
          libavutil-dev libpostproc-dev libswresample-dev libswscale-dev)

chroot_mount
in_chroot "apt-get update -qq && apt-get install -y -qq --no-install-recommends ${DEV_PKGS[*]} ${RUNTIME_PKGS[*]}"
chroot_umount

DEB="$WORK/download/ffmpeg-debian"   # Debian's source and reference packages
KW="$WORK/src/ffmpeg-kwiboo"
for d in "$SRC" "$STAGE" "$DEB" "$KW" "$WORK/pkg-ffmpeg" "$ROOTFS/tmp/ffdeb"; do
  [ -e "$d" ] && safe_rm -r "$d"
done
mkdir -p "$SRC" "$STAGE" "$DEB/src" "$DEB/ref" "$ROOTFS/tmp/ffdeb"

# Debian's source package and its binary packages of that version, fetched by apt in the rootfs,
# which checks them against trixie-security's signed indexes. The source needs a deb-src line for
# the moment; it is removed right after.
src_list="$ROOTFS/etc/apt/sources.list.d/zz-handtop-ffmpeg-src.list"
grep -h '^deb .*-security' "$ROOTFS/etc/apt/sources.list" | sed 's/^deb /deb-src /' > "$src_list"
[ -s "$src_list" ] || die "no -security line in the rootfs' sources.list"
refs=""
for p in "${REF_PKGS[@]}"; do refs="$refs $p=$FFMPEG_DEBIAN_VERSION"; done
chroot_mount
fetched=1
in_chroot "apt-get update -qq && cd /tmp/ffdeb && apt-get source -qq --download-only ffmpeg=$FFMPEG_DEBIAN_VERSION && apt-get download -qq$refs" || fetched=0
safe_rm "$src_list"
in_chroot "apt-get update -qq"
chroot_umount
[ "$fetched" = 1 ] || die "Debian's ffmpeg $FFMPEG_DEBIAN_VERSION could not be fetched (superseded in trixie-security? bump FFMPEG_DEBIAN_VERSION, docs/video-decode.md)"
mv "$ROOTFS"/tmp/ffdeb/*.deb "$DEB/ref/"
mv "$ROOTFS"/tmp/ffdeb/ffmpeg_* "$DEB/src/"
safe_rm -r "$ROOTFS/tmp/ffdeb"

orig="$DEB/src/ffmpeg_$FFMPEG_VERSION.orig.tar.xz"
debian_tar=$(find "$DEB/src" -maxdepth 1 -name 'ffmpeg_*.debian.tar.xz' | head -n1)
[ -f "$orig" ] && [ -f "$debian_tar" ] || die "Debian's ffmpeg source is not orig.tar.xz + debian.tar.xz"
tar -C "$SRC" --strip-components=1 -xf "$orig"
tar -C "$SRC" -xf "$debian_tar"
[ "$(cat "$SRC/RELEASE")" = "$FFMPEG_VERSION" ] || die "Debian's source is not FFmpeg $FFMPEG_VERSION"
debian_patches=0
if [ -f "$SRC/debian/patches/series" ]; then
  while read -r p _; do
    case "$p" in ""|\#*) continue ;; esac
    patch -d "$SRC" -p1 --forward -s < "$SRC/debian/patches/$p" || die "Debian's patch $p does not apply"
    debian_patches=$((debian_patches + 1))
  done < "$SRC/debian/patches/series"
fi
git init -q "$SRC"     # its own repository, so git apply below works on it and not on Handtop's

# Kwiboo's branch, deep enough to reach its base (KWIBOO_COMMITS + 1), only to take the diff.
git init -q "$KW"
(cd "$KW" && git remote add kwiboo "$KWIBOO_URL" \
  && git fetch -q --depth $((KWIBOO_COMMITS + 1)) kwiboo "$KWIBOO_PIN")
[ "$(cd "$KW" && git rev-list --count "$KWIBOO_BASE..$KWIBOO_PIN")" = "$KWIBOO_COMMITS" ] \
  || die "Kwiboo's branch is not $KWIBOO_COMMITS commits on top of $KWIBOO_BASE"
# git apply is all or nothing: one hunk that doesn't fit and nothing is changed.
(cd "$KW" && git diff --binary "$KWIBOO_BASE" "$KWIBOO_PIN") | (cd "$SRC" && git apply) \
  || die "Kwiboo's patchset does not apply onto Debian's ffmpeg $FFMPEG_DEBIAN_VERSION"
[ -f "$SRC/libavutil/hwcontext_v4l2request.c" ] || die "Kwiboo's patchset is missing after applying it"
for fix in "${SECURITY_FIXES[@]}"; do
  IFS='|' read -r cve file line <<< "$fix"
  grep -qF "$line" "$SRC/$file" || die "FFmpeg $FFMPEG_VERSION lacks the fix for $cve ($file)"
done
# version.sh takes the version from this file; without it ffmpeg -version would show
# only a commit hash.
echo "$FF_VERSION" > "$SRC/VERSION"

# Local patch: register the decoders under the DRM device type as well, and
# accept the DRM device a render API's dmabuf interop hands over.
FF_PATCH="$TOP/build/patches/ffmpeg-v4l2request-drm.patch"
[ -f "$FF_PATCH" ] || die "missing patch: $FF_PATCH"
(cd "$SRC" && git apply "$FF_PATCH") || die "failed to apply $FF_PATCH"
grep -q "HWACCEL_DRM_V4L2REQUEST" "$SRC/libavcodec/hwconfig.h" || die "DRM-registration patch did not apply"

export PKG_CONFIG_SYSROOT_DIR="$ROOTFS"
export PKG_CONFIG_LIBDIR="$ROOTFS/usr/lib/aarch64-linux-gnu/pkgconfig:$ROOTFS/usr/share/pkgconfig"
(cd "$SRC" && ./configure --arch=aarch64 --target-os=linux --enable-cross-compile --cross-prefix=aarch64-linux-gnu- --sysroot="$ROOTFS" --pkg-config=pkg-config --prefix=/usr --libdir=/usr/lib/aarch64-linux-gnu --incdir=/usr/include/aarch64-linux-gnu --enable-shared --disable-static --disable-doc --disable-debug --enable-gpl --enable-neon --enable-libdrm --enable-libudev --enable-libdav1d --enable-v4l2-request --enable-vaapi --enable-gnutls --enable-libx264 --enable-libmp3lame --enable-libopus --enable-libvorbis --enable-libvpx --enable-libass --enable-libfreetype --enable-libxml2 --enable-vdpau > "$WORK/ffmpeg-config.log" 2>&1)
(cd "$SRC" && make -j"$(nproc)" > "$WORK/ffmpeg-build.log" 2>&1)

(cd "$SRC" && make DESTDIR="$STAGE" install >> "$WORK/ffmpeg-build.log" 2>&1)
# The cross-build's library paths (-L<rootfs>/usr/lib/...) end up in Libs.private of the .pc files:
# they are the standard library directories on the handheld anyway, so they go (review #28).
ROOTFS="$ROOTFS" python3 - "$STAGE"/usr/lib/aarch64-linux-gnu/pkgconfig/*.pc <<'PC'
import os, re, sys
root = re.escape(os.environ["ROOTFS"])
for p in sys.argv[1:]:
    t = open(p).read()
    t = re.sub(r"[ \t]*-L" + root + r"\S*", "", t)
    open(p, "w").write(t)
PC

file "$STAGE/usr/bin/ffmpeg" | grep -q "ARM aarch64" || die "ffmpeg is not arm64"
grep -q "#define CONFIG_V4L2_REQUEST 1" "$SRC/config.h" || die "v4l2_request not compiled in"
for c in H264 HEVC AV1 VP8 VP9 MPEG2; do
  grep -q "#define CONFIG_${c}_V4L2REQUEST_HWACCEL 1" "$SRC/config_components.h" \
    || die "${c}_v4l2request hwaccel not compiled in"
done

# VA-API is the other half: the driver 04e ships is reached through libva, and
# VLC 3 decodes with libavcodec's vaapi hwaccels through it (H.264 and HEVC are
# the ones that matter on this SoC). A build without them leaves VLC and
# Chromium on the CPU with no error, so gate on both paths.
grep -q "#define CONFIG_VAAPI 1" "$SRC/config.h" || die "vaapi not compiled in"
for c in H264 HEVC; do
  grep -q "#define CONFIG_${c}_VAAPI_HWACCEL 1" "$SRC/config_components.h" \
    || die "${c}_vaapi hwaccel not compiled in"
done

# AV1 has no Cedrus VPU decoder, so playback relies on software: this build must
# carry dav1d, because the native av1 decoder fails to pick a pixel format once
# av1 advertises the drm/v4l2request hw devices (renders black). See
# docs/video-decode.md.
grep -q "#define CONFIG_LIBDAV1D 1" "$SRC/config.h" || die "dav1d not compiled in"
# VDPAU only so that libavcodec exports the same functions as Debian's (av_vdpau_*): our package
# replaces Debian's, and a program using them must not fail to start. No VDPAU driver here.
grep -q "#define CONFIG_VDPAU 1" "$SRC/config.h" || die "vdpau not compiled in"

# Where these files came from (shipped in libavutil59).
mkdir -p "$STAGE/usr/share/doc/handtop-ffmpeg"
{
  echo "FFmpeg $FF_VERSION, built by Handtop's build/04c-v4l2-ffmpeg.sh."
  echo "Packaged under Debian's names as $FFMPEG_HANDTOP_VERSION."
  echo "base:      Debian's ffmpeg source package $FFMPEG_DEBIAN_VERSION (FFmpeg $FFMPEG_VERSION, $debian_patches Debian patches)"
  echo "patchset:  $KWIBOO_URL $KWIBOO_BASE..$KWIBOO_PIN ($KWIBOO_COMMITS commits)"
  echo "patch:     build/patches/ffmpeg-v4l2request-drm.patch sha256 $(sha256sum "$FF_PATCH" | cut -d' ' -f1)"
} > "$STAGE/usr/share/doc/handtop-ffmpeg/BUILDINFO"
chmod -R u=rwX,go=rX "$STAGE"
python3 "$TOP/build/pkg/build-ffmpeg-debs.py" "$STAGE" "$DEB/ref" "$ROOTFS" "$WORK/pkg-ffmpeg" "$FFMPEG_HANDTOP_VERSION"
# No packaged file may mention the build machine's paths (they leak the build account and point nowhere).
for d in "$WORK"/pkg-ffmpeg/*.deb; do
  if dpkg-deb --fsys-tarfile "$d" | tar -xO 2>/dev/null | grep -a -q -F "$ROOTFS"; then
    die "$(basename "$d") contains the build root path ($ROOTFS)"
  fi
done

# A reused rootfs still has the files earlier builds copied in without a package: headers in the
# old /usr/include location, examples, BUILDINFO. The packages put everything else in place.
for d in libavcodec libavdevice libavfilter libavformat libavutil libpostproc libswresample libswscale; do
  [ -d "$ROOTFS/usr/include/$d" ] && safe_rm -r "$ROOTFS/usr/include/$d"
done
for d in usr/share/ffmpeg/examples usr/share/doc/handtop-ffmpeg; do
  [ -e "$ROOTFS/$d" ] && safe_rm -r "$ROOTFS/$d"
done

chroot_mount
in_chroot "apt-mark unhold ${HOLD_PKGS[*]} >/dev/null"
mkdir -p "$ROOTFS/tmp/ffpkg"
cp "$WORK"/pkg-ffmpeg/*.deb "$ROOTFS/tmp/ffpkg/"
in_chroot "dpkg -i /tmp/ffpkg/*.deb"
safe_rm -r "$ROOTFS/tmp/ffpkg"
for p in "${HOLD_PKGS[@]}"; do
  [ "$(in_chroot "dpkg-query -W -f='\${Version}' $p")" = "$FFMPEG_HANDTOP_VERSION" ] || die "$p is not $FFMPEG_HANDTOP_VERSION after installing"
done
in_chroot "ldconfig"
[[ "$(in_chroot "command -v ffmpeg")" == "/usr/bin/ffmpeg" ]] || die "ffmpeg in PATH is not /usr/bin/ffmpeg"
[[ "$(in_chroot "ffmpeg -version")" == *"$FF_VERSION"* ]] || die "patched ffmpeg is not the installed one"
in_chroot "ffmpeg -hide_banner -hwaccels" | grep -w v4l2request >/dev/null || die "installed ffmpeg has no v4l2request hwaccel"
in_chroot "ffmpeg -hide_banner -hwaccels" | grep -w vaapi >/dev/null || die "installed ffmpeg has no vaapi hwaccel"
in_chroot "ffmpeg -hide_banner -decoders" | grep -w libdav1d >/dev/null || die "installed ffmpeg has no dav1d decoder"

# (grep without -q below: -q stops reading at the first match, the long ffmpeg list then dies of
# SIGPIPE, and with pipefail the check fails although the match was found.)
# The distro build has these; without them the replacement is a downgrade
# (no https in libavformat, no common encoders, no subtitle rendering).
in_chroot "ffmpeg -hide_banner -protocols" | grep -w https >/dev/null || die "installed ffmpeg has no https protocol (gnutls)"
for enc in libx264 libmp3lame libopus libvorbis libvpx; do
  in_chroot "ffmpeg -hide_banner -encoders" | grep -w "$enc" >/dev/null || die "installed ffmpeg has no $enc encoder"
done
in_chroot "ffmpeg -hide_banner -filters" | grep -w ass >/dev/null || die "installed ffmpeg has no ass filter (libass)"

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
  if in_chroot "mpv --hwdec=help" | grep -w drm >/dev/null; then drm_ok=1; break; fi
  sleep 1
done
if [ "$drm_ok" != 1 ]; then
  ls -la "$ROOTFS/usr/lib/aarch64-linux-gnu/libavcodec.so.61"* >&2
  in_chroot "ldconfig -p | grep libavcodec" >&2
  in_chroot "mpv --hwdec=help" >&2 | head -20
  die "mpv does not offer the drm hwdec (DRM-registration patch missing?)"
fi

# Hold our packages until Handtop's apt source (with its pin) is in the image.
hold=""
for p in "${HOLD_PKGS[@]}"; do
  in_chroot "dpkg -s $p >/dev/null 2>&1" && hold="$hold $p"
done
[ -n "$hold" ] || die "none of the libav packages are installed, cannot hold them"
in_chroot "apt-mark hold $hold"
for p in $hold; do
  in_chroot "apt-mark showhold" | grep -w "$p" >/dev/null || die "apt-mark hold did not take for $p"
done

in_chroot "apt-get purge -y -qq ${DEV_PKGS[*]} && apt-get autoremove -y -qq --purge && apt-get clean"
safe_rm -r "$ROOTFS"/var/lib/apt/lists/*
mkdir -p "$ROOTFS/var/lib/apt/lists/partial"
echo "ffmpeg $FF_VERSION installed to /usr."
