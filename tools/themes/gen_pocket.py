"""The Pocket theme: the classic four-shade green handheld screen. Everything is drawn in exactly
four colours, lightest to darkest: a #9bbc0f, b #8bac0f, c #306230, d #0f380f. All pixel art is
drawn for Pocket (no drawings shared with Retro): chunky sprites with a dark outline, a light
highlight on the upper left, darker shading on the lower right, like handheld game sprites.

Drawings are made of filled shapes on a small canvas; `outline()` adds the dark outline around
everything drawn, so shapes never need it by hand. Every drawing is centred in its image.

Usage: python3 tools/themes/gen_pocket.py [theme folder]      (src/theme/extra/pocket)
Needs Pillow. fonts/ (Pixelify Sans, VT323, LICENSE.txt) is kept as it is."""
import json
import math
import os
import sys

from PIL import Image, ImageDraw, ImageFont

A, B, C, D = (155, 188, 15), (139, 172, 15), (48, 98, 48), (15, 56, 15)
SH = {"a": A, "b": B, "c": C, "d": D}
H = {k: "#%02x%02x%02x" % v for k, v in SH.items()}
FONT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "src", "theme", "extra",
                    "pocket", "fonts", "ui.ttf")
IDX = {".": 0, "a": 1, "b": 2, "c": 3, "d": 4}


class P:
    """A pixel canvas: 0 = clear, 1..4 = shades a..d. No smoothing anywhere."""
    def __init__(self, w, h):
        self.w, self.h = w, h
        self.im = Image.new("L", (w, h), 0)
        self.d = ImageDraw.Draw(self.im)

    def rect(self, x0, y0, x1, y1, s):
        self.d.rectangle((x0, y0, x1, y1), fill=IDX[s])

    def box(self, x0, y0, x1, y1, s, width=1):
        self.d.rectangle((x0, y0, x1, y1), outline=IDX[s], width=width)

    def rrect(self, x0, y0, x1, y1, r, s, outline=None):
        self.d.rounded_rectangle((x0, y0, x1, y1), radius=r, fill=IDX[s],
                                 outline=IDX[outline] if outline else None)

    def ellipse(self, x0, y0, x1, y1, s, outline=None, width=1):
        self.d.ellipse((x0, y0, x1, y1), fill=IDX[s] if s else None,
                       outline=IDX[outline] if outline else None, width=width)

    def poly(self, pts, s):
        self.d.polygon(pts, fill=IDX[s])

    def line(self, pts, s, width=1):
        self.d.line(pts, fill=IDX[s], width=width)

    def px(self, x, y, s):
        if 0 <= x < self.w and 0 <= y < self.h:
            self.im.putpixel((x, y), IDX[s])

    def grid(self, x, y, rows):
        for j, r in enumerate(rows):
            for i, ch in enumerate(r):
                if ch != " " and ch != "_":
                    self.px(x + i, y + j, ch if ch != "." else ".")

    def stamp(self, x, y, rows):
        """Like grid, but '.' means 'leave as is' (only letters are drawn)."""
        for j, r in enumerate(rows):
            for i, ch in enumerate(r):
                if ch in "abcd":
                    self.px(x + i, y + j, ch)

    def outline(self, s="d"):
        """A 1 px outline (shade s) around everything drawn (4-neighbourhood)."""
        src = self.im.copy().load()
        for y in range(self.h):
            for x in range(self.w):
                if src[x, y] == 0 and any(0 <= x + dx < self.w and 0 <= y + dy < self.h
                                          and src[x + dx, y + dy] for dx, dy in
                                          ((1, 0), (-1, 0), (0, 1), (0, -1))):
                    self.im.putpixel((x, y), IDX[s])
        return self

    def ring(self, s="a"):
        """A 1 px ring of shade s around everything (the highlighted power-menu icons)."""
        return self.outline(s)

    def rgba(self):
        out = Image.new("RGBA", (self.w, self.h), (0, 0, 0, 0))
        src = self.im.load()
        cols = [None, A, B, C, D]
        for y in range(self.h):
            for x in range(self.w):
                v = src[x, y]
                if v:
                    out.putpixel((x, y), cols[v] + (255,))
        return out

    def centred(self):
        b = self.im.getbbox()
        if b:
            out = Image.new("L", (self.w, self.h), 0)
            out.paste(self.im.crop(b), ((self.w - (b[2] - b[0])) // 2, (self.h - (b[3] - b[1])) // 2))
            self.im, self.d = out, ImageDraw.Draw(out)
        return self

    def copy(self):
        n = P(self.w, self.h)
        n.im = self.im.copy()
        n.d = ImageDraw.Draw(n.im)
        return n


def big(p, z):
    return p.rgba().resize((p.w * z, p.h * z), Image.NEAREST)


FONT3 = {"P": ["ccc", "c.c", "ccc", "c..", "c.."], "D": ["cc.", "c.c", "c.c", "c.c", "cc."],
         "F": ["ccc", "c..", "cc.", "c..", "c.."], "Z": ["ddd", "..d", ".d.", "d..", "ddd"],
         "z": ["dd", ".d", "d.", "dd"]}


def text(p, x, y, s, shade):
    for ch in s:
        g = FONT3[ch]
        for j, r in enumerate(g):
            for i, b in enumerate(r):
                if b != ".":
                    p.px(x + i, y + j, shade)
        x += len(g[0]) + 1


# ---- small shared sprites ------------------------------------------------------------------------------
def handheld(p, x, y):
    """A horizontal handheld, 17x9 before its outline: light body, dark screen with a glint,
    D-pad on the left, two buttons on the right."""
    p.rrect(x, y, x + 16, y + 8, 2, "b")
    p.rect(x + 1, y + 7, x + 15, y + 7, "c")                       # lower edge shading
    p.rect(x + 5, y + 2, x + 11, y + 6, "d")                       # screen
    p.px(x + 6, y + 3, "a")
    p.rect(x + 2, y + 4, x + 3, y + 4, "d")                        # D-pad
    p.rect(x + 2, y + 3, x + 2, y + 5, "d")
    p.px(x + 1, y + 4, "d")
    p.px(x + 13, y + 3, "c")
    p.px(x + 14, y + 5, "c")


def bt_rune(p, x, y, s):
    p.grid(x, y, [s and r.replace("#", s).replace(" ", "_") for r in
                  ["__#__", "__##_", "#_#_#", "_###_", "__#__", "_###_", "#_#_#", "__##_", "__#__"]])


# ---- taskbar: a dark HUD strip, so its images are light on dark ------------------------------------
# Images that External Controller also shows on its light pages (input modes, battery) get a dark
# outline and then a light ring, so they read on both.
def panel_apps():
    """The START button's mark: a D-pad."""
    p = P(16, 16)
    p.rect(6, 2, 9, 13, "d")
    p.rect(2, 6, 13, 9, "d")
    p.px(7, 4, "c"); p.px(7, 11, "c"); p.px(4, 7, "c"); p.px(11, 7, "c")
    return p


def panel_power():
    p = P(24, 24)
    p.ellipse(4, 4, 19, 19, None, "a", 3)
    p.rect(9, 1, 14, 9, ".")
    p.rect(10, 2, 13, 11, "a")
    return p.centred()


def glove(p, x, y):
    """The game-menu glove, pointing right (also the pointer)."""
    p.grid(x, y, [r.replace(".", "_") for r in GLOVE])


def inputmode(mode):
    p = P(23, 23)
    if mode == "desktop":                                          # desktop mode: the glove
        glove(p, 1, 6)
    elif mode == "gamepad":
        handheld(p, 2, 7)
        p.outline()
    else:
        handheld(p, 2, 13)
        if mode == "bt":
            p.rrect(7, 0, 15, 10, 2, "c")
            bt_rune(p, 9, 1, "a")
        else:
            p.rect(9, 0, 13, 3, "a")
            p.px(10, 1, "c"); p.px(12, 1, "c")
            p.rect(8, 4, 14, 8, "c")
            p.rect(11, 9, 11, 12, "d")
        p.outline()
    p.centred()
    return p.outline("a").centred()


HEART = ["dd_dd", "ddddd", "ddddd", "_ddd_", "__d__"]


def battery(n, charging=False, low=False, saver=False):
    """Hearts: three hearts filled in halves from the left (level 0-5 -> 0-6 halves), light on the
    dark taskbar, empty ones in the middle shade, a dark outline so they also read on External
    Controller's light status screen; a bolt while charging; Battery saver fills them half-light."""
    p = P(20, 11)
    full = "b" if saver else "a"
    halves = round(6 * n / 5)
    x0 = 0 if charging else 1
    for i in range(3):
        for j, r in enumerate(HEART):
            for k, ch in enumerate(r):
                if ch == "d":
                    filled = (2 * i + (1 if k < 3 else 2)) <= halves
                    p.px(x0 + 1 + i * 6 + k, 3 + j, full if filled else "c")
    if charging:
        p.grid(18, 2, ["_a", "a_", "aa", "_a", "a_"])
    p.outline("d")
    return p


# ---- tray (taskbar only: light on the dark strip) ---------------------------------------------------
def fan(p, lit, dim=False):
    """Wi-Fi on the dark strip: a 3x3 dot under three arcs, the dot apart from the first arc and
    everything centred on the same column (x = 11)."""
    cx, cy = 11, 18
    for i, r in enumerate((5, 8, 11)):
        on = (i + 1) <= lit and not dim
        p.d.arc((cx - r, cy - r, cx + r, cy + r), 225, 315, fill=IDX["a" if on else "c"], width=2)
    p.rect(cx - 1, cy - 1, cx + 1, cy + 1, "a" if (lit >= 1 and not dim) else "c")
    p.centred()


def wifi(name):
    p = P(23, 23)
    secure = name.endswith("-secure")
    base = name[:-7] if secure else name
    if base.startswith("nm-signal-"):
        fan(p, {"00": 0, "25": 1, "50": 2, "75": 3, "100": 3}[base.split("-")[2]])
    elif base == "nm-no-connection":
        fan(p, 0, dim=True)
        p.grid(16, 15, ["a___a", "_a_a_", "__a__", "_a_a_", "a___a"])
    elif base.startswith("nm-stage"):
        fan(p, int(base[-2:]) % 4)
    else:                                                          # wired: a network plug
        p.rect(7, 3, 15, 11, "a")
        p.rect(8, 9, 14, 11, "b")
        p.rect(9, 12, 13, 15, "b")
        p.rect(10, 16, 12, 20, "a")
        p.px(9, 6, "d"); p.px(11, 6, "d"); p.px(13, 6, "d")
        p.centred()
    if secure:
        p.stamp(0, 0, [".aaa.", "a...a", "a...a", "aaaaa", "abbba", "abdba", "aaaaa"])
    return p


def bluetooth(state):
    p = P(23, 23)
    fill, rune = ("c", "b") if state == "blueman-disabled" else ("a", "d")
    p.rrect(6, 3, 16, 19, 3, fill)
    bt_rune(p, 9, 7, rune)
    p.centred()
    if state == "blueman-active":
        p.rect(17, 16, 20, 19, "a")
        p.box(16, 15, 21, 20, "c")
    return p


def usbtarget(t):
    p = P(23, 23)
    if t == "pc":
        p.rrect(3, 1, 19, 12, 1, "b")                              # monitor
        p.rect(5, 3, 17, 10, "d")
        p.px(6, 4, "a"); p.px(7, 4, "a"); p.px(6, 5, "a")
        p.rect(10, 13, 12, 14, "c")
        p.rect(2, 17, 20, 21, "b")                                 # keyboard
        for x in range(4, 19, 2):
            p.px(x, 19, "c")
    else:
        p.rrect(2, 0, 20, 12, 2, "b")                              # TV
        p.rect(4, 2, 18, 10, "d")
        p.px(5, 3, "a"); p.px(6, 3, "a"); p.px(5, 4, "a")
        p.rect(7, 13, 8, 14, "c"); p.rect(14, 13, 15, 14, "c")
        p.rrect(5, 16, 17, 21, 2, "b")                             # gamepad
        p.rect(7, 18, 9, 18, "d"); p.rect(8, 17, 8, 19, "d")
        p.px(14, 18, "c"); p.px(15, 19, "c")
    p.outline()
    return p.centred()


# ---- app icons: 28x28 art, shown 2x --------------------------------------------------------------------
def app(name):
    p = P(28, 28)
    if name == "theme":                                            # a paint brush and a drop
        p.poly([(18, 3), (24, 9), (14, 19), (8, 13)], "b")         # handle
        p.poly([(20, 5), (23, 8), (14, 17), (11, 14)], "a")
        p.poly([(8, 13), (14, 19), (12, 21), (6, 15)], "c")        # ferrule
        p.poly([(6, 15), (12, 21), (8, 25), (3, 25), (2, 20)], "d")  # bristles with paint
        p.ellipse(19, 18, 25, 25, "c")                             # drop
        p.poly([(22, 14), (19, 20), (25, 20)], "c")
        p.px(20, 20, "a"); p.px(21, 21, "a")
    elif name == "external-controller":                            # a game pad with two grips
        p.rrect(1, 7, 26, 18, 5, "b")
        p.ellipse(1, 11, 10, 23, "b"); p.ellipse(17, 11, 26, 23, "b")
        p.rect(4, 19, 7, 21, "c"); p.rect(20, 19, 23, 21, "c")      # grip shading
        p.rect(4, 11, 9, 12, "d"); p.rect(6, 9, 7, 14, "d")         # D-pad
        p.ellipse(18, 9, 20, 11, "c"); p.ellipse(21, 12, 23, 14, "c")
        p.rect(11, 13, 12, 13, "c"); p.rect(15, 13, 16, 13, "c")    # select / start
        p.rect(4, 8, 8, 8, "a")                                     # highlight
    elif name == "display":                                        # a monitor showing a landscape
        p.rrect(1, 2, 26, 19, 2, "b")
        p.rect(3, 4, 24, 17, "a")
        p.poly([(3, 17), (3, 13), (8, 9), (13, 14), (17, 11), (24, 15), (24, 17)], "c")
        p.ellipse(18, 5, 21, 8, "b")
        p.rect(11, 20, 16, 22, "c")
        p.rect(7, 23, 20, 24, "b")
    elif name == "enable-ssh":                                     # a screen with a prompt and a key
        p.rrect(1, 2, 22, 19, 2, "d")
        p.grid(4, 6, ["a__", "_a_", "__a", "_a_", "a__"])
        p.rect(9, 10, 12, 10, "a")
        p.ellipse(15, 15, 22, 22, "b")                             # key bow
        p.ellipse(17, 17, 20, 20, ".")
        p.rect(22, 18, 27, 19, "b"); p.rect(25, 20, 25, 21, "b"); p.rect(27, 20, 27, 21, "b")
        p.outline()
        p.px(18, 18, "d"); p.px(19, 19, "d")
        return p.centred()
    elif name == "recenter-sticks":                                # a stick seen from above + arrows
        p.ellipse(6, 6, 21, 21, "c")
        p.ellipse(9, 9, 18, 18, "b")
        p.ellipse(10, 10, 14, 14, "a")
        p.outline()
        for (x, y, rows) in ((11, 0, ["__dd__", "_dddd_", "dddddd"]), (11, 25, ["dddddd", "_dddd_", "__dd__"]),
                             (0, 11, ["__d", "_dd", "ddd", "ddd", "_dd", "__d"]),
                             (25, 11, ["d__", "dd_", "ddd", "ddd", "dd_", "d__"])):
            p.grid(x, y, rows)
        return p.centred()
    elif name == "foot":                                           # a terminal
        p.rrect(1, 3, 26, 23, 3, "d")
        p.rect(3, 5, 24, 6, "c")
        p.grid(5, 10, ["a___", "_a__", "__a_", "_a__", "a___"])
        p.rect(11, 14, 16, 14, "a")
    elif name == "thunar":                                         # a folder
        p.rrect(1, 5, 11, 10, 1, "c")
        p.rrect(1, 8, 26, 23, 2, "c")
        p.poly([(4, 11), (27, 11), (25, 23), (1, 23)], "b")
        p.rect(4, 12, 24, 12, "a")
    elif name == "mousepad":                                       # a notepad with a pencil line
        p.rect(5, 3, 22, 25, "a")
        p.rect(21, 4, 22, 25, "b"); p.rect(5, 24, 22, 25, "b")
        for x in range(7, 22, 3):
            p.rect(x, 1, x, 4, "d")
        for y in (9, 13, 17, 21):
            p.rect(8, y, 19, y, "c")
    elif name == "chromium":                                       # a globe
        p.ellipse(2, 2, 25, 25, "b")
        p.poly([(7, 6), (13, 5), (14, 10), (10, 14), (6, 12)], "c")
        p.poly([(15, 13), (22, 12), (23, 18), (17, 22)], "c")
        p.poly([(5, 17), (9, 18), (8, 22)], "c")
        p.ellipse(6, 5, 9, 8, "a")
        p.d.arc((2, 2, 25, 25), 20, 160, fill=IDX["c"], width=2)
    elif name == "htop":                                           # a screen with level bars
        p.rrect(1, 3, 26, 23, 3, "d")
        for i, h in enumerate((6, 10, 8, 13, 5, 11)):
            p.rect(4 + i * 4, 20 - h, 6 + i * 4, 20, "a" if i % 2 else "b")
    elif name == "micro":                                          # a page with a pencil
        p.rect(3, 3, 19, 25, "a")
        p.rect(18, 4, 19, 25, "b")
        for y in (7, 11, 15, 19):
            p.rect(6, y, 15, y, "c")
        p.poly([(24, 6), (27, 9), (15, 21), (12, 18)], "b")
        p.poly([(25, 7), (26, 8), (15, 19), (14, 18)], "a")
        p.poly([(12, 18), (15, 21), (11, 22)], "c")
        p.px(11, 22, "d")
    elif name == "qpdfview":                                       # a document with a PDF label
        p.poly([(4, 1), (18, 1), (24, 7), (24, 26), (4, 26)], "a")
        p.poly([(18, 1), (24, 7), (18, 7)], "b")
        p.rect(23, 8, 24, 26, "b")
        for y in (5, 9):
            p.rect(7, y, 15, y, "c")
        p.rect(2, 13, 21, 22, "c")
        text(p, 5, 15, "PDF", "a")
    elif name == "xarchiver":                                      # a treasure chest
        p.rrect(2, 5, 25, 13, 4, "b")
        p.rect(2, 11, 25, 24, "b")
        p.rect(2, 12, 25, 13, "c")
        p.rect(6, 5, 7, 24, "c"); p.rect(20, 5, 21, 24, "c")
        p.rect(3, 22, 24, 23, "c")
        p.rect(11, 10, 16, 16, "a")
        p.rect(13, 13, 14, 15, "d")
        p.rect(4, 7, 5, 8, "a")
    elif name == "blueman":                                        # the Bluetooth rune on a badge
        p.rrect(5, 1, 22, 26, 5, "c")
        p.rect(7, 3, 9, 4, "b")
        p.line([(13, 5), (13, 22)], "a", 2)
        p.line([(13, 5), (18, 9), (9, 17)], "a", 2)
        p.line([(13, 22), (18, 18), (9, 10)], "a", 2)
    p.outline()
    return p.centred()


# ---- app icons as game cartridges -------------------------------------------------------------------
# Every app is a cartridge (a generic one: notched corner, grip ridges, contacts at the bottom) with
# a label showing the app; the console is the device, the apps are its games (Jason 2026-11-11:
# each theme should feel like a different device). The labels are 12x12 sprites.
MINI = {
    "theme": ["_______dd___", "______dbd___", "_____dbd____", "____dbd_____", "___dcd______",
              "__dddd______", "_dddd_______", "_ddd____d___", "dd_____ddd__", "______ddddd_",
              "______ddddd_", "_______ddd__"],
    "external-controller": ["____________", "____________", "_dddddddddd_", "dbbbbbbbbbbd",
                            "dbdbbbbbcbbd", "dddddbbcbcbd", "dbdbbbbbcbbd", "dbbbbbbbbbbd",
                            "dbbddddddbbd", "_dd______dd_", "____________", "____________"],
    "display": ["dddddddddddd", "dbbbbbbbbbbd", "dbbbbbbbbbbd", "dbbbbbbccbbd", "dbcbbbbccbbd",
                "dcccbbccccbd", "dccccccccccd", "dddddddddddd", "_____dd_____", "_____dd_____",
                "___dddddd___", "____________"],
    "enable-ssh": ["____________", "_dddd_______", "dd__dd______", "d____d______", "d____ddddddd",
                   "d____ddddddd", "dd__dd__d_dd", "_dddd___d__d", "____________", "____________",
                   "____________", "____________"],
    "recenter-sticks": ["_____dd_____", "____dddd____", "____________", "___dddddd___",
                        "d_dd____dd_d", "ddd__dd__ddd", "ddd__dd__ddd", "d_dd____dd_d",
                        "___dddddd___", "____________", "____dddd____", "_____dd_____"],
    "foot": ["_dddddddddd_", "dddddddddddd", "dbbddddddddd", "ddbbdddddddd", "dddbbddddddd", "ddbbdddddddd", "dbbddbbbbbdd", "dddddddddddd", "_dddddddddd_"],   # a dark screen with a bold ">_"
    "thunar": ["____________", "ddddd_______", "dbbbbd______", "dbbbbbddddd_", "dddddddddddd",
               "dbbbbbbbbbbd", "dbbbbbbbbbbd", "dbbbbbbbbbbd", "dbbbbbbbbbbd", "dccccccccccd",
               "dddddddddddd", "____________"],
    "mousepad": ["_d_d_d_d_d__", "dddddddddd__", "d________d__", "d_dddddd_d__", "d________d__",
                 "d_dddddd_d__", "d________d__", "d_dddd___d__", "d________d__", "dddddddddd__",
                 "____________", "____________"],
    "chromium": ["____dddd____", "__ddccbbdd__", "_dccccbbbbd_", "_dcccbbbbbd_", "dbbccbbbbccd",
                 "dbbbbbbbcccd", "dbbbbbbccccd", "dbbccbbbcccd", "_dbccccbbbd_", "_dbbccbbbbd_",
                 "__ddbbbbdd__", "____dddd____"],
    "htop": ["dddddddddddd", "d__________d", "d________d_d", "d___d____d_d", "d___d__d_d_d",
             "d_d_d__d_d_d", "d_d_d_dd_d_d", "d_d_d_dd_d_d", "d_dddddddddd", "d__________d",
             "dddddddddddd", "____________"],
    "micro": ["____________", "________dd__", "_______dbbd_", "______dbbd__", "_____dbbd___",
              "____dbbd____", "___dbbd_____", "___dcd______", "__ddd_______", "__dd________",
              "____________", "____________"],
    "qpdfview": ["dddddddd____", "d______dd___", "d______d_d__", "d______dddd_", "dddddddddddd", "dbbddbbddbbb", "dbdbdbdbdbdd", "dbbddbdbdbbd", "dbdddbdbdbdd", "dbdddbbddbdd", "dddddddddddd"],
    "xarchiver": ["__dddddddd__", "_dbbbbbbbbd_", "dbbbbbbbbbbd", "dddddddddddd", "dbbbbddbbbbd",
                  "dbbbdbbdbbbd", "dbbbbddbbbbd", "dbbbbbbbbbbd", "dbbbbbbbbbbd", "dccccccccccd",
                  "dddddddddddd", "____________"],
    "blueman": ["_____d______", "_____dd_____", "_____d_d____", "__d__d__d___", "___d_d_d____",
                "____ddd_____", "_____d______", "____ddd_____", "___d_d_d____", "__d__d__d___",
                "_____d_d____", "_____dd_____"],
}


def mini(name, light=False):
    """The app's 12x12 label sprite; light: recoloured for the dark taskbar and title bars."""
    p = P(12, 12)
    rows = MINI[name]
    if light:
        # dark lines -> light, mid -> light-mid, light fill -> left clear (the bar is dark)
        rows = [r.replace("b", "_").replace("d", "A").replace("c", "b").replace("A", "a") for r in rows]
    p.grid(0, 0, [r.replace("_", " ") for r in rows])
    return p.centred()


def cartridge(name):
    p = P(28, 28)
    # the shell: light grey-green body, notched top-right corner, shaded right and bottom
    p.poly([(4, 1), (20, 1), (23, 4), (23, 26), (4, 26)], "b")
    p.rect(22, 5, 23, 26, "c")
    p.rect(4, 25, 23, 26, "c")
    p.rect(4, 1, 5, 24, "a")
    for x in range(8, 19, 2):                                      # grip ridges along the top
        p.rect(x, 2, x, 4, "c")
    p.rect(7, 6, 20, 21, "d")                                      # label frame
    p.rect(8, 7, 19, 20, "a")                                      # label
    p.outline()
    for x in range(8, 20, 2):                                      # contacts along the bottom
        p.px(x, 27, "c")
    lab = mini(name)
    p.im.paste(lab.im, (8, 8), lab.im.point(lambda v: 255 if v else 0))
    return p


# ---- power menu: 36x36 art, shown 2x; -focus gets a light ring (the button turns dark) -------------
def power(action):
    p = P(36, 36)
    if action == "sleep":                                          # a moon and Zz
        p.ellipse(4, 8, 27, 31, "b")
        p.ellipse(11, 4, 33, 26, ".")
        p.poly([(8, 22), (12, 28), (18, 30), (10, 26)], "c")
        p.outline()
        p.grid(23, 4, ["dddd", "__d_", "_d__", "dddd"])
        p.grid(29, 10, ["ddd", "_d_", "ddd"])
        return p.centred()
    if action == "reboot":                                         # a thick ring, its end an arrowhead
        cx, cy, r = 17.5, 19.5, 10.5                               # middle of the 6 px band
        p.d.arc((4, 6, 31, 33), -40, 215, fill=IDX["b"], width=6)
        p.d.arc((4, 6, 31, 33), 60, 190, fill=IDX["c"], width=2)
        a = math.radians(215)
        ex, ey = cx + r * math.cos(a), cy + r * math.sin(a)
        tx, ty = -math.sin(a), math.cos(a)                         # clockwise direction there
        nx, ny = math.cos(a), math.sin(a)
        p.poly([(ex + nx * 7, ey + ny * 7), (ex - nx * 7, ey - ny * 7), (ex + tx * 9, ey + ty * 9)], "b")
        p.outline()
        return p.centred()
    if action == "logout":                                         # an open door and an arrow out
        p.rect(2, 3, 17, 32, "c")
        p.rect(4, 5, 15, 32, "d")
        p.poly([(4, 5), (11, 8), (11, 34), (4, 32)], "b")
        p.px(9, 20, "d")
        p.outline()
        p.poly([(19, 15), (26, 15), (26, 10), (34, 18), (26, 26), (26, 21), (19, 21)], "d")
        return p.centred()
    if action == "shutdown":                                       # the power symbol on a button
        p.ellipse(3, 3, 32, 32, "b")
        p.d.arc((3, 3, 32, 32), 20, 160, fill=IDX["c"], width=3)
        p.ellipse(10, 10, 25, 25, None, "d", 3)
        p.rect(15, 6, 20, 15, "b")
        p.rect(16, 7, 19, 18, "d")
        p.outline()
        return p.centred()
    if action == "saver":                                          # a battery and a leaf above it
        p.rect(2, 16, 27, 32, "a")
        p.rect(28, 21, 30, 27, "c")
        for i in range(3):
            p.rect(5 + i * 7, 19, 9 + i * 7, 29, "c")
        p.outline()
        p.poly([(14, 11), (14, 6), (19, 1), (27, 1), (27, 5), (22, 11)], "b")
        p.line([(15, 10), (25, 2)], "c")
        p.outline()
        return p.centred()

# ---- pointer: 24 px art, shown 2x. The arrow is the game-menu glove pointing right (the fingertip
# is the hotspot); links get the same glove pointing up.
GLOVE = ["....ddddd...........", "...daaaaaddddddddd..", "..daaaaaaaaaaaaaaad.",
         ".dbaaaaaaaaaaaaaaaad", ".dbaaaaadddddddddd..", "ddbaaaaaaad.........",
         "dcbaaaaaad..........", "dcbaaaaaaad.........", "dcbaaaaaad..........",
         ".dcbaaaaaad.........", "..ddcccccd..........", "...dddddd..........."]
UP = ["___dd_____", "__daad____", "__daad____", "__daad____", "__daaddddd", "_ddaadaada",
      "dbdaaaaaad", "dbaaaaaaad", "dbaaaaaaad", "_dbaaaaaad", "__dbaaaad_", "__dccccd__",
      "__dddddd__"]
IBEAM = ["ddd_ddd", "___d___", "___d___", "___d___", "___d___", "___d___", "___d___", "___d___",
         "___d___", "___d___", "___d___", "___d___", "___d___", "ddd_ddd"]
COIN = ["___dddd___", "__daaaad__", "_daabbaad_", "daabaaabad", "daabaaabad", "daabaaabad",
        "daabaaabad", "_daabbaad_", "__daaaad__", "___dddd___"]
HOTSPOTS = {"arrow": [19, 3], "hand": [3, 0], "text": [3, 7], "busy": [5, 5], "progress": [19, 3]}


def pointer(shape):
    p = P(24, 24)
    if shape in ("arrow", "progress"):
        glove(p, 0, 0)
        if shape == "progress":
            p.grid(13, 12, [r.replace(".", "_") for r in COIN])
    else:
        rows = {"hand": UP, "text": IBEAM, "busy": COIN}[shape]
        p.grid(0, 0, [r.replace("_", " ") for r in rows])
    return p.centred()


# ---- wallpaper: a dithered landscape, 320x240 doubled ---------------------------------------------------
def wallpaper(w=640, h=480):
    """The handheld's home screen: a dot-matrix LCD (a faint grid every 3 px), the POCKET
    wordmark in big pixels, and 'press START' (the taskbar's START button)."""
    im = Image.new("RGB", (w, h), A)
    d = ImageDraw.Draw(im)
    for y in range(0, h, 3):
        d.line([(0, y), (w, y)], fill=B)
    for x in range(0, w, 3):
        d.line([(x, 0), (x, h)], fill=B)
    letters = {   # 5x7 pixel letters, drawn in 6x6 blocks
        "P": ["####.", "#...#", "#...#", "####.", "#....", "#....", "#...."],
        "O": [".###.", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."],
        "C": [".###.", "#...#", "#....", "#....", "#....", "#...#", ".###."],
        "K": ["#...#", "#..#.", "#.#..", "##...", "#.#..", "#..#.", "#...#"],
        "E": ["#####", "#....", "#....", "####.", "#....", "#....", "#####"],
        "T": ["#####", "..#..", "..#..", "..#..", "..#..", "..#..", "..#.."],
    }

    def word(s, cx, cy, z, col, shadow=None):
        wpx = len(s) * 6 * z - z
        x = cx - wpx // 2
        for ch in s:
            for j, r in enumerate(letters[ch]):
                for i, b in enumerate(r):
                    if b == "#":
                        if shadow:
                            d.rectangle((x + i * z + z // 2, cy + j * z + z // 2,
                                         x + i * z + z - 1 + z // 2, cy + j * z + z - 1 + z // 2), fill=shadow)
                        d.rectangle((x + i * z, cy + j * z, x + i * z + z - 1, cy + j * z + z - 1), fill=col)
            x += 6 * z
    word("POCKET", w // 2, 150, 12, C, shadow=B)
    small = ImageFont.truetype(FONT, 24) if os.path.exists(FONT) else None
    if small:
        d.text((w // 2, 300), "press START", font=small, fill=C, anchor="mm")
    return im


# ---- theme.json and CSS ------------------------------------------------------------------------------
THEME = {
    "schema": 1, "id": "pocket", "name": "Pocket", "base": "light", "author": "Handtop",
    "description": "A pocket game console: four greens on a dot-matrix screen, game menus, hearts for the battery.",
    "palette": {"bg": H["a"], "surface": H["b"], "surface_hi": H["c"], "border": H["d"],
                "fg": H["d"], "fg_dim": H["c"], "accent": H["d"], "accent_fg": H["d"],
                "on_accent": H["a"], "warn": H["c"], "error": H["d"], "brightness": H["c"],
                "success": H["c"]},
    "colors": {
        "taskbar.bg": H["d"], "taskbar.fg": H["a"], "taskbar.border": H["d"],
        "taskbar.apps_bg": H["a"], "taskbar.apps_fg": H["d"], "taskbar.active_bg": H["c"],
        "taskbar.warn": H["b"], "taskbar.critical": H["a"],
        "titlebar.active_bg": H["d"], "titlebar.inactive_bg": H["b"],
        "titlebar.active_fg": H["a"], "titlebar.inactive_fg": H["c"],
        "titlebar.active_button": H["a"], "titlebar.inactive_button": H["c"],
        "drawer.bg": H["a"], "drawer.fg": H["d"], "drawer.entry_bg": H["b"], "drawer.hover_bg": H["c"],
        "powermenu.backdrop": H["b"], "powermenu.button_bg": H["a"], "powermenu.button_border": H["d"],
        "powermenu.fg": H["d"], "powermenu.hover_bg": H["c"], "powermenu.hover_border": H["d"],
        "powermenu.focus": H["c"],
        "notify.bg": H["a"], "notify.fg": H["d"], "notify.border": H["d"],
        "osk.bg": H["b"], "osk.key": H["a"], "osk.border": H["d"], "osk.fg": H["d"],
        "osk.spec": H["b"], "osk.spec_border": H["d"], "osk.spec_fg": H["d"],
        "osk.sel": H["d"], "osk.sel_border": H["d"], "osk.sel_fg": H["a"],
        "osk.latch": H["c"], "osk.latch_sel": H["c"], "osk.latch_border": H["d"],
        "osk.badge": H["c"], "osk.hit": H["c"], "osk.hit_border": H["d"], "osk.hit_fg": H["a"],
        "status.bg": H["a"], "status.body": H["b"], "status.body_edge": H["d"], "status.body_shade": H["c"],
        "status.part": H["c"], "status.part_edge": H["d"], "status.lit": H["d"], "status.lit_edge": H["d"],
        "status.bezel": H["d"], "status.bezel_edge": H["d"], "status.screen": H["c"],
        "status.led": H["d"], "status.cap": H["b"],
        "status.face_x": H["c"], "status.face_y": H["c"], "status.face_a": H["c"], "status.face_b": H["c"],
        "status.label": H["a"], "status.label_lit": H["a"], "status.text": H["d"], "status.dim": H["c"],
        "status.ok": H["d"], "status.warn": H["c"],
        "status.screen_text": H["a"], "status.screen_dim": H["b"], "status.screen_ok": H["a"],
        "status.screen_warn": H["b"],
        "display.bg": H["a"], "display.card": H["b"], "display.card_hi": H["a"], "display.border": H["d"],
        "display.accent": H["d"], "display.text": H["d"], "display.dim": H["c"], "display.body": H["d"],
        "display.off": H["d"], "display.desk": H["c"], "display.bar": H["d"], "display.win": H["a"],
        "display.sun": H["b"], "display.track": H["c"], "display.btn": H["b"],
        "terminal.bg": H["a"], "terminal.fg": H["d"], "terminal.cursor": H["d"],
        "terminal.cursor_text": H["a"], "terminal.selection_bg": H["c"], "terminal.selection_fg": H["a"],
        **{f"terminal.ansi{i}": H[c] for i, c in enumerate("dccccccccccccccd")},
        "osd.bg": H["a"], "osd.volume_border": H["d"], "osd.volume_level": H["d"],
        "osd.brightness_border": H["d"], "osd.brightness_level": H["c"], "osd.text": H["d"],
    },
    "wallpaper": {"color": H["a"], "image": "images/wallpaper.png", "mode": "center"},
    "status_screen": {"style": "solid"},
    "gtk": {"color_scheme": "default", "theme": "Adwaita", "icon_theme": "Adwaita"},
    "cursor": {"size": 24, "hotspots": {k: [v[0] * 2, v[1] * 2] for k, v in HOTSPOTS.items()}},
    "fonts": {"ui": "Pixelify Sans", "mono": "VT323", "scale": 1.0},
    "borders": 2,
}

BD = "border: 2px solid %s;" % H["d"]
# the text-box frame of handheld games: a thick dark line, a light gap, a thin dark line
DOUBLE = ("border: 3px solid %s; box-shadow: inset 0 0 0 3px %s, inset 0 0 0 4px %s;"
          % (H["d"], H["a"], H["d"]))
CSS = {
    "taskbar": f"""/* Pocket: the handheld's dark HUD strip; Apps is the light START pill. */
window#waybar {{ border-top: 2px solid {H["c"]}; }}
#custom-apps {{ margin: 5px 4px 5px 5px; padding: 0 10px 0 28px; border-radius: 10px; font-weight: bold; }}
#custom-apps:hover {{ background-color: {H["b"]}; }}
#taskbar button {{ margin: 4px 1px; padding: 0 6px; border-radius: 0; border: 2px solid transparent; }}
#taskbar button.active {{ background-color: {H["c"]}; border-color: {H["a"]}; }}
#taskbar button:hover {{ background-color: {H["c"]}; }}
#clock {{ padding: 0 10px; font-weight: bold; }}
""",
    "drawer": f"""/* Pocket: a game menu. Every tile is a text box with a double frame; the chosen one goes
   dark (the hover itself comes from css/apps.css, which GTK applies here too and which wins). */
entry {{ border-radius: 0; background-color: {H["a"]}; color: {H["d"]}; {DOUBLE} }}
button {{ border-radius: 0; margin: 4px; {DOUBLE} }}
""",
    "powermenu": f"""/* Pocket: a pause menu. Double-framed boxes; the chosen one goes dark. */
button {{ border-radius: 0; {DOUBLE} }}
button:hover {{ color: {H["a"]}; box-shadow: inset 0 0 0 3px {H["c"]}, inset 0 0 0 5px {H["a"]}; }}
""",
    "apps": f"""/* Pocket: GTK 3 apps in the four greens, on top of Adwaita (light). GTK also applies this
   to the taskbar, app drawer and power menu: the colour rules here are the same as theirs, so
   broad selectors (.view, list, row: white in Adwaita) are safe here. */
* {{ border-radius: 0; -gtk-outline-radius: 0; box-shadow: none; text-shadow: none; -gtk-icon-shadow: none; }}
window, .background, dialog, popover, menu, .menu, menubar, toolbar, .toolbar, statusbar,
notebook > header, notebook > stack, actionbar, .sidebar, placessidebar, paned > separator {{
  background-color: {H["a"]}; background-image: none; color: {H["d"]};
}}
headerbar, .titlebar {{ background-image: none; background-color: {H["d"]}; color: {H["a"]}; border: none; }}
headerbar label, headerbar .title {{ color: {H["a"]}; }}
button {{ background-image: none; background-color: {H["b"]}; color: {H["d"]}; {BD} }}
button:hover {{ background-color: {H["d"]}; color: {H["a"]}; }}
button:hover label, button:hover image {{ color: {H["a"]}; }}
button:hover {{ box-shadow: inset 0 0 0 3px {H["d"]}, inset 0 0 0 4px {H["a"]}; }}
button:active, button:checked {{ background-color: {H["c"]}; color: {H["a"]}; }}
button:disabled {{ color: {H["c"]}; }}
button.flat {{ border-color: transparent; background-color: transparent; }}
button.flat:hover {{ background-color: {H["d"]}; {BD} }}   /* like every hover: dark, light icon */
entry, spinbutton, textview, textview text, treeview, treeview.view, iconview, .view, list, row,
scrolledwindow viewport {{
  background-image: none; background-color: {H["a"]}; color: {H["d"]};
}}
entry, spinbutton {{ {BD} }}
scrolledwindow.frame, frame > border {{ {DOUBLE} }}
*:selected, treeview.view:selected, row:selected, .view:selected, iconview:selected,
entry selection, textview text selection, menuitem:hover, modelbutton:hover,
placessidebar row:selected {{ background-color: {H["c"]}; color: {H["a"]}; }}
row:selected label, menuitem:hover label {{ color: {H["a"]}; }}
check, radio, switch {{ background-image: none; background-color: {H["a"]}; {BD} }}
check:checked, radio:checked, switch:checked {{ background-color: {H["d"]}; color: {H["a"]}; }}
switch slider {{ background-image: none; background-color: {H["b"]}; {BD} }}
scrollbar {{ background-color: {H["b"]}; border: none; }}
scrollbar slider {{ background-color: {H["c"]}; border: 2px solid {H["b"]}; min-width: 8px; min-height: 8px; }}
progressbar trough, scale trough {{ background-image: none; background-color: {H["b"]}; {BD} }}
progressbar progress, scale highlight {{ background-image: none; background-color: {H["d"]}; border: none; }}
scale slider {{ background-image: none; background-color: {H["a"]}; {BD} }}
tooltip, tooltip.background {{ background-color: {H["d"]}; color: {H["a"]}; border: none; }}
tooltip * {{ color: {H["a"]}; }}
separator {{ background-color: {H["c"]}; }}
""",
}


def main(out):
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "src", "theme"))
    from handtop_theme import schema as S
    os.makedirs(out, exist_ok=True)

    def save(img, rel):
        p = os.path.join(out, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        img.save(p)

    with open(os.path.join(out, "theme.json"), "w", encoding="utf-8") as f:
        json.dump(THEME, f, indent=2)
        f.write("\n")
    save(panel_apps().rgba(), "icons/taskbar/apps.png")
    save(panel_power().rgba(), "icons/taskbar/power.png")
    for m in S.INPUT_MODES:
        save(inputmode(m).rgba(), f"icons/taskbar/inputmode-{m}.png")
    for ch in (False, True):
        for low in (False, True):
            for n in range(6):
                for sv in (False, True):
                    name = f"battery{'-charging' if ch else ''}{'-low' if low else ''}-{n}{'-saver' if sv else ''}"
                    save(battery(n, ch, low, sv).rgba(), f"icons/taskbar/{name}.png")
    for w in S.WIFI:
        save(wifi(w).rgba(), f"icons/tray/{w}.png")
    for b in S.BLUETOOTH:
        save(bluetooth(b).rgba(), f"icons/tray/{b}.png")
    for name in S.HANDTOP_APPS + S.DEFAULT_APPS:
        save(big(cartridge(name), 2), f"icons/apps/{name}.png")
        for size in (22, 20):                                      # taskbar buttons and title bars
            small = P(size, size)
            small.im.paste(mini(name, light=True).im, ((size - 12) // 2, (size - 12) // 2))
            save(big(small, 1), f"icons/apps/{name}@{size}.png")
    for act in S.POWER_ACTIONS:
        p = power(act)
        save(big(p, 2), f"icons/power-menu/{act}.png")
        save(big(p.copy().ring("a"), 2), f"icons/power-menu/{act}-focus.png")
    for t in S.USB_TARGETS:
        save(usbtarget(t).rgba(), f"icons/controller/usbtarget-{t}.png")
    for shape in S.CURSOR_SHAPES:
        save(big(pointer(shape), 2), f"cursors/{shape}.png")
    save(wallpaper(), "images/wallpaper.png")
    for part, css in CSS.items():
        p = os.path.join(out, "css", f"{part}.css")
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            f.write(css)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "src/theme/extra/pocket")
