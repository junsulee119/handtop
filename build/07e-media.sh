#!/bin/bash
# Install the media apps' code (src/media: Videos and Music, docs/apps/videos.md and music.md)
# into the rootfs after running their unit tests. Their launchers, .desktop files and mpv's
# Handtop config come with the overlay.
set -euo pipefail
source "$(dirname "$(realpath "$0")")/config.sh"
assert_rootfs
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider "$TOP/src/media/tests"
DEST="$ROOTFS/usr/local/lib/rg35xxh-media"
[ -e "$DEST" ] && safe_rm -r "$DEST"
mkdir -p "$DEST"
rsync -a --chown=root:root --chmod=D755,F644 --exclude __pycache__ "$TOP/src/media/handtop_media" "$DEST/"
echo "Media apps installed."
