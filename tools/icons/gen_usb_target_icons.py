"""External Controller app: the two halves of the USB cable card (23x23, shown at 2x). Just the
drawing on a transparent background, no glass frame (the half's button is the frame). Generic
pictures, no brand logos or console likenesses:

  usbtarget-pc[-light].png      Xbox (PC): a monitor on its stand and a keyboard.
  usbtarget-console[-light].png Switch: a TV on legs and a gamepad with the handheld's coloured
                                X/A/B/Y.

Dark set: white drawing (inks of gen_base.py). Light set: dark ink (gen_light.py).

Usage: python3 gen_usb_target_icons.py <icon folder>   (overlay/usr/local/share/rg35xxh/icons)
"""
import os
import sys

from PIL import Image

N = 23
PC = (4, """
WWWWWWWWWWWWWWWWW
WDDDDDDDDDDDDDDDW
WDDDDDDDDDDDgDDDW
WDDDDDDDDDDDDgDDW
WDDDDDDDDDDDDDDDW
WDDDDDDDDDDDDDDDW
WDDDDDDDDDDDDDDDW
WDDDDDDDDDDDDDDDW
WWWWWWWWWWWWWWWWW
.......WWW.......
.....WWWWWWW.....
.................
WWWWWWWWWWWWWWWWW
WKWKWKWKWKWKWKWKW
WWWWWWWWWWWWWWWWW
""")
CONSOLE = (4, """
WWWWWWWWWWWWWWWWW
WDDDDDDDDDDDDDDDW
WDDDDDDDDDDDgDDDW
WDDDDDDDDDDDDgDDW
WDDDDDDDDDDDDDDDW
WDDDDDDDDDDDDDDDW
WDDDDDDDDDDDDDDDW
WWWWWWWWWWWWWWWWW
.W.............W.
.................
..WWWWWWWWWWWWW..
.WWBWWWWWWWWxWWW.
.WBBBWWWWWWyWaWW.
.WWBWWWWWWWWbWWW.
..WWW.......WWW..
""")
ICONS = {"pc": PC, "console": CONSOLE}
WHITE, SHADE = "#e8eaee", "#aab3c2"                 # gen_base.py
INK, INK_SHADE = "#2b303b", "#4f5869"               # gen_light.py
COLORS = {"D": "#161a22", "g": "#464e5e", "K": "#3c4350",
          "x": "#4a8ce6", "a": "#e24646", "b": "#f0c83c", "y": "#50be64"}
COLORS_LIGHT = dict(COLORS, D="#cfd6e2", g="#f4f6fa", K="#8a93a3")


def rgb(h):
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))


def render(name, light):
    top, art = ICONS[name]
    im = Image.new("RGBA", (N, N), (0, 0, 0, 0))
    rows = art.strip("\n").split("\n")
    w = len(rows[0])
    assert all(len(r) == w for r in rows) and w % 2 == 1, name
    left = (N - w) // 2
    g = {(x + left, y + top): c for y, r in enumerate(rows) for x, c in enumerate(r) if c != "."}
    low = {}
    for (x, y), c in g.items():
        if c == "W":
            low[x] = max(low.get(x, -1), y)
    colors = COLORS_LIGHT if light else COLORS
    for (x, y), c in g.items():
        if c == "W":
            ink = (INK_SHADE if low[x] == y else INK) if light else (SHADE if low[x] == y else WHITE)
            im.putpixel((x, y), rgb(ink) + (255,))
        elif c != "B":                              # B: the D-pad, a hole (background shows through)
            im.putpixel((x, y), rgb(colors[c]) + (255,))
    return im


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "."
    for name in ICONS:
        for light in (False, True):
            path = os.path.join(out, f"usbtarget-{name}{'-light' if light else ''}.png")
            render(name, light).save(path)
            print(path)
