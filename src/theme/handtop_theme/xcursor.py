"""A theme's own pointer as an Xcursor set (no xcursorgen needed; same format as
tools/icons/gen_cursors.py writes for Handtop's pointer).

Each shape is drawn at 48x48; the set holds that (nominal size 48) and a 24 px copy (nominal
24), so XCURSOR_SIZE 24 and 48 are both exact. Shapes the theme does not draw come from Handtop's
pointer (index.theme Inherits=Handtop)."""
import os
import struct

from . import schema as S

MARK = ".handtop-theme-pointer"     # in every set this module writes (only those are ever removed)


def chunk(argb, w, h, nominal, hx, hy):
    """argb: w*h premultiplied ARGB pixels as 32-bit ints, rows top to bottom."""
    return struct.pack("<9I", 36, 0xfffd0002, nominal, 1, w, h, hx, hy, 0) + struct.pack(f"<{w * h}I", *argb)


def xcursor(images):
    """images: [(nominal, chunk bytes)] -> Xcursor file bytes."""
    head = 16 + 12 * len(images)
    out, toc, pos = [], [], head
    for nominal, c in images:
        toc.append(struct.pack("<3I", 0xfffd0002, nominal, pos))
        out.append(c)
        pos += len(c)
    return struct.pack("<4sIII", b"Xcur", 16, 0x10000, len(images)) + b"".join(toc) + b"".join(out)


def write_set(theme, dest, ops):
    """Write theme's pointer set (index.theme, cursors/) into the folder dest (created)."""
    os.makedirs(os.path.join(dest, "cursors"), exist_ok=True)
    with open(os.path.join(dest, "index.theme"), "w") as f:
        f.write(f"[Icon Theme]\nName={S.CURSOR_SET_PREFIX}{theme.id}\n"
                f"Comment=Pointer of the Handtop theme {theme.id} (rg35xxh-theme)\nInherits=Handtop\n")
    open(os.path.join(dest, MARK), "w").close()
    big = S.CURSOR_ART
    for shape, path in theme.cursor_images.items():
        hx, hy = theme.cursor["hotspots"][shape]
        images = []
        for size in (big // 2, big):
            argb = ops.argb(path, size)
            images.append((size, chunk(argb, size, size, size, hx * size // big, hy * size // big)))
        blob = xcursor(images)
        for name in S.CURSOR_SHAPES[shape][0]:
            with open(os.path.join(dest, "cursors", name), "wb") as f:
                f.write(blob)
