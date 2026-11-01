#!/bin/bash
# Check the VA-API driver on a device (docs/video-decode.md, "VA-API").
#
# An image built with build/04e-va-api.sh already carries the driver; these
# checks are for an image built before that step, or for a freshly built .so.
#
#   DEVICE=user@host tools/test-va-v4l2request.sh install   # copy the built .so over
#   DEVICE=user@host tools/test-va-v4l2request.sh info      # vainfo: H264/HEVC profiles
#
# install needs root on the device: passwordless sudo, or SUDO_PW=<password>.
# The artifact comes from: sudo tools/build-va-v4l2request.sh
set -euo pipefail
TOP="$(cd "$(dirname "$(realpath "${BASH_SOURCE[0]}")")/.." && pwd)"
SO="$TOP/work/va-driver/v4l2_request_drv_video.so"
DEST=/usr/lib/aarch64-linux-gnu/dri/v4l2_request_drv_video.so
DEVICE="${DEVICE:-}"
need_device() { [ -n "$DEVICE" ] || { echo "set DEVICE=user@host"; exit 1; }; }
WENV='export XDG_RUNTIME_DIR=/run/user/$(id -u) WAYLAND_DISPLAY=wayland-0'

run() { ssh "$DEVICE" "$@"; }

case "${1:-}" in
install)
  need_device
  [ -f "$SO" ] || { echo "missing $SO — run: sudo tools/build-va-v4l2request.sh"; exit 1; }
  scp -q "$SO" "$DEVICE:/tmp/v4l2_request_drv_video.so"
  run "if [ -n '${SUDO_PW:-}' ]; then echo '$SUDO_PW' | sudo -S install -m755 /tmp/v4l2_request_drv_video.so $DEST && echo '$SUDO_PW' | sudo -S ldconfig; else sudo -n install -m755 /tmp/v4l2_request_drv_video.so $DEST && sudo -n ldconfig; fi; rm -f /tmp/v4l2_request_drv_video.so"
  run "ls -l $DEST"
  ;;
info)
  need_device
  run "LIBVA_DRIVER_NAME=v4l2_request vainfo --display drm --device /dev/dri/renderD128" \
    | grep -E "Driver version|VAProfile(H264|HEVC)" \
    || { echo "no H264/HEVC profiles: the driver is not engaging"; exit 1; }
  echo "profiles OK"
  ;;
play)
  need_device
  # one file, both players, CPU of one core over 10 s (this is the number the
  # docs quote; see "Performance" there for what to expect)
  FILE="${2:?usage: $0 play <file on the device>}"
  for cmd in \
    "mpv --hwdec=drm --no-audio --vo=gpu $FILE" \
    "env LIBVA_DRIVER_NAME=v4l2_request DISPLAY=:0 vlc --avcodec-hw=vaapi -I dummy --play-and-exit $FILE"; do
    echo "== $cmd"
    run "timeout 10 $cmd >/dev/null 2>&1 & p=\$!; sleep 4; \
         t0=\$(awk '{print \$14+\$15}' /proc/\$p/stat 2>/dev/null || echo 0); sleep 6; \
         t1=\$(awk '{print \$14+\$15}' /proc/\$p/stat 2>/dev/null || echo 0); \
         echo \"cpu: \$(( (t1-t0) * 100 / 6 / 100 ))% of one core over 6 s\"; wait \$p 2>/dev/null"
  done
  ;;
*)
  sed -n '2,12p' "$0" | sed 's/^# \{0,1\}//'
  exit 1
  ;;
esac
