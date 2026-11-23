"""The Update app's icons for Handtop dark and light (pixel art, nearest-neighbour).

  app-update[-light].png            app drawer, 56x56 (27x27 art x2 + 1 px margin): an open parcel
                                    (cardboard box, flaps up) with the accent-blue arrow going down into it
  update[-light].png                taskbar badge, 23x23: the parcel and arrow, small (an update is
                                    downloaded, or installs at the next restart)
  update-failed[-light].png         taskbar badge, 23x23: the parcel with a red "!" disc (the last update
                                    failed or was stopped)
The -light versions get a dark 1 px outline so they hold on the light taskbar.

Usage: python3 gen_update_icons.py <icon folder>      (overlay/usr/local/share/rg35xxh/icons)"""
import sys

from PIL import Image

EN = 27
BOX, BOX_SIDE, BOX_DARK, FLAP, TAPE = (206, 152, 92), (176, 124, 70), (130, 88, 48), (226, 182, 124), (238, 214, 168)
BLUE, BLUE_HI, BLUE_LIGHT_THEME = (96, 160, 250), (180, 208, 255), (61, 104, 176)
RED, WHITE, INK = (224, 72, 64), (255, 255, 255), (30, 36, 48)


def _img(n, g, colors, outline=None):
    im = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    for (x, y), c in g.items():
        if 0 <= x < n and 0 <= y < n:
            im.putpixel((x, y), colors[c] + (255,))
    if outline:
        src = im.copy()
        for y in range(n):
            for x in range(n):
                if src.getpixel((x, y))[3]:
                    continue
                if any(0 <= x + dx < n and 0 <= y + dy < n and src.getpixel((x + dx, y + dy))[3]
                       for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))):
                    im.putpixel((x, y), outline + (255,))
    return im


def _parcel(g, x0, y0, w, h, flap):
    """A box w x h at (x0, y0): front face, darker right side strip and bottom row, open flaps above."""
    for y in range(y0, y0 + h):
        for x in range(x0, x0 + w):
            g[(x, y)] = "S" if x >= x0 + w - 2 else "B"
        g[(x0, y)] = "B"
    for x in range(x0, x0 + w):
        g[(x, y0 + h - 1)] = "D"
    for x in range(x0 + w // 2 - 1, x0 + w // 2 + 1):        # tape down the middle of the front
        for y in range(y0, y0 + max(2, h // 3)):
            g[(x, y)] = "T"
    for i in range(flap):                                     # flaps folded open to both sides
        for x in range(x0 - i - 1, x0 + 2 - i):
            g[(x, y0 - 1 - i)] = "F"
        for x in range(x0 + w - 2 + i, x0 + w + 1 + i):
            g[(x, y0 - 1 - i)] = "F"


def _arrow(g, cx, top, shaft_end, head, width):
    """A down arrow centred on column cx: shaft (width px) from top to shaft_end, then a head."""
    for y in range(top, shaft_end):
        for x in range(cx - width // 2, cx - width // 2 + width):
            g[(x, y)] = "A"
        g[(cx - width // 2, y)] = "H"
    for i in range(head):
        y = shaft_end + i
        for x in range(cx - head + 1 + i, cx + head - i):
            g[(x, y)] = "A"


def app_icon(light=False):
    g = {}
    _parcel(g, 4, 13, 19, 12, 3)
    _arrow(g, 13, 1, 9, 6, 5)
    colors = dict(B=BOX, S=BOX_SIDE, D=BOX_DARK, F=FLAP, T=TAPE, A=BLUE_LIGHT_THEME if light else BLUE,
                  H=(120, 160, 220) if light else BLUE_HI)
    im = _img(EN, g, colors)
    out = Image.new("RGBA", (56, 56), (0, 0, 0, 0))
    out.paste(im.resize((EN * 2, EN * 2), Image.NEAREST), (1, 1))
    return out


def badge(failed=False, light=False):
    g = {}
    _parcel(g, 5, 12, 13, 8, 2)
    colors = dict(B=BOX, S=BOX_SIDE, D=BOX_DARK, F=FLAP, T=TAPE, A=BLUE_LIGHT_THEME if light else BLUE,
                  H=(120, 160, 220) if light else BLUE_HI, R=RED, W=WHITE)
    if failed:
        for y in range(23):                                   # a red disc with a white "!", top right
            for x in range(23):
                if (x - 16.5) ** 2 + (y - 6) ** 2 <= 30:
                    g[(x, y)] = "R"
        for y in (3, 4, 5, 6):
            g[(16, y)] = g[(17, y)] = "W"
        g[(16, 8)] = g[(17, 8)] = "W"
    else:
        _arrow(g, 11, 1, 7, 5, 3)
    return _img(23, g, colors, outline=INK if light else None)


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "."
    for light, sfx in ((False, ""), (True, "-light")):
        app_icon(light).save(f"{out}/app-update{sfx}.png")
        badge(False, light).save(f"{out}/update{sfx}.png")
        badge(True, light).save(f"{out}/update-failed{sfx}.png")
