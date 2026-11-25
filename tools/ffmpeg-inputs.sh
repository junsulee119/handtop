#!/bin/bash
# Checks that Handtop's FFmpeg build gets a new version when what it is built from changes
# (review 2026-11-19 #22): build/pkg/ffmpeg-inputs.txt records FFMPEG_HANDTOP_REV and a checksum of the
# inputs (Debian's version, the patchset pin, our patch, 04c and the packaging script; comment lines
# don't count). Run by tools/ci-checks.sh.
#   tools/ffmpeg-inputs.sh            check (exit 1 when the inputs changed but the rev didn't)
#   tools/ffmpeg-inputs.sh --update   record the current inputs (after raising FFMPEG_HANDTOP_REV)
set -euo pipefail
TOP=$(cd "$(dirname "$(realpath "$0")")/.." && pwd)
# shellcheck source=/dev/null
. "$TOP/build/config.sh"
REC="$TOP/build/pkg/ffmpeg-inputs.txt"
sum=$( {
  printf '%s\n' "$FFMPEG_DEBIAN_VERSION" "$KWIBOO_BASE" "$KWIBOO_PIN"
  cat "$TOP/build/patches/ffmpeg-v4l2request-drm.patch"
  grep -hv '^[[:space:]]*#' "$TOP/build/04c-v4l2-ffmpeg.sh" "$TOP/build/pkg/build-ffmpeg-debs.py"
} | sha256sum | cut -d' ' -f1)
if [ "${1:-}" = --update ]; then
  printf 'rev=%s\ninputs=%s\n' "$FFMPEG_HANDTOP_REV" "$sum" > "$REC"
  echo "recorded: rev $FFMPEG_HANDTOP_REV, inputs $sum"
  exit 0
fi
rec_rev=$(sed -n 's/^rev=//p' "$REC"); rec_sum=$(sed -n 's/^inputs=//p' "$REC")
if [ "$sum" = "$rec_sum" ] && [ "$FFMPEG_HANDTOP_REV" = "$rec_rev" ]; then
  echo "FFmpeg build inputs unchanged (rev $FFMPEG_HANDTOP_REV)"
elif [ "$sum" != "$rec_sum" ] && [ "$FFMPEG_HANDTOP_REV" = "$rec_rev" ]; then
  echo "FFmpeg build inputs changed but FFMPEG_HANDTOP_REV is still $rec_rev: raise it in build/config.sh" \
       "(or reset it to 1 with a new FFMPEG_DEBIAN_VERSION), then tools/ffmpeg-inputs.sh --update" >&2
  exit 1
else
  echo "FFMPEG_HANDTOP_REV changed ($rec_rev -> $FFMPEG_HANDTOP_REV): record it with tools/ffmpeg-inputs.sh --update" >&2
  exit 1
fi
