#!/bin/bash
# Check the hardware video-decode (Cedrus VPU) path on a running Handtop device.
#
# Nothing in the image build can prove this: the VPU only exists on the device,
# behind /dev/video0. Run this there.
#
#   ./check-video-decode.sh [video-file]
#
# With no argument it uses the first video file it finds under ~/Downloads or
# /usr/share; pass a H.264 or HEVC file to be explicit. Exits non-zero if the
# VPU path does not decode.
#
# The checks require a real decode (VPU engaged, no decode errors) rather than a
# capability listing: an earlier image shipped with CONFIG_*_V4L2REQUEST_HWACCEL
# set and `mpv --hwdec=help` listing the method, and still crashed on every HEVC
# file. See docs/video-decode.md.
set -u

FILE="${1:-}"
if [ -z "$FILE" ]; then
  # Cedrus has no AV1 decoder here (docs/video-decode.md): decoding AV1 would fail and look
  # like a broken VPU, so skip AV1 candidates instead of picking the first file blindly.
  for d in "$HOME/Downloads" /usr/share/mpv /usr/share; do
    [ -d "$d" ] || continue
    while IFS= read -r -d '' f; do
      [ "$(ffprobe -v error -select_streams v:0 -show_entries stream=codec_name -of csv=p=0 "$f" 2>/dev/null)" = av1 ] && continue
      FILE="$f"; break
    done < <(find "$d" -maxdepth 3 -type f \( -iname '*.mkv' -o -iname '*.mp4' -o -iname '*.webm' \) -print0 2>/dev/null)
    [ -n "$FILE" ] && break
  done
fi
[ -n "$FILE" ] && [ -r "$FILE" ] || { echo "usage: $0 <video-file>"; exit 2; }

export WAYLAND_DISPLAY="${WAYLAND_DISPLAY:-wayland-0}"
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"

T=$(mktemp -d)
trap 'rm -rf "$T"' EXIT

codec=$(ffprobe -v error -select_streams v:0 -show_entries stream=codec_name -of csv=p=0 "$FILE" 2>/dev/null)
echo "file:  $FILE"
echo "codec: ${codec:-unknown}"
fail=0
chk() { printf '  %-4s  %s\n' "$([ "$2" = 0 ] && echo ok || echo FAIL)" "$1"; [ "$2" = 0 ] || fail=1; }

echo "device:"
[ -e /dev/video0 ] && chk "/dev/video0 present" 0 || chk "/dev/video0 present" 1
[ -e /dev/media0 ] && chk "/dev/media0 present" 0 || chk "/dev/media0 present" 1
lsmod 2>/dev/null | grep -q '^sunxi_cedrus' && chk "sunxi_cedrus loaded" 0 || chk "sunxi_cedrus loaded" 1
if [ -e /dev/dma_heap/system ]; then
  if [ -r /dev/dma_heap/system ] && [ -w /dev/dma_heap/system ]; then
    chk "dma-buf heaps openable by $(id -un)" 0
  else
    chk "dma-buf heaps openable by $(id -un) -- see 72-rg35xxh-dma-heap.rules" 1
  fi
fi

echo "patched ffmpeg:"
ffmpeg_bin=$(command -v ffmpeg || true)
[ -n "$ffmpeg_bin" ] \
  && chk "ffmpeg is installed (${ffmpeg_bin})" 0 \
  || chk "ffmpeg is installed" 1
ffmpeg -hide_banner -hwaccels 2>/dev/null | grep -qw v4l2request \
  && chk "ffmpeg -hwaccels lists v4l2request" 0 \
  || chk "ffmpeg -hwaccels lists v4l2request" 1

echo "ffmpeg -hwaccel v4l2request (real decode, first 5 s):"
timeout 90 ffmpeg -hide_banner -nostdin -v verbose -hwaccel v4l2request -t 5 -i "$FILE" -f null /dev/null > "$T/ff.log" 2>&1
rc=$?
[ $rc -eq 0 ] && chk "decodes without crashing (exit 0)" 0 || chk "decodes without crashing (exit $rc)" 1
grep -q 'Using V4L2 media driver cedrus' "$T/ff.log" \
  && chk "Cedrus VPU engaged (not software)" 0 \
  || chk "Cedrus VPU engaged (not software)" 1
grep -qa '0 decode errors' "$T/ff.log" \
  && chk "no decode errors" 0 \
  || chk "no decode errors" 1
grep -aiE 'Using V4L2 media driver|decode errors|Segmentation|Invalid' "$T/ff.log" | tail -3 | sed 's/^/        /'

echo "mpv --hwdec=v4l2request-copy (60 frames):"
timeout 90 mpv --hwdec=v4l2request-copy --vo=gpu --gpu-context=wayland --no-audio --frames=60 \
      --msg-level=all=info -- "$FILE" > "$T/mpv.log" 2>&1
rc=$?
if grep -qa 'Using hardware decoding' "$T/mpv.log"; then
  chk "hardware decoding used" 0
else
  chk "hardware decoding used (exit $rc, no 'Using hardware decoding' line)" 1
fi
grep -aE 'Using hardware decoding|Using software decoding' "$T/mpv.log" | head -2 | sed 's/^/        /'

echo
echo "mpv --hwdec=auto-safe zero-copy (60 frames, what the image ships):"
timeout 90 mpv --hwdec=auto-safe --vo=gpu --gpu-context=wayland --no-audio --frames=60 \
      --msg-level=all=v -- "$FILE" > "$T/mpv-zerocopy.log" 2>&1
if grep -qa 'Using hardware decoding (drm' "$T/mpv-zerocopy.log" \
   && grep -qa 'dmabuf interop' "$T/mpv-zerocopy.log"; then
  chk "mpv renders zero-copy (drmprime EGL dmabuf interop)" 0
else
  chk "mpv renders zero-copy (drmprime EGL dmabuf interop)" 1
fi
grep -aE 'Using hardware decoding|dmabuf interop|Using software decoding' "$T/mpv-zerocopy.log" \
  | head -3 | sed 's/^/        /'

# A picture whose width is not a multiple of 64 is the case the driver's
# 64-byte stride exists for: Mali only imports linear surfaces whose stride
# and plane offsets are 64-byte aligned, so a 16-byte stride leaves panfrost
# refusing every frame ("rejecting image due to unsupported offset or stride
# alignment") and the video area blue. See docs/video-decode.md.
echo
echo "zero-copy at an unaligned width (416):"
ODD="$T/odd416.mp4"
if ffmpeg -hide_banner -nostdin -v error -f lavfi -i testsrc2=size=416x234:rate=24 \
       -t 1 -c:v libx264 -pix_fmt yuv420p "$ODD" -y 2>/dev/null && [ -s "$ODD" ]; then
  timeout 90 mpv --hwdec=drm --vo=gpu --gpu-context=wayland --no-audio --frames=30 \
        --msg-level=all=info -- "$ODD" > "$T/mpv-odd.log" 2>&1
  grep -qa 'Using hardware decoding (drm' "$T/mpv-odd.log" \
    && chk "416-wide file decodes on the VPU" 0 \
    || chk "416-wide file decodes on the VPU" 1
  if grep -qaE 'rejecting image due to unsupported offset|Mapping hardware decoded surface failed' \
       "$T/mpv-odd.log"; then
    chk "panfrost imports the 416-wide frame (64-byte stride)" 1
    grep -aoE 'rejecting image due to unsupported offset or stride alignment|Mapping hardware decoded surface failed' \
      "$T/mpv-odd.log" | sort -u | head -2 | sed 's/^/        /'
  else
    chk "panfrost imports the 416-wide frame (64-byte stride)" 0
  fi
else
  echo "  skip  416-wide check (no libx264 to make the test file)"
fi

# VP9: the VPU now has a VP9 backend (out-of-tree series, docs/video-decode.md).
# Decode a clip twice, once through the VPU and once in software, and require
# the first 10 frames to be bit-identical: "decodes with no errors" alone has
# already passed on frames that were visually wrong.
#
# The clip is generated at 416 wide when none is present. Widths that are not a
# multiple of 64 are the case that was broken until the backend derived its
# reference stride from the capture surface: key frames decoded, every inter
# frame read its references with the wrong stride.
vp9_check() {
	local f=$1 label=$2
	local wh pix_fmt raw_fmt psnr rc
	wh=$(ffprobe -v error -select_streams v:0 -show_entries stream=width,height -of csv=p=0:s=x "$f")
	pix_fmt=$(ffprobe -v error -select_streams v:0 -show_entries stream=pix_fmt -of csv=p=0 "$f")
	case "$pix_fmt" in
		yuv420p) raw_fmt=nv12 ;;
		yuv420p10le) raw_fmt=p010le ;;
		*) chk "VP9 $label has supported pixel format ($pix_fmt)" 1; return ;;
	esac
	timeout 120 ffmpeg -hide_banner -nostdin -v verbose -hwaccel v4l2request \
		-hwaccel_output_format drm_prime -i "$f" -frames:v 10 \
		-vf "hwdownload,format=$raw_fmt" -f rawvideo "$T/vp9-hw.yuv" -y > "$T/vp9-hw.log" 2>&1
	rc=$?
	grep -qa 'Using V4L2 media driver cedrus' "$T/vp9-hw.log" \
		&& chk "VP9 $label goes through the VPU (cedrus)" 0 \
		|| chk "VP9 $label goes through the VPU (cedrus)" 1
	[ $rc -eq 0 ] && chk "VP9 $label decodes without crashing (exit 0)" 0 \
		|| chk "VP9 $label decodes without crashing (exit $rc)" 1
	if [ $rc -ne 0 ]; then
		tail -20 "$T/vp9-hw.log" | sed 's/^/        /'
	fi
	timeout 120 ffmpeg -hide_banner -nostdin -v error -i "$f" -frames:v 10 \
		-pix_fmt "$raw_fmt" -f rawvideo "$T/vp9-sw.yuv" -y >/dev/null 2>&1
	psnr=$(ffmpeg -hide_banner -nostdin -f rawvideo -pix_fmt "$raw_fmt" -s "$wh" -i "$T/vp9-hw.yuv" \
		-f rawvideo -pix_fmt "$raw_fmt" -s "$wh" -i "$T/vp9-sw.yuv" -lavfi psnr -f null - 2>&1 \
		| grep -o 'average:[^ ]*' | head -1)
	case "$psnr" in
	average:inf|average:infinity*)
		chk "VP9 $label matches software ($psnr)" 0 ;;
	average:*)
		awk -v a="${psnr#average:}" 'BEGIN { exit !(a + 0 >= 35) }' \
			&& chk "VP9 $label matches software ($psnr, >= 35 dB)" 0 \
			|| chk "VP9 $label matches software ($psnr, below 35 dB)" 1 ;;
	*)
		chk "VP9 $label matches software (no PSNR measured)" 1 ;;
	esac
}

echo
echo "VP9 hardware decode (10 frames, compared against software):"
VP9F=""; VP9ODD=""
for f in "$HOME"/Downloads/*vp9*.mkv "$HOME"/Downloads/*vp9*.webm "$HOME"/Videos/*vp9*.mkv; do
	[ -r "$f" ] || continue
	[ "$(ffprobe -v error -select_streams v:0 -show_entries stream=codec_name -of csv=p=0 "$f" 2>/dev/null)" = vp9 ] || continue
	w=$(ffprobe -v error -select_streams v:0 -show_entries stream=width -of csv=p=0 "$f" 2>/dev/null)
	if [ -z "$VP9F" ]; then
		VP9F="$f"
	elif [ -z "$VP9ODD" ] && [ $((w % 64)) -ne 0 ]; then
		VP9ODD="$f"
	fi
done
if [ -z "$VP9F" ] && ffmpeg -hide_banner -encoders 2>/dev/null | grep -qw libvpx-vp9; then
	GEN8="$T/vp9-640x360.mkv"; GEN10="$T/vp9-416x240-10.mkv"
	timeout 180 ffmpeg -hide_banner -v error -f lavfi -i testsrc2=s=640x360:r=24 -t 2 \
		-c:v libvpx-vp9 -b:v 800k -pix_fmt yuv420p "$GEN8" -y >/dev/null 2>&1
	timeout 180 ffmpeg -hide_banner -v error -f lavfi -i testsrc2=s=416x240:r=24 -t 2 \
		-c:v libvpx-vp9 -b:v 500k -pix_fmt yuv420p10le "$GEN10" -y >/dev/null 2>&1
	[ -s "$GEN8" ] && VP9F="$GEN8"
	[ -s "$GEN10" ] && VP9ODD="$GEN10"
fi
if [ -n "$VP9F" ]; then
	vp9_check "$VP9F" ""
	if [ -n "$VP9ODD" ]; then
		vp9_check "$VP9ODD" "at $(( $(ffprobe -v error -select_streams v:0 -show_entries stream=width -of csv=p=0 "$VP9ODD") % 64 ))-off-64 width"
	else
		echo "  skip  VP9 width-not-multiple-of-64 check (no such clip)"
	fi
else
	echo "  skip  VP9 check (no test clip and libvpx-vp9 not available)"
fi

echo
[ $fail -eq 0 ] && echo "RESULT: VPU path OK" || echo "RESULT: VPU path NOT working (see docs/video-decode.md)"
exit $fail
