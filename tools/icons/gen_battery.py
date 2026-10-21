"""Battery icons for the taskbar and the external-control status screen.

Pixel art, battery only (no frame, no margin): 20 x 11 px. An 18 x 11 shell with a 2 x 5 terminal
on the right; inside, a 1 px gap, then 5 bars (2 px wide, 1 px gaps), one per 20 %
(bars = ceil(percent / 20)). Odd heights, so the terminal and the bars sit on the middle row.

Colours: the shell is always white (dark set) / ink (light set). Lit bars use the same colour,
or red while the real level is 0-20 %. Unlit slots stay faintly visible.

Charging: a yellow lightning bolt with a 1 px clear outline is drawn over the bars, and the
animation (driven by rg35xxh-battery) shows the bar counts from the current level up to full in
turn. The bar colour follows the real level, so it never flickers between red and white.

Output (into the folder given as the first argument, default "."):
  battery-<bars>[-light].png               level > 20 %
  battery-low-<bars>[-light].png           level <= 20 % (red bars)
  battery-charging-<bars>[-light].png      the same with the bolt
  battery-charging-low-<bars>[-light].png
"""
import sys

from PIL import Image

W, H = 20, 11
SHELL = (0, 0, 18, 11)                              # x, y, w, h
NUB = (18, 3, 2, 5)                                 # terminal: cols 18-19, rows 3..7 (middle row 5)
BARS = [(2 + 3 * i, 2, 2, 7) for i in range(5)]     # cols 2-3, 5-6, 8-9, 11-12, 14-15; rows 2..8
BOLT = ["...YY.",                                   # 6 x 7, centred on the shell's inside
        "..YY..",                                   # (cols 6..11, rows 2..8)
        ".YYYYY",
        "YYYYY.",
        "..YY..",
        ".YY...",
        ".Y...."]
BOLT_AT = (6, 2)
THEMES = {
    "dark":  {"ink": (232, 234, 238), "red": (255, 107, 107), "slot": ((255, 255, 255), 0.16),
              "bolt": (255, 214, 64)},
    "light": {"ink": (43, 48, 59), "red": (204, 51, 51), "slot": ((43, 48, 59), 0.14),
              "bolt": (230, 160, 0)},
}


def fill(im, rect, rgb, alpha=1.0):
    x0, y0, w, h = rect
    for y in range(y0, y0 + h):
        for x in range(x0, x0 + w):
            im.putpixel((x, y), tuple(rgb) + (round(alpha * 255),))


def icon(theme, bars, low, charging):
    T = THEMES[theme]
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    x, y, w, h = SHELL
    for r in ((x, y, w, 1), (x, y + h - 1, w, 1), (x, y, 1, h), (x + w - 1, y, 1, h)):
        fill(im, r, T["ink"])
    fill(im, NUB, T["ink"])
    for i, bar in enumerate(BARS):
        if i < bars:
            fill(im, bar, T["red"] if low else T["ink"])
        else:
            fill(im, bar, *T["slot"])
    if charging:
        bx, by = BOLT_AT
        pts = {(bx + c, by + r) for r, row in enumerate(BOLT) for c, ch in enumerate(row) if ch == "Y"}
        halo = {(px + dx, py + dy) for (px, py) in pts for dx in (-1, 0, 1) for dy in (-1, 0, 1)} - pts
        for (px, py) in halo:
            if 1 <= px <= 16 and 1 <= py <= 9:      # inside the shell only; the shell stays intact
                im.putpixel((px, py), (0, 0, 0, 0))
        for p in pts:
            im.putpixel(p, T["bolt"] + (255,))
    return im


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "."
    for theme in THEMES:
        sfx = "" if theme == "dark" else "-light"
        for bars in range(6):
            for low in (False, True):
                for charging in (False, True):
                    name = "battery" + ("-charging" if charging else "") + ("-low" if low else "")
                    icon(theme, bars, low, charging).save(f"{out}/{name}-{bars}{sfx}.png")
