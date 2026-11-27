#!/bin/bash
# Check FFmpeg's build inputs against the latest recorded package version.
#   tools/ffmpeg-inputs.sh            check (run by CI)
#   tools/ffmpeg-inputs.sh --update   append a record for a newer package version
set -euo pipefail
source "$(dirname "$(realpath "$0")")/../build/config.sh"
cd "$TOP"
REC=build/pkg/ffmpeg-inputs.txt
version=$FFMPEG_HANDTOP_VERSION
[[ $# -eq 0 || ($# -eq 1 && $1 = --update) ]] || die "usage: $0 [--update]"
version_pattern='[^[:space:]]+[+]handtop[1-9][0-9]*'
[[ $version =~ ^$version_pattern$ ]] || die "invalid Handtop FFmpeg package version: $version"
dpkg --validate-version "$version" || die "invalid FFmpeg package version: $version"

# Lock the directory so another updater can't read stale history across the final rename.
if [[ $# -eq 1 ]]; then
  exec 9<build/pkg
  flock -x -w 10 9 || die "could not lock FFmpeg input history"
fi
mapfile -t history < "$REC"
row="^($version_pattern)[[:blank:]]+([0-9a-f]{64})$"
last_version=
last_sum=
for line in "${history[@]}"; do
  [[ -z $line || $line = \#* ]] && continue
  [[ $line =~ $row ]] || die "$REC contains a malformed record: $line"
  rec_version=${BASH_REMATCH[1]}
  rec_sum=${BASH_REMATCH[2]}
  dpkg --validate-version "$rec_version" || die "$REC contains an invalid version: $rec_version"
  if [[ -n $last_version ]]; then
    dpkg --compare-versions "$rec_version" gt "$last_version" \
      || die "$REC versions must increase ($last_version -> $rec_version)"
  fi
  last_version=$rec_version
  last_sum=$rec_sum
done
[[ -n $last_version ]] || die "$REC has no FFmpeg input records"

# The source and all reference .debs use the same Debian version pin.
# Hash raw file bytes because a comment-looking line can be data in a heredoc or string.
sum=$(
  {
    printf '%s\0' "$FFMPEG_VERSION" "$FFMPEG_DEBIAN_VERSION" "$KWIBOO_URL" \
      "$KWIBOO_BASE" "$KWIBOO_PIN" "$KWIBOO_COMMITS"
    sha256sum build/patches/ffmpeg-v4l2request-drm.patch build/04c-v4l2-ffmpeg.sh \
      build/pkg/build-ffmpeg-debs.py build/pkg/ffmpeg-paths.py
  } | sha256sum
)
sum=${sum%% *}

if dpkg --compare-versions "$version" eq "$last_version"; then
  [[ $version = "$last_version" && $sum = "$last_sum" ]] \
    || die "FFmpeg inputs differ for already recorded version $last_version. Raise FFMPEG_HANDTOP_REV."
  echo "FFmpeg build inputs unchanged ($version)"
  exit 0
fi
dpkg --compare-versions "$version" gt "$last_version" \
  || die "FFmpeg package version $version is older than $last_version"
[[ $# -eq 1 ]] || die "Run tools/ffmpeg-inputs.sh --update to record FFmpeg package version $version."

# Write the new history beside the old one so a failed write cannot leave a partial record.
tmp=$(mktemp "$REC.XXXXXX")
trap 'rm -f -- "$tmp"' EXIT
printf '%s\n' "${history[@]}" "$version $sum" > "$tmp"
chmod --reference="$REC" "$tmp"
mv -fT -- "$tmp" "$REC"
echo "recorded: $version, inputs $sum"
