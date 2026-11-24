#!/bin/bash
# Install the Update app's code (src/update, docs/apps/update.md) into the rootfs after running its
# unit tests. Its launcher, .desktop file and the taskbar badge come with the overlay; the privileged
# side is the update worker (overlay/usr/local/sbin/handtop-update, docs/services/update.md).
set -euo pipefail
source "$(dirname "$(realpath "$0")")/config.sh"
assert_rootfs
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider "$TOP/src/update/tests"
DEST="$ROOTFS/usr/local/lib/rg35xxh-update"
[ -e "$DEST" ] && safe_rm -r "$DEST"
mkdir -p "$DEST"
rsync -a --chown=root:root --chmod=D755,F644 --exclude __pycache__ "$TOP/src/update/handtop_update" "$DEST/"
# The boot partition's files as the image writes them (10-image.sh), for cards moved onto packages:
# the update worker's migrate plan adds recovery.txt and replaces v0.4.0's active input file.
T="$ROOTFS/usr/local/share/handtop/boot"
mkdir -p "$T"
sed 's/\r*$/\r/' "$TOP/boot-files/recovery.txt" > "$T/recovery.txt"
python3 "$TOP/tools/boot-input-conf.py" "$TOP/overlay/etc/rg35xxh/input.conf" | sed 's/$/\r/' > "$T/rg35xxh-input.conf"
grep -q '^\[rescue\]' "$T/rg35xxh-input.conf" || die "rg35xxh-input.conf: template failed"
chmod 644 "$T"/*
echo "Update app installed."
