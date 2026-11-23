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
echo "Update app installed."
