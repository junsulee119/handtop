"""The built-in Grayscale theme (handtop-grayscale): Handtop dark with every colour and image
turned grey (luma, Rec. 601: 0.299 R + 0.587 G + 0.114 B; transparency kept), so contrast and
shapes stay as in Handtop dark.

Writes src/theme/themes/handtop-grayscale/ (theme.json, icons/, images/wallpaper.png) from
handtop-dark as the image build assembles it (src/theme/handtop_theme/builtin.py). Run from the
repo root after changing Handtop dark's colours or any of its images:

    python3 tools/icons/gen_grayscale.py

Needs Pillow (like the other generators here)."""
import json
import os
import sys
import tempfile
from collections import OrderedDict

from PIL import Image

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(REPO, "src", "theme"))
from handtop_theme import builtin, theme  # noqa: E402
from handtop_theme import schema as S  # noqa: E402

OUT = os.path.join(REPO, "src", "theme", "themes", "handtop-grayscale")


def grey(c):
    """'#rrggbb[aa]' -> the same luma as grey, alpha kept."""
    if c is None:
        return None
    v = [int(c[i:i + 2], 16) for i in range(1, len(c), 2)]
    y = round(0.299 * v[0] + 0.587 * v[1] + 0.114 * v[2])
    return "#%02x%02x%02x" % (y, y, y) + ("%02x" % v[3] if len(v) == 4 else "")


def grey_png(src, dst):
    im = Image.open(src).convert("RGBA")
    r, g, b, a = im.split()
    y = Image.merge("RGB", (r, g, b)).convert("L")     # Pillow's L is Rec. 601 luma
    Image.merge("LA", (y, a)).save(dst, optimize=True)


def main():
    with tempfile.TemporaryDirectory() as tmp:
        builtin.assemble(REPO, tmp)
        dark = theme.load(os.path.join(tmp, "handtop-dark"), tmp)
        if dark.errors:
            sys.exit(f"handtop-dark has errors: {dark.errors}")
        with open(os.path.join(tmp, "handtop-dark", S.THEME_FILE)) as f:
            data = json.load(f, object_pairs_hook=OrderedDict)
        n = 0
        for slot in sorted(dark.own):
            dst = os.path.join(OUT, S.slot_file(slot))
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            grey_png(dark.images[slot][1], dst)
            n += 1
        os.makedirs(os.path.join(OUT, "images"), exist_ok=True)
        grey_png(dark.wallpaper["image"], os.path.join(OUT, S.WALLPAPER_FILE))
    data["id"], data["name"] = "handtop-grayscale", "Grayscale"
    data["description"] = "Handtop dark in shades of grey, colours and icons alike."
    data["palette"] = OrderedDict((k, grey(v)) for k, v in data["palette"].items())
    data["colors"] = OrderedDict((k, grey(v)) for k, v in data["colors"].items())
    data["wallpaper"]["color"] = grey(data["wallpaper"]["color"])
    with open(os.path.join(OUT, S.THEME_FILE), "w") as f:
        json.dump(data, f, indent=2)
        f.write("\n")
    print(f"{OUT}: {n} images, wallpaper, theme.json")


if __name__ == "__main__":
    main()
