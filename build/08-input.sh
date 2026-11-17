#!/bin/bash
# Install the input daemon (src/inputd) into the rootfs after running its unit tests.
set -euo pipefail
source "$(dirname "$(realpath "$0")")/config.sh"
assert_rootfs
PYTHONDONTWRITEBYTECODE=1 python3 "$TOP/src/inputd/tests/test_core.py"
DEST="$ROOTFS/usr/local/lib/rg35xxh-inputd"
[ -e "$DEST" ] && safe_rm -r "$DEST"
mkdir -p "$DEST"
# Owned by root like every other system file (as 05-configure-base.sh does for the overlay):
# plain -a kept the checkout's owner, and the build host's user has uid 1000 = the device's
# rg, so the daemon's code ended up writable by the desktop user.
rsync -a --chown=root:root --chmod=D755,F644 --exclude __pycache__ "$TOP/src/inputd/rg35xxh_inputd" "$DEST/"
# The Controls app's code (src/controls), next to it: it reads the daemon's config module.
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider "$TOP/src/controls/tests"
CDEST="$ROOTFS/usr/local/lib/rg35xxh-controls"
[ -e "$CDEST" ] && safe_rm -r "$CDEST"
mkdir -p "$CDEST"
rsync -a --chown=root:root --chmod=D755,F644 --exclude __pycache__ "$TOP/src/controls/handtop_controls" "$CDEST/"
echo "Input daemon and Controls app installed."
