"""The Handtop logo and the wallpapers built from it (pixel art).

Logo (48x48 art): an RG35XX H showing a little desktop (window + taskbar), a keyboard below it and
a big mouse pointer over both: a handheld used as a desktop. A 1 px dark outline around the whole
silhouette keeps it readable on light and dark backgrounds.

  media/logo/handtop-logo.png            48 px (1x)
  media/logo/handtop-logo-{192,384}.png  4x / 8x (nearest-neighbour)
  media/logo/handtop-logo.svg            one rect per pixel (scales sharp)
  media/logo/handtop-wordmark-{dark,light}.png  logo + "Handtop" in a pixel font ("top" in the
                                         accent blue), for dark / light pages (README)
  overlay/usr/local/share/rg35xxh/wallpaper-{dark,light}.png  640x480: the logo and wordmark
                                         carved into the theme's wallpaper colour (no colour of their
                                         own: light from the upper left, shadow on the upper-left inner
                                         edges, highlight on the lower-right ones, the shapes a shade
                                         darker), at 3x, centred above the taskbar (swaybg centres it,
                                         same colour around it on bigger screens)

Usage: python3 tools/icons/gen_logo.py   (from the repo root)
"""
import os

from PIL import Image

N = 48
C = {"W": (232, 234, 238), "w": (170, 179, 194), "D": (22, 26, 34), "S": (30, 36, 48), "T": (61, 90, 138),
     "K": (43, 50, 64), "q": (30, 35, 46), "k": (201, 206, 216), "c": (128, 137, 152), "g": (70, 78, 94),
     "x": (74, 140, 230), "a": (226, 70, 70), "b": (240, 200, 60), "y": (80, 190, 100), "O": (14, 17, 23)}
WALL = {"dark": (0x1e, 0x24, 0x30), "light": (0xdf, 0xe4, 0xec)}          # rg35xxh-themed swaybg colours
INK = {"dark": ((232, 234, 238), (143, 180, 255)), "light": ((43, 48, 59), (61, 104, 176))}


def rect(g, x0, y0, x1, y1, c, cut=False):
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            if cut and x in (x0, x1) and y in (y0, y1):
                continue                                   # rounded corner
            g[(x, y)] = c


def handheld(g, ox, oy):
    rect(g, ox, oy, ox + 39, oy + 21, "W", cut=True)
    for x in range(ox + 1, ox + 39):
        g[(x, oy + 21)] = "w"                              # bottom shade
    rect(g, ox + 9, oy + 2, ox + 30, oy + 18, "D")         # bezel
    rect(g, ox + 10, oy + 3, ox + 29, oy + 17, "S")        # screen: a desktop
    rect(g, ox + 10, oy + 16, ox + 29, oy + 17, "K")       # taskbar
    rect(g, ox + 10, oy + 16, ox + 12, oy + 17, "T")       # its Apps block
    rect(g, ox + 13, oy + 5, ox + 24, oy + 13, "k")        # a window
    rect(g, ox + 13, oy + 5, ox + 24, oy + 6, "T")         # its title bar
    cx, cy = ox + 4, oy + 6                                # D-pad
    rect(g, cx - 2, cy, cx + 2, cy, "g")
    rect(g, cx, cy - 2, cx, cy + 2, "g")
    fx, fy = ox + 35, oy + 6                               # X A B Y
    g[(fx, fy - 2)], g[(fx + 2, fy)], g[(fx, fy + 2)], g[(fx - 2, fy)] = "x", "a", "b", "y"
    for sx in (ox + 3, ox + 34):                           # sticks
        rect(g, sx, oy + 13, sx + 2, oy + 15, "c")
    g[(ox + 7, oy + 2)] = g[(ox + 32, oy + 2)] = "c"       # select / start


def keyboard(g, ox, oy, w=44):
    rect(g, ox, oy, ox + w - 1, oy + 11, "K", cut=True)
    for x in range(ox + 1, ox + w - 1):
        g[(x, oy + 11)] = "q"                              # bottom shade
    for r in range(3):                                     # staggered key rows
        for i in range((w - 3 - r) // 4):
            rect(g, ox + 2 + r + i * 4, oy + 2 + r * 3, ox + 4 + r + i * 4, oy + 3 + r * 3, "k")
    rect(g, ox + 12, oy + 10, ox + w - 13, oy + 10, "k")   # space bar


CURSOR = ["O..........", "OO.........", "OWO........", "OWWO.......", "OWWWO......", "OWWWWO.....",
          "OWWWWWO....", "OWWWWWWO...", "OWWWWWWWO..", "OWWWWWWWWO.", "OWWWWWOOOOO", "OWWOWWO....",
          "OWO.OWWO...", "OO..OWWO...", "O....OWWO..", ".....OWWO..", "......OO..."]


def logo():
    g = {}
    keyboard(g, 2, 33)
    handheld(g, 4, 7)
    for y, r in enumerate(CURSOR):
        for x, c in enumerate(r):
            if c != ".":
                g[(31 + x, 22 + y)] = c
    edge = {(x + dx, y + dy) for (x, y) in g for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))} - set(g)
    for p in edge:                                         # outline around the silhouette
        g[p] = "O"
    im = Image.new("RGBA", (N, N), (0, 0, 0, 0))
    for (x, y), c in g.items():
        if 0 <= x < N and 0 <= y < N:
            im.putpixel((x, y), C[c] + (255,))
    return im


# Pixel font for the wordmark: 5 wide, 9 tall (2 rows of descender for "p").
GLYPHS = {"H": ["#...#", "#...#", "#...#", "#####", "#...#", "#...#", "#...#", ".....", "....."],
          "a": [".....", ".....", ".###.", "....#", ".####", "#...#", ".####", ".....", "....."],
          "n": [".....", ".....", "####.", "#...#", "#...#", "#...#", "#...#", ".....", "....."],
          "d": ["....#", "....#", ".####", "#...#", "#...#", "#...#", ".####", ".....", "....."],
          "t": [".#...", ".#...", "####.", ".#...", ".#...", ".#..#", "..##.", ".....", "....."],
          "o": [".....", ".....", ".###.", "#...#", "#...#", "#...#", ".###.", ".....", "....."],
          "p": [".....", ".....", "####.", "#...#", "#...#", "#...#", "####.", "#....", "#...."]}


def wordmark_text(theme):
    ink, accent = INK[theme]
    w = 6 * 7 - 1
    im = Image.new("RGBA", (w, 9), (0, 0, 0, 0))
    for i, ch in enumerate("Handtop"):
        col = accent if i >= 4 else ink                    # "Hand" + "top" in the accent blue
        for y, row in enumerate(GLYPHS[ch]):
            for x, c in enumerate(row):
                if c == "#":
                    im.putpixel((i * 6 + x, y), col + (255,))
    return im


def _lum(p):
    return (0.299 * p[0] + 0.587 * p[1] + 0.114 * p[2]) / 255


def carve(im, bg, strength=0.10, inset=0.015, flat=False):
    """Engraving: each pixel = the background colour shifted by the brightness step from its
    upper-left neighbour (negated, so edges facing the light are in shadow: pressed in), and
    the shape itself a little darker. Done on the 1x art, scaled afterwards. flat: the shape is cut
    as one even step (its own colours ignored), so every letter of the wordmark is equally deep."""
    w, h, px, bl = im.width, im.height, im.load(), _lum(bg)
    L = [[(bl + 0.6 if flat else _lum(px[x, y])) if px[x, y][3] else bl for x in range(w)] for y in range(h)]
    get = lambda x, y: L[y][x] if 0 <= x < w and 0 <= y < h else bl  # noqa: E731
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    o = out.load()
    for y in range(h):
        for x in range(w):
            v = (get(x, y) - get(x - 1, y - 1)) * strength - (inset if px[x, y][3] else 0)
            if abs(v) >= 0.004:
                o[x, y] = tuple(max(0, min(255, round(bg[k] + v * 255))) for k in range(3)) + (255,)
    return out


def big(im, z):
    return im.resize((im.width * z, im.height * z), Image.NEAREST)


def svg(im):
    rects = []
    for y in range(im.height):
        for x in range(im.width):
            r, g, b, a = im.getpixel((x, y))
            if a:
                rects.append(f'<rect x="{x}" y="{y}" width="1" height="1" fill="#{r:02x}{g:02x}{b:02x}"/>')
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{im.width}" height="{im.height}" '
            f'viewBox="0 0 {im.width} {im.height}" shape-rendering="crispEdges">\n'
            '<!-- Handtop logo, pixel art 48x48 (tools/icons/gen_logo.py) -->\n' + "\n".join(rects) + "\n</svg>\n")


if __name__ == "__main__":
    os.makedirs("media/logo", exist_ok=True)
    L = logo()
    L.save("media/logo/handtop-logo.png")
    for z in (4, 8):
        big(L, z).save(f"media/logo/handtop-logo-{N * z}.png")
    open("media/logo/handtop-logo.svg", "w").write(svg(L))
    for theme in ("dark", "light"):
        t = big(wordmark_text(theme), 4)                   # wordmark: logo 4x + text 4x, side by side
        lg = big(L, 4)
        wm = Image.new("RGBA", (lg.width + 24 + t.width, lg.height), (0, 0, 0, 0))
        wm.paste(lg, (0, 0), lg)
        wm.paste(t, (lg.width + 24, (lg.height - 7 * 4) // 2), t)
        wm.save(f"media/logo/handtop-wordmark-{theme}.png")
        wall = Image.new("RGB", (640, 480), WALL[theme])   # wallpaper: carved logo 3x, wordmark below
        lg3 = big(carve(L, WALL[theme]), 3)
        t3 = big(carve(wordmark_text(theme), WALL[theme], flat=True), 3)
        top = (448 - (lg3.height + 14 + 7 * 3)) // 2       # centred in the area above the 32 px taskbar
        wall.paste(lg3, ((640 - lg3.width) // 2, top), lg3)
        wall.paste(t3, ((640 - t3.width) // 2, top + lg3.height + 14), t3)
        wall.save(f"overlay/usr/local/share/rg35xxh/wallpaper-{theme}.png")
