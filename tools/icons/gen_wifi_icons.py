"""Wi-Fi / network tray icons (pixel art, no frame) for the NetworkManager applet (nm-applet).
They replace the applet's own icons by name, so the package's files are untouched:
  dark set   hicolor/{22x22,24x24}/apps         (/usr/local/share/icons/hicolor is searched before
                                                /usr/share for the same subdirectory; see gen_bt_icons.py)
  light set  Handtop-Light/{22x22,24x24}/apps   an icon theme that only holds these and inherits
                                                Adwaita + hicolor; rg35xxh-theme makes it the GTK
                                                icon theme while the light theme is on

23x23 (Waybar asks for 23 px; nm-applet ships its icons in 22x22/apps):
  nm-signal-{00,25,50,75,100}[-secure].png   a Wi-Fi fan: dot + 3 arcs (2 px), lit from the
                                             inside out (00: dot only, 25: 1 arc, 50: 2, 75/100: 3);
                                             unlit arcs stay faintly visible
  nm-no-connection.png                       grey fan with a red X
  nm-stage0{1,2,3}-connecting{01..11}.png    connecting: the arcs light up in turn, over and over
  nm-device-wired[-secure].png               wired (e.g. USB Ethernet): a network socket

Colours like the battery icon: white on the dark taskbar, dark ink on the light one; unlit arcs
are a faint version of the same colour. No connection: a grey fan and a red X.

Usage: python3 gen_wifi_icons.py <icons folder>    (e.g. overlay/usr/local/share/icons)
"""
import math
import os
import sys

from PIL import Image

S = 23
GREY = (128, 137, 152)
THEMES = {                                      # folder, ink, faint (rgb, alpha), red
    "dark":  ("hicolor", (232, 234, 238), ((255, 255, 255), 0.18), (255, 107, 107)),
    "light": ("Handtop-Light", (43, 48, 59), ((43, 48, 59), 0.16), (204, 51, 51)),
}
INDEX = """[Icon Theme]
Name=Handtop-Light
Comment=Handtop light theme: taskbar icons drawn for a light background (rg35xxh-theme light)
Inherits=Adwaita,hicolor
Hidden=true
Directories=22x22/apps,24x24/apps

[22x22/apps]
Size=22
Context=Applications
Type=Threshold

[24x24/apps]
Size=24
Context=Applications
Type=Threshold
"""
CX, CY = 11, 18                                 # centre of the arcs (the dot's bottom row)
RADII = ((5, 6), (9, 10), (13, 14))             # 2 px arcs
DOT = [(x, y) for x in (10, 11, 12) for y in (17, 18)]


def arc(rs):
    return {(x, y) for y in range(CY) for x in range(S)
            if any(abs(math.hypot(x - CX, y - CY) - r) < 0.5 for r in rs)
            and abs(math.degrees(math.atan2(CX - x, CY - y))) <= 46}


ARCS = [arc(rs) for rs in RADII]


def fan(theme, lit, off=False):
    _, ink, (frgb, fa), red = THEMES[theme]
    if off:
        ink = GREY
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    for i, pts in enumerate(ARCS):
        for p in pts:
            im.putpixel(p, ink + (255,) if i < lit else frgb + (round(fa * 255),))
    for p in DOT:
        im.putpixel(p, ink + (255,))
    if off:
        for i in range(5):
            im.putpixel((16 + i, 14 + i), red + (255,))
            im.putpixel((20 - i, 14 + i), red + (255,))
    return im


def wired(theme):
    """A network socket, 15 x 13: outline, a latch notch at the bottom, 4 contacts at the top."""
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    x0, y0, w, h = 4, 5, 15, 13
    ink = THEMES[theme][1]
    px = lambda x, y: im.putpixel((x, y), ink + (255,))
    for x in range(x0, x0 + w):
        px(x, y0)
    for y in range(y0, y0 + h):
        px(x0, y)
        px(x0 + w - 1, y)
    notch = range(x0 + 4, x0 + w - 4)                   # bottom edge, stepped in for the latch
    for x in range(x0, x0 + w):
        if x not in notch:
            px(x, y0 + h - 1)
    for y in range(y0 + h - 1, y0 + h + 2):
        px(notch[0], y)
        px(notch[-1], y)
    for x in notch:
        px(x, y0 + h + 1)
    for i in range(4):                                  # contacts
        for y in range(y0 + 2, y0 + 5):
            px(x0 + 3 + 3 * i, y)
    return im


if __name__ == "__main__":
    root = sys.argv[1] if len(sys.argv) > 1 else "."
    for theme, (folder, *_) in THEMES.items():
        icons = {}
        for name, lit in (("00", 0), ("25", 1), ("50", 2), ("75", 3), ("100", 3)):
            icons[f"nm-signal-{name}"] = icons[f"nm-signal-{name}-secure"] = fan(theme, lit)
        icons["nm-no-connection"] = fan(theme, 0, off=True)
        for stage in (1, 2, 3):
            for f in range(1, 12):
                icons[f"nm-stage0{stage}-connecting{f:02d}"] = fan(theme, (f - 1) % 4)
        icons["nm-device-wired"] = icons["nm-device-wired-secure"] = wired(theme)
        for size in ("22x22", "24x24"):
            os.makedirs(f"{root}/{folder}/{size}/apps", exist_ok=True)
            for name, im in icons.items():
                im.save(f"{root}/{folder}/{size}/apps/{name}.png")
    with open(f"{root}/Handtop-Light/index.theme", "w") as f:
        f.write(INDEX)
