"""Power menu (wlogout) and taskbar button icons, pixel art.

  power-<action>.png        power menu buttons, 24x24 art x3 = 72 px: sleep (crescent moon and a
  power-<action>-light.png  star), reboot (ring with an arrowhead, clockwise), logout (door frame
  power-<action>-focus.png  with an arrow out), shutdown (the power symbol). Each action has its own
                            colour (blue / amber / grey / red); -light = darker inks for the light
                            theme; -focus = white, for the highlighted button in the dark theme
                            (the coloured icon would be lost on the blue highlight).
  panel-apps.png            taskbar Apps button: 3x3 app grid, 8x8 art x2 = 16 px, white (both themes)
  panel-power[-light].png   taskbar power button: the power symbol at 1x (24 px), red

Every column's lowest pixel is drawn a little darker, like the other Handtop pixel art.
Usage: python3 gen_power_icons.py <icon folder>   (overlay/usr/local/share/rg35xxh/icons)
"""
import math
import sys

from PIL import Image

G = 24


def _ring(px, cx, cy, r0, r1, skip):
    for y in range(G):
        for x in range(G):
            dx, dy = x + .5 - cx, y + .5 - cy
            if r0 <= math.hypot(dx, dy) <= r1 and not skip(dx, dy, math.degrees(math.atan2(-dy, dx)) % 360):
                px.add((x, y))


def _art(rows, x0, y0, px):
    for j, r in enumerate(rows):
        for i, c in enumerate(r):
            if c == "#":
                px.add((x0 + i, y0 + j))


def power():
    p = set()
    _ring(p, 12, 13, 7.4, 9.6, lambda dx, dy, a: dy < 0 and abs(dx) <= 3.6)   # open at the top
    for y in range(2, 13):
        p.update({(11, y), (12, y)})                                         # the bar
    return p


def restart():
    """Ring open on the upper right; the top end of the arc carries a solid arrowhead pointing
    right (clockwise), its base centred on the ring band so the two read as one stroke."""
    p = set()
    _ring(p, 12, 13.5, 7.4, 9.6, lambda dx, dy, a: a <= 72 or a >= 352)
    for i, (y0, y1) in enumerate(((1, 8), (2, 7), (3, 6), (4, 5))):   # columns x = 14..17
        p.update((14 + i, y) for y in range(y0, y1 + 1))
    return p


def logout():
    p = set()
    for y in range(3, 21):
        p.update({(3, y), (4, y)})                                           # door frame
    for x in range(3, 13):
        p.update({(x, 3), (x, 4), (x, 19), (x, 20)})
    for y in (5, 6, 17, 18):
        p.update({(11, y), (12, y)})
    for x in range(8, 18):
        p.update({(x, 11), (x, 12)})                                         # arrow shaft
    _art(["#....", "##...", "###..", "####.", "#####", "#####", "####.", "###..", "##...", "#...."], 17, 7, p)
    return p


def sleep():
    p = set()
    for y in range(G):
        for x in range(G):
            if math.hypot(x + .5 - 11, y + .5 - 13) <= 9.2 and math.hypot(x + .5 - 15.5, y + .5 - 8.5) > 7.6:
                p.add((x, y))
    _art(["..#..", ".###.", "#####", ".###.", "..#.."], 17, 2, p)          # star
    return p


def apps():
    p = set()
    for bx in (0, 3, 6):
        for by in (0, 3, 6):
            p.update({(bx, by), (bx + 1, by), (bx, by + 1), (bx + 1, by + 1)})
    return p


def draw(px, col, size, z, shade=True):
    sh = tuple(round(c * .72) for c in col) if shade else col
    low = {}
    for x, y in px:
        low[x] = max(low.get(x, -1), y)
    im = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    for x, y in px:
        im.putpixel((x, y), (sh if low[x] == y else col) + (255,))
    return im.resize((size * z, size * z), Image.NEAREST)


def rgb(h):
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))


ACTIONS = {"sleep": sleep, "reboot": restart, "logout": logout, "shutdown": power}
COLOURS = {"": {"sleep": "#8fb4ff", "reboot": "#ffd28f", "logout": "#c9ced8", "shutdown": "#ff6b6b"},
           "-light": {"sleep": "#3d68b0", "reboot": "#a36b00", "logout": "#4f5869", "shutdown": "#cc3333"}}

if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "."
    for name, fn in ACTIONS.items():
        art = fn()
        for suffix, cols in COLOURS.items():
            draw(art, rgb(cols[name]), G, 3).save(f"{out}/power-{name}{suffix}.png")
        draw(art, (255, 255, 255), G, 3).save(f"{out}/power-{name}-focus.png")
    draw(apps(), (255, 255, 255), 8, 2, shade=False).save(f"{out}/panel-apps.png")
    draw(power(), rgb("#ff6b6b"), G, 1).save(f"{out}/panel-power.png")
    draw(power(), rgb("#cc3333"), G, 1).save(f"{out}/panel-power-light.png")
