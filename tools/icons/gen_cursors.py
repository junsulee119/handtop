"""The Handtop cursor theme (pixel art, Xcursor format, no xcursorgen needed).

Soft white with a 1 px dark outline and a darker lowest pixel per column (like the other Handtop
pixel art); the busy hourglass has amber sand. The same set works on the dark and the light theme.
The pointer is the arrow from the logo (gen_logo.py).

Shapes and the cursor names written for them (plain copies, no symlinks, so a Windows checkout
keeps them):
  arrow     left_ptr default arrow top_left_arrow
  hand      hand2 hand1 pointer
  text      xterm text ibeam
  busy      watch wait
  progress  left_ptr_watch progress (arrow + small hourglass)
Two nominal sizes per file: 24 (art 1x) and 48 (2x, for big screens). Every other cursor name
comes from Adwaita (index.theme Inherits).

Usage: python3 tools/icons/gen_cursors.py <icons folder>   (overlay/usr/share/icons; libwayland-cursor
       does not search /usr/local/share/icons)
"""
import os
import struct
import sys

ARROW = ["O..........", "OO.........", "OWO........", "OWWO.......", "OWWWO......", "OWWWWO.....",
         "OWWWWWO....", "OWWWWWWO...", "OWWWWWWWO..", "OWWWWWWWWO.", "OWWWWWOOOOO", "OWWOWWO....",
         "OWO.OWWO...", "OO..OWWO...", "O....OWWO..", ".....OWWO..", "......OO..."]
HAND = ["....OO.........", "...OWWO........", "...OWWO........", "...OWWO........", "...OWWOOO......",
        "...OWWOWWOOO...", ".OOOWWOWWOWWOO.", "OWWOWWWWWWWWWO.", "OWWWWWWWWWWWWO.", ".OWWWWWWWWWWWO.",
        "..OWWWWWWWWWWO.", "..OWWWWWWWWWO..", "...OWWWWWWWWO..", "...OWWWWWWWO...", "....OWWWWWWO...",
        "....OOOOOOOO..."]
IBEAM = ["OOO.OOO", "OWWOWWO", "OOOWOOO"] + ["..OWO.."] * 10 + ["OOOWOOO", "OWWOWWO", "OOO.OOO"]
BUSY = ["OOOOOOOOOOO", "OWWWWWWWWWO", "OOOOOOOOOOO", ".OWWWWWWWO.", ".OWAAAAAWO.", "..OWAAAWO..",
        "...OWAWO...", "....OWO....", "...OWWWO...", "..OWWAWWO..", ".OWWAAAWWO.", ".OWAAAAAWO.",
        "OOOOOOOOOOO", "OWWWWWWWWWO", "OOOOOOOOOOO"]
MINI_BUSY = ["OOOOOOO", "OWWWWWO", ".OAAAO.", "..OAO..", ".OWAWO.", "OWAAAWO", "OOOOOOO"]

COLS = {"W": (232, 234, 238), "O": (16, 20, 28), "A": (255, 210, 143)}
SHADE = (170, 179, 194)

# shape: (art, hotspot x, y), extra art pasted at an offset
SHAPES = {
    "arrow": (ARROW, 0, 0, None),
    "hand": (HAND, 5, 1, None),
    "text": (IBEAM, 3, 7, None),
    "busy": (BUSY, 5, 7, None),
    "progress": (ARROW, 0, 0, (MINI_BUSY, 9, 12)),
}
NAMES = {"arrow": ["left_ptr", "default", "arrow", "top_left_arrow"],
         "hand": ["hand2", "hand1", "pointer"],
         "text": ["xterm", "text", "ibeam"],
         "busy": ["watch", "wait"],
         "progress": ["left_ptr_watch", "progress"]}


def pixels(art, extra, canvas=24):
    """canvas x canvas ARGB (premultiplied, all opaque or clear) at 1x."""
    grid = {}

    def put(rows, ox, oy):
        low = {}
        for y, r in enumerate(rows):
            for x, c in enumerate(r):
                if c == "W":
                    low[x] = y
        for y, r in enumerate(rows):
            for x, c in enumerate(r):
                if c != ".":
                    grid[(ox + x, oy + y)] = SHADE if c == "W" and low[x] == y else COLS[c]
    put(art, 0, 0)
    if extra:
        put(*extra)
    return [[grid.get((x, y)) for x in range(canvas)] for y in range(canvas)]


def scaled(px, z):
    return [[px[y // z][x // z] for x in range(len(px[0]) * z)] for y in range(len(px) * z)]


def chunk(px, nominal, hx, hy):
    h, w = len(px), len(px[0])
    data = b"".join(struct.pack("<I", 0 if p is None else (0xff << 24 | p[0] << 16 | p[1] << 8 | p[2]))
                    for row in px for p in row)
    return struct.pack("<9I", 36, 0xfffd0002, nominal, 1, w, h, hx, hy, 0) + data


def xcursor(images):
    """images: [(nominal, chunk bytes)] -> Xcursor file bytes."""
    head = 16 + 12 * len(images)
    out, toc, pos = [], [], head
    for nominal, c in images:
        toc.append(struct.pack("<3I", 0xfffd0002, nominal, pos))
        out.append(c)
        pos += len(c)
    return struct.pack("<4sIII", b"Xcur", 16, 0x10000, len(images)) + b"".join(toc) + b"".join(out)


if __name__ == "__main__":
    root = sys.argv[1] if len(sys.argv) > 1 else "."
    d = f"{root}/Handtop/cursors"
    os.makedirs(d, exist_ok=True)
    with open(f"{root}/Handtop/index.theme", "w") as f:
        f.write("[Icon Theme]\nName=Handtop\nComment=Handtop pixel-art cursors (tools/icons/gen_cursors.py)\n"
                "Inherits=Adwaita\n")
    for shape, (art, hx, hy, extra) in SHAPES.items():
        px = pixels(art, extra)
        blob = xcursor([(24, chunk(px, 24, hx, hy)), (48, chunk(scaled(px, 2), 48, hx * 2, hy * 2))])
        for name in NAMES[shape]:
            with open(f"{d}/{name}", "wb") as f:
                f.write(blob)
