"""App icons (pixel art, drawn small and scaled up with nearest-neighbour so the pixels stay
sharp in the app drawer).

  app-theme.png                Theme app: a circle split into a dark and a light half (27x27 art).
  app-external-controller.png  External Controller: the input-mode glass (BT blue / wired brown split
                               diagonally, rainbow stripes) with BT waves, a USB plug and an RG35XX H.
  All are 27x27 art x2 + 1 px margin = exactly 56x56, the app drawer's icon size.
  Each also gets a -light variant (dark drawing, pastel glass, deeper ring) for the light theme.

Usage: python3 gen_app_icons.py <icon folder>
"""
import colorsys
import sys

from PIL import Image

EN = 27                                       # art grid; x2 + 1 px margin = 56 px tile


def _tile(im):
    out = Image.new("RGBA", (56, 56), (0, 0, 0, 0))
    out.paste(im.resize((EN * 2, EN * 2), Image.NEAREST), (1, 1))
    return out


DARK, LIGHT, EDGE = (30, 36, 48), (236, 239, 244), (159, 195, 255)
EDGE_LIGHT = (61, 104, 176)                   # deeper ring for the light theme


def theme_icon(light=False):
    """A circle split into a dark and a light half; the odd centre column is the divider."""
    edge = EDGE_LIGHT if light else EDGE
    im = Image.new("RGBA", (EN, EN), (0, 0, 0, 0))
    c, r = (EN - 1) / 2, 12.0                    # centre pixel 13, radius 12 (1 px inside the 56 px tile)
    for y in range(EN):
        for x in range(EN):
            d = ((x - c) ** 2 + (y - c) ** 2) ** 0.5
            if d <= r - 0.8:
                im.putpixel((x, y), (edge if x == 13 else DARK if x < 13 else LIGHT) + (255,))
            elif d <= r + 0.5:
                im.putpixel((x, y), edge + (255,))
    return _tile(im)


# ---- External Controller -------------------------------------------------------------------
EXT_HANDHELD = """
.WWWWWWWWWWWWWWWWWWW.
WWWWWWWWWWWWWWWWWWWWW
WWBWWWDDDDDDDDDWWWxWW
WBBBWWDDDDDDgDDWWyWaW
WWBWWWDDDDDDDgDWWWbWW
WWWWWWDDDDDDDDDWWWWWW
WKKKWWDDDDDDDDDWWKKKW
WKCKWWDDDDDDDDDWWKCKW
WKKKWWDDDDDDDDDWWKKKW
WWWWWWWWWWWWWWWWWWWWW
.WWWWWWWWWWWWWWWWWWW.
"""
EXT_WAVES = """
..WWWWW..
.W.....W.
W..WWW..W
..W...W..
....W....
"""
EXT_PLUG = """
.W.W.
WWWWW
WWWWW
.WWW.
..W..
..W..
..W..
..W..
"""
EXT_PARTS = [(EXT_HANDHELD, 13, 3), (EXT_WAVES, 4, 3), (EXT_PLUG, 3, 17)]   # (art, top, left)
COLORS = {"W": (232, 234, 238), "D": (22, 26, 34), "g": (70, 78, 94), "K": (60, 67, 80), "C": (128, 137, 152),
          "x": (74, 140, 230), "a": (226, 70, 70), "b": (240, 200, 60), "y": (80, 190, 100)}
SHADE = (170, 179, 194)                       # lowest white pixel of each column
BT_BG, BT_RING, W_BG, W_RING = (61, 90, 138), (95, 128, 189), (138, 95, 61), (192, 138, 92)
# light theme: dark drawing on pastel glass (same palette as tools/icons/gen_light.py)
COLORS_LIGHT = dict(COLORS, W=(43, 48, 59), D=(207, 214, 226), g=(244, 246, 250), K=(138, 147, 163), C=(213, 218, 227))
SHADE_LIGHT = (79, 88, 105)
LBT_BG, LBT_RING, LW_BG, LW_RING = (163, 189, 230), (61, 104, 176), (226, 184, 143), (176, 117, 63)


def _coverage(x, y, inset, r, ss=8):
    lo, hi = inset, EN - inset
    n = 0
    for i in range(ss):
        for j in range(ss):
            px, py = x + (i + .5) / ss, y + (j + .5) / ss
            cx, cy = min(max(px, lo + r), hi - r), min(max(py, lo + r), hi - r)
            n += lo <= px <= hi and lo <= py <= hi and (px - cx) ** 2 + (py - cy) ** 2 <= r * r
    return n / ss / ss


def _mix(a, b, t):
    return tuple(round(a[k] * (1 - t) + b[k] * t) for k in range(3))


def external_controller_icon(light=False):
    colors, shade = (COLORS_LIGHT, SHADE_LIGHT) if light else (COLORS, SHADE)
    bt_bg, bt_ring, w_bg, w_ring = (LBT_BG, LBT_RING, LW_BG, LW_RING) if light else (BT_BG, BT_RING, W_BG, W_RING)
    g = {}
    for art, top, left in EXT_PARTS:
        for y, row in enumerate(art.strip("\n").split("\n")):
            for x, c in enumerate(row):
                if c != ".":
                    g[(x + left, y + top)] = c
    solid = {p for p, c in g.items() if c in colors}
    halo = {(x + dx, y + dy) for (x, y) in solid for dx in (-1, 0, 1) for dy in (-1, 0, 1)}
    im = Image.new("RGBA", (EN, EN), (0, 0, 0, 0))
    for y in range(EN):
        for x in range(EN):
            outer, inner = _coverage(x, y, 0, 5.5), _coverage(x, y, 1, 4.5)
            k = x + (EN - 1 - y)                                  # diagonal split: BT | wired
            side = 0 if k < EN - 1 else 1 if k > EN - 1 else 0.5
            base, ring = _mix(bt_bg, w_bg, side), _mix(bt_ring, w_ring, side)
            d = x + y
            if d % 4 < 2 and (x, y) not in halo:                  # rainbow stripe, tinted to the side
                stripe = tuple(round(v * 255) for v in colorsys.hsv_to_rgb(d / (2 * EN - 2) * 0.85, 0.65, 0.88 if light else 0.58))
                fill, fa = _mix(stripe, base, 0.35), 0.75 if light else 0.7
            else:
                fill, fa = base, 0.15 if light else 0.12
            fa *= inner
            ra = outer - inner
            a = fa + ra
            if a > 0:
                col = tuple(round((fill[i] * fa + ring[i] * ra) / a) for i in range(3))
                im.putpixel((x, y), col + (round(min(a, 1) * 255),))
    low = {}
    for (x, y), c in g.items():
        if c == "W":
            low[x] = max(low.get(x, -1), y)
    for (x, y), c in g.items():
        if c in colors:
            im.putpixel((x, y), (shade if c == "W" and low[x] == y else colors[c]) + (255,))
    return _tile(im)


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "."
    for light, sfx in ((False, ""), (True, "-light")):
        theme_icon(light).save(f"{out}/app-theme{sfx}.png")
        external_controller_icon(light).save(f"{out}/app-external-controller{sfx}.png")
