"""App icons (pixel art, drawn small and scaled up with nearest-neighbour so the pixels stay
sharp in the app drawer).

  app-theme.png                Theme app: a circle split into a dark and a light half (27x27 art).
  app-external-controller.png  External Controller: the input-mode glass (BT blue / wired brown split
                               diagonally, rainbow stripes) with BT waves, a USB plug and an RG35XX H.
  app-display.png              Display: a monitor with an HDMI cable to an RG35XX H (no glass, fills the grid).
  app-ssh.png                  Enable SSH: a terminal saying "SSH" (white) over a ">_" prompt, and a key (no glass).
  (terminal_icon: the default terminal's icon, written by gen_default_app_icons.py)
  app-recenter.png             Re-center sticks: a stick well seen from above with a crosshair, a faint
                               drifted knob up-right and a blue arrow back to the knob in the centre (no glass).
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


# ---- Display ------------------------------------------------------------------------------
# No glass: the drawing itself fills the 27x27 grid.
DISP_MONITOR = ["W" * 23] + ["W" + "S" * 21 + "W"] * 12 + ["W" * 23]   # screen filled in below
DISP_STAND = ["..........WWW..........", "........WWWWWWW........"]
DISP_HANDHELD = [".WWWWWWWWWWWWW.",
                 "WWKWWDDDDDWWxWW",
                 "WKKKWDDDDDWyWaW",
                 "WWKWWDDDDDWWbWW",
                 "WWWWWDDDDDWWWWW",
                 ".WWWWWWWWWWWWW."]
DISP_CABLE = [(15, 22), (16, 22), (17, 22), (18, 22), (19, 22), (20, 22), (21, 22), (22, 21),
              (23, 20), (23, 19), (23, 18), (23, 17), (23, 16), (23, 15)]   # handheld -> monitor
DISP_DESK, DISP_BAR, DISP_WIN = (61, 90, 138), (20, 24, 32), (232, 234, 238)


def _draw(g, colors, shade):
    """Paint grid cells; the lowest white pixel of each column gets the shade colour."""
    im = Image.new("RGBA", (EN, EN), (0, 0, 0, 0))
    low = {}
    for (x, y), c in g.items():
        if c == "W":
            low[x] = max(low.get(x, -1), y)
    for (x, y), c in g.items():
        im.putpixel((x, y), (shade if c == "W" and low[x] == y else colors[c]) + (255,))
    return im


def _put(g, art, x0, y0):
    for y, row in enumerate(art):
        for x, c in enumerate(row):
            if c != ".":
                g[(x0 + x, y0 + y)] = c


def display_icon(light=False):
    colors = dict(COLORS_LIGHT if light else COLORS)
    colors.update(S=DISP_DESK, T=DISP_BAR, V=DISP_WIN, C=(79, 88, 105) if light else (170, 179, 194))
    g = {}
    _put(g, DISP_MONITOR, 3, 1)
    for y in range(12):                                 # desktop with a window and a taskbar
        for x in range(21):
            g[(4 + x, 2 + y)] = "T" if y == 11 else "V" if 2 <= y <= 7 and 3 <= x <= 12 else "S"
    _put(g, DISP_STAND, 3, 15)
    _put(g, DISP_HANDHELD, 0, 20)
    for xy in DISP_CABLE:
        g[xy] = "C"
    return _tile(_draw(g, colors, SHADE_LIGHT if light else SHADE))


# ---- Enable SSH -----------------------------------------------------------------------------
# No glass: a 25-wide terminal and a key fill the 27x27 grid.
SSH_TERM = ["T" * 25, "TrTyTgT" + "T" * 18] + ["W" + "D" * 23 + "W"] * 14 + ["W" * 25]
SSH_KEY = [".YYY.....", "Y...Y....", "Y...YYYYY", "Y...Y.Y.Y", ".YYY....."]
SSH_GLYPH = {"S": [".###.", "#...#", "#....", ".###.", "....#", "#...#", ".###."],
             "H": ["#...#", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"]}


def ssh_icon(light=False):
    colors = dict(COLORS_LIGHT if light else COLORS)
    # G: the text, white
    colors.update(D=(22, 26, 34), G=(232, 234, 238), Y=(240, 200, 60), r=(226, 70, 70), y=(240, 200, 60),
                  g=(80, 190, 100), T=(79, 88, 105) if light else (200, 205, 214))
    g = {}
    _put(g, SSH_TERM, 1, 3)
    for i, ch in enumerate("SSH"):                       # 5x7 letters, centred in the terminal
        for y, row in enumerate(SSH_GLYPH[ch]):
            for x, c in enumerate(row):
                if c == "#":
                    g[(5 + i * 6 + x, 7 + y)] = "G"
    for dx, dy in ((0, 0), (1, 1), (0, 2), (3, 2), (4, 2)):   # small ">_" prompt
        g[(5 + dx, 15 + dy)] = "G"
    _put(g, SSH_KEY, 17, 18)
    return _tile(_draw(g, colors, SHADE_LIGHT if light else SHADE))


# ---- Terminal (default app: foot) ------------------------------------------------------------
# The Enable SSH terminal without its text and key: a big ">_" prompt. Written under the icon name
# "foot" by gen_default_app_icons.py (not into the Handtop app icon folder).
TERM_PROMPT = ["#.......", "##......", ".##.....", "..##....", ".##.....", "##......", "#......."]


def terminal_icon(light=False):
    colors = dict(COLORS_LIGHT if light else COLORS)
    colors.update(D=(22, 26, 34), G=(232, 234, 238), r=(226, 70, 70), y=(240, 200, 60),
                  g=(80, 190, 100), T=(79, 88, 105) if light else (200, 205, 214))
    g = {}
    _put(g, SSH_TERM, 1, 3)
    for y, row in enumerate(TERM_PROMPT):                # ">" 4x7, 2 px strokes
        for x, c in enumerate(row):
            if c == "#":
                g[(6 + x, 8 + y)] = "G"
    for x in range(11, 18):                              # "_" 7x2
        for y in (13, 14):
            g[(x, y)] = "G"
    return _tile(_draw(g, colors, SHADE_LIGHT if light else SHADE))


# ---- Re-center sticks -----------------------------------------------------------------------
def _disc(g, cx, cy, r, c, ring=None):
    for y in range(EN):
        for x in range(EN):
            d = ((x - cx) ** 2 + (y - cy) ** 2) ** 0.5
            if d <= r + 0.45:
                g[(x, y)] = ring if ring and d > r - 0.55 else c


RC_ARROW = [(20, 6), (19, 7), (18, 8), (17, 9), (16, 10),        # from the drifted knob's centre,
            (17, 10), (18, 10), (16, 9), (16, 8)]                # head pointing down-left


def recenter_icon(light=False):
    colors = dict(COLORS_LIGHT if light else COLORS)
    colors.update(S=SHADE_LIGHT if light else SHADE, R=COLORS_LIGHT["K"] if light else COLORS["C"],
                  G=(138, 147, 163) if light else (70, 78, 94))
    g = {}
    _disc(g, 13, 13, 12.5, "D", ring="R")              # the stick's well
    for i in range(2, 25, 2):                          # dotted crosshair
        g[(i, 13)] = g[(13, i)] = "K"
    _disc(g, 19, 7, 4, "D", ring="G")                  # the drifted knob: outline only
    _disc(g, 13, 13, 4.5, "W", ring="S")               # the knob, back in the centre
    _disc(g, 13, 13, 1, "S")
    for xy in RC_ARROW:
        g[xy] = "x"
    im = Image.new("RGBA", (EN, EN), (0, 0, 0, 0))
    for xy, c in g.items():
        im.putpixel(xy, colors[c] + (255,))
    return _tile(im)


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "."
    for light, sfx in ((False, ""), (True, "-light")):
        theme_icon(light).save(f"{out}/app-theme{sfx}.png")
        external_controller_icon(light).save(f"{out}/app-external-controller{sfx}.png")
        display_icon(light).save(f"{out}/app-display{sfx}.png")
        ssh_icon(light).save(f"{out}/app-ssh{sfx}.png")
        recenter_icon(light).save(f"{out}/app-recenter{sfx}.png")
