#!/bin/bash
# Theme system (src/theme, docs/apps/theme.md): run its tests, install the code rg35xxh-theme
# uses, and assemble the built-in themes (handtop-dark, handtop-light) from their theme.json and
# the overlay's pixel art. Needs python3 with pytest on the host (00-host-deps.sh).
set -euo pipefail
source "$(dirname "$(realpath "$0")")/config.sh"
assert_rootfs
cd "$TOP"
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider src/theme/tests

# The code, owned by root (as 08-input.sh does for the input daemon).
LIB="$ROOTFS/usr/local/lib/rg35xxh-theme"
[ -e "$LIB" ] && safe_rm -r "$LIB"
mkdir -p "$LIB"
rsync -a --chown=root:root --chmod=D755,F644 --exclude __pycache__ "$TOP/src/theme/handtop_theme" "$LIB/"

# The built-in themes, unpacked, then loaded once to be sure they are complete.
THEMES="$ROOTFS/usr/share/rg35xxh/themes"
[ -e "$THEMES" ] && safe_rm -r "$THEMES"
mkdir -p "$THEMES"
PYTHONDONTWRITEBYTECODE=1 python3 - "$TOP" "$THEMES" <<'PY'
import sys
sys.path.insert(0, sys.argv[1] + "/src/theme")
from handtop_theme import builtin, theme
for path in builtin.assemble(sys.argv[1], sys.argv[2]):
    t = theme.load(path, sys.argv[2])
    if t.problems:
        sys.exit(f"{path}: {t.problems}")
    print(f"built-in theme {t.id}: {len(t.own)} images")
PY
chown -R root:root "$THEMES"
chmod -R u=rwX,go=rX "$THEMES"

# Handtop's apps name their icons (Icon=rg35xxh-theme, ...); the current theme's icon theme
# (Handtop-Current, linked at the first log-in) serves them. Handtop dark's copies in hicolor keep
# them visible should the theme not be rendered.
H="$ROOTFS/usr/local/share/icons/hicolor/scalable/apps"
mkdir -p "$H"
for a in theme:app-theme external-controller:app-external-controller display:app-display \
         enable-ssh:app-ssh recenter-sticks:app-recenter; do
  install -m644 "$TOP/overlay/usr/local/share/rg35xxh/icons/${a#*:}.png" "$H/rg35xxh-${a%%:*}.png"
done
echo "Theme system installed."
