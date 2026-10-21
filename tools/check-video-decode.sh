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

echo
[ $fail -eq 0 ] && echo "RESULT: VPU path OK" || echo "RESULT: VPU path NOT working (see docs/video-decode.md)"
exit $fail
