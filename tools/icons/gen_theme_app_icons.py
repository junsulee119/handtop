"""Import / export icons for the Theme app's header (pixel art, one colour): a tray with an arrow
coming down into it (import) and an open box with an arrow going up out of it (export, the
familiar "share" shape). 12x12 art doubled = 24 px, white on transparent: the app paints them in
its text colour, so one file serves every theme.

    python3 tools/icons/gen_theme_app_icons.py overlay/usr/local/share/rg35xxh/icons
writes ui-import.png and ui-export.png. Needs Pillow."""
import os
import sys

from PIL import Image

# Arrowheads are drawn with 2-pixel strokes like the shafts (1-pixel diagonals looked thin).
IMPORT = [
    ".....##.....",
    ".....##.....",
    ".....##.....",
    ".##..##..##.",
    "..##.##.##..",
    "...######...",
    "....####....",
    ".....##.....",
    "##........##",
    "##........##",
    "############",
    "############",
]
EXPORT = [
    ".....##.....",
    "....####....",
    "...######...",
    "..##.##.##..",
    ".##..##..##.",
    ".....##.....",
    "###..##..###",
    "##........##",
    "##........##",
    "##........##",
    "############",
    "############",
]


def draw(art, z=2):
    im = Image.new("RGBA", (len(art[0]) * z, len(art) * z), (0, 0, 0, 0))
    for y, row in enumerate(art):
        for x, ch in enumerate(row):
            if ch == "#":
                for dy in range(z):
                    for dx in range(z):
                        im.putpixel((x * z + dx, y * z + dy), (255, 255, 255, 255))
    return im


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "."
    for name, art in (("ui-import", IMPORT), ("ui-export", EXPORT)):
        draw(art).save(os.path.join(out, f"{name}.png"), optimize=True)
        print(os.path.join(out, f"{name}.png"))
