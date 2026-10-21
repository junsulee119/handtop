"""Bluetooth icons (pixel art, no frame): the taskbar tray states of the blueman applet and the
Bluetooth Manager's drawer icon. They replace blueman's own icons by name from
/usr/local/share/icons/hicolor (searched before /usr/share for the same subdirectory), so the
package's files are untouched. They must sit in the subdirectory GTK picks for the requested size:

  {22x22,24x24}/status/blueman-tray.png       23x23  Bluetooth on: blue rune
  {22x22,24x24}/status/blueman-active.png     23x23  a device connected: blue rune + green dot
  {22x22,24x24}/status/blueman-disabled.png   23x23  Bluetooth off: grey rune
  scalable/{status,apps}/blueman.png          56x56  Bluetooth Manager in the app drawer: bold rune

For 23 px GTK takes the 22x22 / 24x24 "Threshold" directories before scalable ones; Waybar asks for
the exact size, so a 23 px file is drawn 1:1. For the drawer's 56 px it takes a scalable directory,
and scalable/status comes before scalable/apps (blueman ships its icon in both).

The tray icons are 23 px like the input-mode icon (Waybar tray "icon-size": 23). One set for both
themes: the blue reads on the dark and the light taskbar.

Usage: python3 gen_bt_icons.py <hicolor folder>    (e.g. overlay/usr/local/share/icons/hicolor)
"""
import os
import sys

from PIL import Image

BLUE, GREY, GREEN = (74, 140, 230), (128, 137, 152), (80, 200, 110)


def rune(w, h):
    """Bluetooth rune in a w x h box (odd sizes): a stem and two crossing chevrons, as points."""
    cx, q = w // 2, (h - 1) // 4
    top, bottom = (cx, 0), (cx, h - 1)
    r1, r2 = (w - 2, q), (w - 2, h - 1 - q)
    l1, l2 = (1, q), (1, h - 1 - q)
    pts = set()
    for (x0, y0), (x1, y1) in ((top, bottom), (top, r1), (r1, l2), (l1, r2), (r2, bottom)):
        dx, dy = abs(x1 - x0), -abs(y1 - y0)                 # Bresenham
        sx, sy = (1 if x0 < x1 else -1), (1 if y0 < y1 else -1)
        err = dx + dy
        while True:
            pts.add((x0, y0))
            if (x0, y0) == (x1, y1):
                break
            e2 = 2 * err
            if e2 >= dy:
                err += dy
                x0 += sx
            if e2 <= dx:
                err += dx
                y0 += sy
    return pts


def tray(state):
    n, w, h = 23, 11, 19
    im = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    x0 = (n - w) // 2
    col = GREY if state == "disabled" else BLUE
    for x, y in rune(w, h):
        im.putpixel((x0 + x, 2 + y), col + (255,))
    if state == "active":                                    # connected: one green dot, bottom right
        for dx in range(3):
            for dy in range(3):
                im.putpixel((x0 + w + 1 + dx, 2 + h - 4 + dy), GREEN + (255,))
    return im


def drawer():
    en = 27                                                  # 27x27 art x2 + 1 px = 56 px
    art = Image.new("RGBA", (en, en), (0, 0, 0, 0))
    for x, y in rune(15, 23):
        for dx in (0, 1, 2):                                 # 3-cell strokes: bold at 56 px
            art.putpixel((5 + x + dx, 2 + y), BLUE + (255,))
    out = Image.new("RGBA", (56, 56), (0, 0, 0, 0))
    out.paste(art.resize((en * 2, en * 2), Image.NEAREST), (1, 1))
    return out


if __name__ == "__main__":
    root = sys.argv[1] if len(sys.argv) > 1 else "."
    for sub in ("22x22/status", "24x24/status", "scalable/status", "scalable/apps"):
        os.makedirs(f"{root}/{sub}", exist_ok=True)
    for state in ("tray", "active", "disabled"):
        for size in ("22x22", "24x24"):
            tray(state).save(f"{root}/{size}/status/blueman-{state}.png")
    for sub in ("scalable/status", "scalable/apps"):
        drawer().save(f"{root}/{sub}/blueman.png")
