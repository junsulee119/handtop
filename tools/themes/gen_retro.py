"""The Retro theme (90s desktop): grey bevelled panels, navy title bars, a teal desktop and 16-colour
pixel art. Writes a complete theme folder (theme.json, every image slot, its own pointer, CSS);
the fonts are copied in by tools/themes/build-extra-themes.sh from src/theme/extra/retro/fonts.

Original drawings in the style of the time: no logos, no copies of any product's icons.

Usage: python3 tools/themes/gen_retro.py <theme folder>     (src/theme/extra/retro)
Needs Pillow."""
import json
import os
import sys

from PIL import Image

# ---- the 16 colours ---------------------------------------------------------------------------------
PAL = {
    "K": (0, 0, 0), "W": (255, 255, 255), "S": (192, 192, 192), "G": (128, 128, 128),
    "L": (223, 223, 223),                         # the light bevel line
    "N": (0, 0, 128), "B": (0, 0, 255), "T": (0, 128, 128), "A": (0, 255, 255),
    "M": (128, 0, 0), "R": (255, 0, 0), "O": (128, 128, 0), "Y": (255, 255, 0),
    "E": (0, 128, 0), "V": (0, 255, 0), "P": (128, 0, 128), "F": (255, 0, 255),
    "C": (255, 255, 225),                         # tooltip cream
    "Z": (192, 128, 64),                          # cardboard / wood
    "z": (128, 80, 32),                           # its shade
}
HEX = {k: "#%02x%02x%02x" % v for k, v in PAL.items()}


class Art:
    """A small RGBA canvas drawn at 1x."""
    def __init__(self, w, h):
        self.w, self.h = w, h
        self.im = Image.new("RGBA", (w, h), (0, 0, 0, 0))

    def px(self, x, y, c):
        if 0 <= x < self.w and 0 <= y < self.h and c not in (None, "."):
            self.im.putpixel((x, y), PAL[c] + (255,))

    def rect(self, x0, y0, x1, y1, c):
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                self.px(x, y, c)

    def box(self, x0, y0, x1, y1, c):
        for x in range(x0, x1 + 1):
            self.px(x, y0, c)
            self.px(x, y1, c)
        for y in range(y0, y1 + 1):
            self.px(x0, y, c)
            self.px(x1, y, c)

    def hline(self, x0, x1, y, c):
        self.rect(x0, y, x1, y, c)

    def vline(self, x, y0, y1, c):
        self.rect(x, y0, x, y1, c)

    def bevel(self, x0, y0, x1, y1, raised=True, fill="S"):
        """A 90s button: 2 px bevel (white / light top-left, black / grey bottom-right)."""
        self.rect(x0, y0, x1, y1, fill)
        a, b, c, d = ("W", "K", "L", "G") if raised else ("K", "W", "G", "L")
        self.hline(x0, x1, y0, a); self.vline(x0, y0, y1, a)
        self.hline(x0, x1, y1, b); self.vline(x1, y0, y1, b)
        self.hline(x0 + 1, x1 - 1, y0 + 1, c); self.vline(x0 + 1, y0 + 1, y1 - 1, c)
        self.hline(x0 + 1, x1 - 1, y1 - 1, d); self.vline(x1 - 1, y0 + 1, y1 - 1, d)

    def grid(self, x, y, rows):
        for j, r in enumerate(rows):
            for i, c in enumerate(r):
                self.px(x + i, y + j, c)

    def text(self, x, y, s, c):
        for ch in s:
            g = FONT3[ch]
            for j, r in enumerate(g):
                for i, b in enumerate(r):
                    if b == "#":
                        self.px(x + i, y + j, c)
            x += len(g[0]) + 1

    def paste(self, other, x, y):
        self.im.alpha_composite(other.im, (x, y))

    def outlined(self, c="W"):
        """A copy with a 1 px ring of colour c around every drawn pixel (focus icons)."""
        out = Art(self.w, self.h)
        src = self.im.load()
        for y in range(self.h):
            for x in range(self.w):
                if src[x, y][3] == 0 and any(
                        0 <= x + dx < self.w and 0 <= y + dy < self.h and src[x + dx, y + dy][3]
                        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))):
                    out.px(x, y, c)
        out.im.alpha_composite(self.im)
        return out

    def centred(self):
        """The drawing moved so its bounding box sits in the middle of the canvas (rounded down)."""
        b = self.im.getbbox()
        if not b:
            return self
        out = Art(self.w, self.h)
        dx = (self.w - (b[2] - b[0])) // 2 - b[0]
        dy = (self.h - (b[3] - b[1])) // 2 - b[1]
        out.im.alpha_composite(self.im, (max(dx, 0), max(dy, 0)), (max(-dx, 0), max(-dy, 0)))
        return out

    def scaled(self, z):
        return self.im.resize((self.w * z, self.h * z), Image.NEAREST)


FONT3 = {   # 3x5 pixel font for labels on icons
    "S": ["###", "#..", "###", "..#", "###"], "H": ["#.#", "#.#", "###", "#.#", "#.#"],
    "P": ["###", "#.#", "###", "#..", "#.."], "D": ["##.", "#.#", "#.#", "#.#", "##."],
    "F": ["###", "#..", "##.", "#..", "#.."], ">": ["#..", ".#.", "..#", ".#.", "#.."],
    "_": ["...", "...", "...", "...", "###"], " ": ["."],
}


# ---- shared drawings ------------------------------------------------------------------------------------
def window(a, x0, y0, x1, y1, content="W", title="N"):
    """A little application window: black outline, title bar, content area."""
    a.rect(x0, y0, x1, y1, "S")
    a.box(x0, y0, x1, y1, "K")
    a.rect(x0 + 1, y0 + 1, x1 - 1, y0 + 3, title)
    a.px(x1 - 2, y0 + 2, "S"); a.px(x1 - 4, y0 + 2, "S")
    a.rect(x0 + 2, y0 + 5, x1 - 2, y1 - 2, content)
    a.hline(x0 + 2, x1 - 2, y0 + 5, "G"); a.vline(x0 + 2, y0 + 5, y1 - 2, "G")


HANDHELD = [
    ".KKKKKKKKKKKKK.",
    "KSSSSSSSSSSSSSK",
    "KSKSKKKKKKKSRSK",
    "KKKKK.....KBSYK",
    "KSKSK.....KSESK",
    "KSSSKKKKKKKSSSK",
    "KSSSSSSSSSSSSSK",
    "KGGGGGGGGGGGGGK",
    ".KKKKKKKKKKKKK.",
]


def handheld(a, x, y, screen="T", wide=False):
    """A 15x9 handheld in the style of the RG35XX H (generic shape, no brand); wide: 16x9 (the
    screen one pixel wider, for a 16 px icon)."""
    rows = [r[:8] + r[7] + r[8:] for r in HANDHELD] if wide else HANDHELD
    a.grid(x, y, rows)
    a.rect(x + 5, y + 3, x + (10 if wide else 9), y + 4, screen)


def power_symbol(a, cx, cy, r, c, outline="K"):
    """Ring with a gap at the top and a 2 px bar through it. The symbol is centred on the line
    between pixel columns cx - 1 and cx, so the even-width bar sits exactly in the middle."""
    mx = cx - 0.5
    pts = set()
    for y in range(-r - 2, r + 3):
        for x in range(cx - r - 2, cx + r + 3):
            dx = x - mx
            d = (dx * dx + y * y) ** 0.5
            if r - 1.5 <= d <= r + 0.3 and not (y < 0 and abs(dx) <= r * 0.5):
                pts.add((x, cy + y))
    bar = {(x, cy + y) for y in range(-r - 1, 1) for x in (cx - 1, cx)}
    shape = pts | bar
    for (x, y) in shape:
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            if (x + dx, y + dy) not in shape:
                a.px(x + dx, y + dy, outline)
    for (x, y) in shape:
        a.px(x, y, c)


def bt_rune(a, x, y, c):
    """7x11 Bluetooth rune."""
    a.grid(x, y, [r.replace("#", c) for r in [
        "...#...", "...##..", ".#.#.#.", "..###..", "...#...", "..###..", ".#.#.#.",
        "...##..", "...#...", "...#...", "......."]][:10])


def padlock(a, x, y):
    a.grid(x, y, [".KKK.", "K...K", "K...K", "KKKKK", "KYYYK", "KYKYK", "KYYYK", "KKKKK"])


def monitor(a, x, y, screen="T"):
    """13x12 monitor on a stand."""
    a.grid(x, y, [
        "KKKKKKKKKKKKK",
        "KWWWWWWWWWWSK",
        "KWKKKKKKKKKGK",
        "KWK.......KGK",
        "KWK.......KGK",
        "KWK.......KGK",
        "KWKKKKKKKKKGK",
        "KSSSSSSSSSEGK",
        "KGGGGGGGGGGGK",
        "KKKKKKKKKKKKK",
        "....KSSSK....",
        "..KKKKKKKKK..",
    ])
    a.rect(x + 3, y + 3, x + 9, y + 5, screen)


# ---- taskbar ---------------------------------------------------------------------------------------------
def panel_apps():
    a = Art(16, 16)
    handheld(a, 0, 4, wide=True)
    return a


def panel_power():
    a = Art(24, 24)
    power_symbol(a, 12, 12, 7, "R")
    return a


def mouse(a, x, y):
    a.grid(x, y, [
        "..KKKKK..", ".KWWKWWK.", "KWWWKWWWK", "KWWWKWWWK", "KKKKKKKKK", "KWWWWWWWK",
        "KWWWWWWWK", "KWWWWWWWK", "KWWWWWWWK", "KSWWWWWSK", ".KSSSSSK.", "..KKKKK..",
    ])


def inputmode(mode):
    a = Art(23, 23)
    if mode == "desktop":
        mouse(a, 7, 4)
        a.vline(11, 1, 3, "K")
        a.grid(9, 0, ["KK.", "..K"])
    else:
        handheld(a, 4, 8)
        if mode == "gamepad":
            a.grid(9, 2, ["KK.KK", "KYKYK", ".KYK.", "KYKYK", "KK.KK"][:0])
        elif mode == "bt":
            # a navy badge with the Bluetooth rune above the handheld (drawn again lower down)
            a = Art(23, 23)
            a.grid(7, 0, [
                ".KKKKKKK.",
                "KNNNNNNNK",
                "KNNNWNNNK",
                "KNNNWWNNK",
                "KNWNWNWNK",
                "KNNWWWNNK",
                "KNNNWNNNK",
                "KNNWWWNNK",
                "KNWNWNWNK",
                "KNNNWWNNK",
                "KNNNWNNNK",
                "KNNNNNNNK",
                ".KKKKKKK.",
            ])
            handheld(a, 4, 14)
        elif mode == "wired":
            # a USB plug on its cable, plugged into the top of the handheld
            a = Art(23, 23)
            a.grid(8, 0, [
                ".KKKKK.",
                ".KSKSK.",
                ".KSSSK.",
                "KKKKKKK",
                "KGGGGGK",
                "KGGGGGK",
                "KGGGGGK",
                ".KKKKK.",
                "...K...",
                "...K...",
                "...K...",
                "...K...",
            ])
            handheld(a, 4, 12)
    return a


def battery(n, charging=False, low=False, saver=False):
    a = Art(20, 11)
    a.rect(0, 0, 17, 10, "W")
    a.box(0, 0, 17, 10, "K")
    a.rect(18, 3, 19, 7, "K")
    fill = "R" if low else ("E" if saver else "N")
    for i in range(n):
        a.rect(2 + i * 3, 2, 3 + i * 3, 8, fill)
    if saver:
        a.box(0, 0, 17, 10, "E")
        a.rect(18, 3, 19, 7, "E")
    if charging:
        a.grid(6, 1, ["...KKKK", "..KYYK.", ".KYYK..", "KYYYYYK", "..KYYK.", ".KYYK..",
                      ".KYK...", "KK.....", "K......"])
    return a


# ---- tray ------------------------------------------------------------------------------------------------
def signal_bars(a, lit, grey=False):
    for i in range(4):
        h = 4 + 3 * i
        x0, y1 = 4 + 4 * i, 18
        on = i < lit and not grey
        a.rect(x0, y1 - h + 1, x0 + 2, y1, "K" if on else "W")
        a.box(x0, y1 - h + 1, x0 + 2, y1, "K" if on else "G")


def wifi(name):
    a = Art(23, 23)
    secure = name.endswith("-secure")
    base = name[:-7] if secure else name
    if base.startswith("nm-signal-"):
        signal_bars(a, {"00": 0, "25": 1, "50": 2, "75": 3, "100": 4}[base.split("-")[2]])
    elif base == "nm-no-connection":
        signal_bars(a, 0, grey=True)
        a.grid(0, 0, ["R...R", "RR.RR", ".RRR.", "RR.RR", "R...R"])
    elif base.startswith("nm-stage"):
        stage, frame = int(base[8:10]), int(base[-2:])
        signal_bars(a, frame % 5)
        for i in range(stage):
            a.rect(1 + 3 * i, 1, 2 + 3 * i, 2, "E")
    elif base.startswith("nm-device-wired"):
        monitor(a, 5, 3)
        a.hline(11, 11, 15, "K")
        a.vline(11, 15, 21, "K")
        a.hline(4, 18, 21, "K")
        a = a.centred()
    if secure:
        padlock(a, 0, 0)
    return a


def bluetooth(state):
    a = Art(23, 23)
    fill, edge = ("G", "K") if state == "blueman-disabled" else ("N", "K")
    a.rect(6, 3, 16, 19, fill)
    a.box(6, 3, 16, 19, edge)
    a.px(6, 3, "."); a.px(16, 3, "."); a.px(6, 19, "."); a.px(16, 19, ".")
    a.grid(8, 6, [r.replace("#", "S" if state == "blueman-disabled" else "W") for r in [
        "...#...", "...##..", ".#.#.#.", "..###..", "...#...", "..###..", ".#.#.#.",
        "...##..", "...#..."]])
    if state == "blueman-active":
        a.rect(17, 16, 21, 20, "V")
        a.box(17, 16, 21, 20, "K")
    return a


# ---- External Controller's USB cable card (shown at 2x) --------------------------------------------------
def usbtarget(t):
    a = Art(23, 23)
    if t == "pc":
        monitor(a, 5, 1)
        a.rect(2, 15, 20, 19, "S")
        a.box(2, 15, 20, 19, "K")
        for x in range(4, 19, 2):
            a.px(x, 17, "G")
    else:
        a.rect(1, 1, 21, 13, "K")
        a.rect(3, 3, 19, 11, "T")
        a.rect(9, 14, 13, 14, "K")
        a.grid(3, 15, [
            ".KKKKKKKKKKKKKKK.", "KSSSSSSSSSSSSSSSK", "KSKSSSSSSSSSSBSSK", "KKKKSSSSSSSSYSRSK",
            "KSKSSSSSSSSSSESSK", ".KKKKKKKKKKKKKKK."])
    return a


# ---- app icons: 28x28 art, shown 2x (56 px) -------------------------------------------------------------
def app(name):
    a = Art(28, 28)
    if name == "foot":
        window(a, 1, 3, 26, 24, content="K")
        a.text(5, 11, ">_", "S")
    elif name == "thunar":
        # a folder: tab, back edge, white highlight, yellow front with olive shade, grey shadow
        rows = ["..KKKKKKK".ljust(28, "."), ".KYYYYYYYK".ljust(28, "."),
                "KYYYYYYYYY" + "K" * 17 + ".", "K" + "W" * 24 + "YK."]
        rows += ["KW" + "Y" * 23 + "OKG"] * 13
        rows += ["K" + "O" * 25 + "KG", "K" * 27 + "G", "." + "G" * 27]
        assert all(len(r) == 28 for r in rows), rows
        a.grid(0, 4, rows)
    elif name == "mousepad":
        a.rect(5, 3, 22, 25, "W")
        a.box(4, 3, 23, 26, "K")
        a.vline(24, 4, 27, "G"); a.hline(5, 24, 27, "G")
        a.rect(5, 4, 22, 6, "B")
        for x in range(6, 22, 3):
            a.grid(x, 1, ["K", "S", "K", "K"])
        for y in range(10, 25, 3):
            a.hline(7, 20, y, "A")
        a.vline(9, 7, 25, "R")
    elif name == "chromium":
        g = [
            "........KKKKKKKK........",
            "......KKBBBBBBBBKK......",
            ".....KBBBVVBBBBBBBK.....",
            "....KBBVVVVVBBBBBWBK....",
            "...KBBVVVVVVVBBBBWWBK...",
            "..KBBBVVVVVVBBBBBBBBBK..",
            "..KBBBBVVVVBBBBVVVBBBK..",
            ".KBBBBBVVVBBBBVVVVVVBBK.",
            ".KBBBBBBVVBBBVVVVVVVVBK.",
            ".KBBBBBBBBBBBVVVVVVVVBK.",
            "KBBBBBBBBBBBBBVVVVVVBBBK",
            "KBBBBBBBBBBBBBBVVVVBBBBK",
            "KBBBVVVBBBBBBBBVVVBBBBBK",
            "KBBVVVVVBBBBBBBBVVBBBBBK",
            "KBBVVVVVVBBBBBBBBBBBBBNK",
            ".KBBVVVVVVBBBBBBBBBBBNK.",
            ".KBBBVVVVVBBBBBBBBBBNNK.",
            ".KBBBBVVVVBBBBBBBBBNNNK.",
            "..KBBBBVVBBBBBBBBNNNNK..",
            "..KBBBBBVBBBBBBBNNNNNK..",
            "...KBBBBBBBBBBNNNNNNK...",
            "....KBBBBBBBNNNNNNNK....",
            ".....KKNNNNNNNNNNKK.....",
            ".......KKKKKKKKKK.......",
        ]
        a.grid(2, 2, g)
    elif name == "htop":
        window(a, 1, 3, 26, 24, content="K")
        heights = [5, 9, 7, 12, 4, 10, 8]
        for i, h in enumerate(heights):
            c = "R" if h >= 11 else ("Y" if h >= 9 else "V")
            a.rect(5 + i * 3, 22 - h, 6 + i * 3, 21, c)
    elif name == "micro":
        window(a, 1, 3, 24, 24)
        for y, w in ((10, 14), (13, 10), (16, 15), (19, 8)):
            a.hline(5, 5 + w, y, "K")
        a.grid(13, 11, [
            ".........KK.", "........KRRK", ".......KYKRK", "......KYYK..", ".....KYYK...",
            "....KYYK....", "...KYYK.....", "..KYYK......", ".KSSK.......", ".KKK........",
            "KK..........", "",
        ][:11])
    elif name == "qpdfview":
        # one page with a folded corner (drawn as a single outline), text lines and a red PDF band
        page = (["KKKKKKKKKKKKK.....", "KWWWWWWWWWWWKK....", "KWWWWWWWWWWWKSK...",
                 "KWWWWWWWWWWWKSSK..", "KWWWWWWWWWWWKSSSK.", "KWWWWWWWWWWWKKKKKK"]
                + ["KWWWWWWWWWWWWWWWWK"] * 18 + ["KKKKKKKKKKKKKKKKKK"])
        a.grid(5, 1, page)
        a.vline(23, 7, 26, "G"); a.hline(6, 23, 26, "G")
        for y in (4, 6, 9, 11):
            a.hline(8, 15 if y < 7 else 19, y, "G")
        a.rect(6, 14, 21, 21, "M")
        a.text(8, 16, "PDF", "W")
    elif name == "xarchiver":
        a.rect(3, 8, 24, 25, "Z")
        a.box(2, 7, 25, 26, "K")
        a.grid(2, 3, [
            "...KKKKKKKKKKKKKKKKKK...",
            "..KZZZZZZZZZZZZZZZZZZK..",
            ".KZZZZZZZZZZZZZZZZZZZZK.",
            "KKKKKKKKKKKKKKKKKKKKKKKK",
        ])
        a.hline(3, 24, 8, "Y")
        a.vline(24, 9, 25, "z"); a.hline(3, 24, 25, "z")
        for y in range(8, 26):
            a.px(13, y, "K"); a.px(14, y, "K")
            if y % 2 == 0:
                a.px(12, y, "S"); a.px(15, y + 1 if y + 1 <= 25 else y, "S")
        a.rect(11, 13, 16, 17, "S")
        a.box(11, 13, 16, 17, "K")
    elif name == "blueman":
        a.rect(5, 2, 22, 25, "N")
        a.box(4, 1, 23, 26, "K")
        a.px(4, 1, "."); a.px(23, 1, "."); a.px(4, 26, "."); a.px(23, 26, ".")
        a.hline(5, 22, 2, "B"); a.vline(5, 2, 25, "B")
        rune = ["....##....", "....###...", "....#.##..", ".#..#..##.", "..#.#.##..", "...###....",
                "....#.....", "...###....", "..#.#.##..", ".#..#..##.", "....#.##..", "....###...",
                "....##....", ]
        for j, r in enumerate(rune):
            for i, c in enumerate(r):
                if c == "#":
                    a.rect(9 + i, 7 + j, 9 + i, 7 + j, "W")
    elif name == "theme":
        a.grid(1, 4, [
            ".......KKKKKKKKKK.......",
            ".....KKZZZZZZZZZZKK.....",
            "...KKZZZZZZZZZZZZZZKK...",
            "..KZZZRRZZZZYYZZZZZZZK..",
            ".KZZZRRRRZZYYYYZZZZZZZK.",
            ".KZZZZRRZZZZYYZZZZVVZZK.",
            "KZZZZZZZZZZZZZZZZVVVVZZK",
            "KZZBBZZZZZZZZZZZZZVVZZZK",
            "KZBBBBZZZZKKKZZZZZZZZZZK",
            "KZZBBZZZZK...KZZZZZZZZZK",
            "KZZZZZZZZK...KZZZFFZZZK.",
            ".KZZZZZZZZKKKZZZFFFFZZK.",
            ".KZZZZZZZZZZZZZZZFFZZK..",
            "..KZZZZZZZZZZZZZZZZZK...",
            "...KKzzzzzzzzzzzzKK.....",
            ".....KKKKKKKKKKKK.......",
        ])
        a.grid(17, 0, [
            "........KK", ".......KSK", "......KSK.", ".....KSK..", "....KMK...",
            "...KMK....", "..KNK.....", ".KNK......", "KNK.......", "KK........",
        ])
    elif name == "external-controller":
        a.vline(13, 1, 8, "K")
        a.rect(11, 1, 15, 3, "S"); a.box(11, 1, 15, 3, "K")
        a.grid(2, 9, [
            "...KKKKKKKKKKKKKKKKKKKK...",
            "..KSSSSSSSSSSSSSSSSSSSSK..",
            ".KSSSSSSSSSSSSSSSSSSSBSSK.",
            "KSSSKKSSSSSSSSSSSSSSBBBSSK",
            "KSSSKKSSSSSSSSSSSSYYSBSRRK",
            "KSKKKKKKSSSKKSKKSYYYSSRRRK",
            "KSKKKKKKSSSSSSSSSSYYSESRRK",
            "KSSSKKSSSSSSSSSSSSSSEEESSK",
            "KSSSKKSSSSSSSSSSSSSSSESSSK",
            "KSSSSSSSSSKKKKKKSSSSSSSSSK",
            "KGSSSSSSSK......KSSSSSSSGK",
            ".KGGGGGGK........KGGGGGGK.",
            "..KKKKKK..........KKKKKK..",
        ])
    elif name == "display":
        g = Art(13, 12)
        monitor(g, 0, 0)
        a.im.alpha_composite(g.scaled(2), (1, 2))
    elif name == "enable-ssh":
        window(a, 1, 2, 26, 21, content="K")
        a.text(5, 9, "SSH", "V")
        a.text(5, 15, ">_", "S")
        a.grid(14, 18, [
            ".KKKK.........", "KYYYYK........", "KYKKYKKKKKKKKK", "KYKKYYYYYYYYYK",
            "KYYYYKKKKYKYKK", ".KKKK....K.K..",
        ])
    elif name == "recenter-sticks":
        a.grid(3, 2, [
            "........KKKKKK........",
            "......KKRRRRRRKK......",
            ".....KRRWWRRRRRRK.....",
            "....KRRWWRRRRRRRRK....",
            "....KRRRRRRRRRRRRK....",
            "....KRRRRRRRRRRRMK....",
            ".....KRRRRRRRRMMK.....",
            "......KKMMMMMMKK......",
            "........KKSSKK........",
            "..........KK..........",
            "..........KK..........",
            "..........KK..........",
            "..........KK..........",
            "......KKKKKKKKKK......",
            "...KKKSSSSSSSSSSKKK...",
            ".KKSSSSSSSSSSSSSSSSKK.",
            "KSSSSSSSSSSSSSSSSSSSSK",
            "KWWWWWWWWWWWWWWWWWWWSK",
            "KGGGGGGGGGGGGGGGGGGGGK",
            "KKKKKKKKKKKKKKKKKKKKKK",
        ])
        for j, w in enumerate((1, 2, 3, 4, 3, 2, 1)):        # arrows pointing at the stick
            a.hline(0, w - 1, 5 + j, "N")
            a.hline(28 - w, 27, 5 + j, "N")
    return a


# ---- power menu: 36x36 art, shown 2x (72 px); -focus: white outline for the navy highlight ----------------
def power(action):
    a = Art(36, 36)
    if action == "sleep":
        moon = []
        for y in range(36):
            for x in range(36):
                d1 = ((x - 16) ** 2 + (y - 19) ** 2) ** 0.5
                d2 = ((x - 23) ** 2 + (y - 13) ** 2) ** 0.5
                if d1 <= 12.5 and d2 > 10:
                    moon.append((x, y))
        s = set(moon)
        for x, y in moon:
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                if (x + dx, y + dy) not in s:
                    a.px(x + dx, y + dy, "K")
        for x, y in moon:
            a.px(x, y, "Y" if (x - 16) * 0.6 + (y - 19) < 6 else "O")
        for sx, sy in ((28, 4), (31, 13)):
            a.grid(sx - 2, sy - 2, ["..K..", "..W..", "KWYWK", "..W..", "..K.."])
    elif action == "reboot":
        # a ring open at the top right, its top end turning into an arrowhead pointing clockwise
        import math
        cx, cy, ro, ri = 17.5, 19.5, 12.5, 7.5
        shape, shade = set(), set()
        for y in range(36):
            for x in range(36):
                dx, dy = x + 0.5 - cx, y + 0.5 - cy
                d = math.hypot(dx, dy)
                ang = math.degrees(math.atan2(dy, dx))          # 0 = right, -90 = top
                if ri <= d <= ro and not (-90 < ang < -25):
                    shape.add((x, y))
                    if dx + dy > 4:
                        shade.add((x, y))
        top = int(cy - ro)                                      # the ring's top end, x 16..17
        for i in range(8):                                      # arrowhead: base at x 17, tip x 24
            for y in range(top - 3 + i, top + 9 - i):
                shape.add((17 + i, y))
        for (x, y) in list(shape):
            for ddx, ddy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                if (x + ddx, y + ddy) not in shape:
                    a.px(x + ddx, y + ddy, "K")
        for (x, y) in shape:
            a.px(x, y, "E" if (x, y) in shade else "V")
    elif action == "logout":
        # a closed door, and an arrow beside it going out to the right
        a.rect(3, 3, 16, 32, "Z")
        a.box(2, 2, 17, 33, "K")
        a.box(5, 5, 14, 15, "z")
        a.box(5, 18, 14, 30, "z")
        a.rect(13, 16, 14, 17, "Y")
        a.box(12, 15, 15, 18, "K")
        a.rect(13, 16, 14, 17, "Y")
        a.grid(19, 10, [
            "........K.......",
            "........KK......",
            "........KNK.....",
            "........KNNK....",
            "KKKKKKKKKNNNK...",
            "KNNNNNNNNNNNNK..",
            "KNNNNNNNNNNNNNK.",
            "KNNNNNNNNNNNNNNK",
            "KNNNNNNNNNNNNNK.",
            "KNNNNNNNNNNNNK..",
            "KKKKKKKKKNNNK...",
            "........KNNK....",
            "........KNK.....",
            "........KK......",
            "........K.......",
        ])
    elif action == "shutdown":
        power_symbol(a, 18, 19, 12, "R")
        inner = Art(36, 36)
        power_symbol(inner, 18, 19, 12, "R")
    elif action == "saver":
        a.rect(3, 9, 28, 28, "W")
        a.box(2, 8, 29, 29, "K")
        a.rect(30, 14, 32, 23, "K")
        for i in range(3):
            a.rect(5 + i * 6, 11, 9 + i * 6, 26, "E")
        a.grid(13, 2, [
            "...........KKKK",
            ".........KKVVVK",
            ".......KKVVVVVK",
            "......KVVVVVVK.",
            ".....KVVVEVVVK.",
            ".....KVVEVVVK..",
            "....KVVEVVKK...",
            "....KVEVKK.....",
            "...KEKKK.......",
            "..KEK..........",
        ])
    return a


# ---- pointer: 24x24 art, written 2x (48 px) -----------------------------------------------------------
ARROW = ["K...........", "KK..........", "KWK.........", "KWWK........", "KWWWK.......",
         "KWWWWK......", "KWWWWWK.....", "KWWWWWWK....", "KWWWWWWWK...", "KWWWWWWWWK..",
         "KWWWWWKKKKK.", "KWWKWWK.....", "KWK.KWWK....", "KK..KWWK....", "K....KWWK...",
         ".....KWWK...", "......KK...."]
HAND = ["....KK.........", "...KWWK........", "...KWWK........", "...KWWK........",
        "...KWWKKK......", "...KWWKWWKKK...", "...KWWKWWKWWKK.", "KKKKWWKWWKWWKWK",
        "KWWKWWWWWWWWKWK", "KWWWWWWWWWWWWWK", ".KWWWWWWWWWWWWK", "..KWWWWWWWWWWWK",
        "..KWWWWWWWWWWK.", "...KWWWWWWWWWK.", "....KWWWWWWWK..", "....KWWWWWWWK..",
        "....KKKKKKKKK.."]
IBEAM = ["KKK.KKK", "...K...", "...K...", "...K...", "...K...", "...K...", "...K...",
         "...K...", "...K...", "...K...", "...K...", "...K...", "...K...", "...K...",
         "KKK.KKK"]
GLASS = ["KKKKKKKKKKK", "KSSSSSSSSSK", "KKKKKKKKKKK", ".KWWWWWWWK.", ".KWYYYYYWK.",
         "..KWYYYWK..", "...KWYWK...", "....KYK....", "...KWYWK...", "..KWWYWWK..",
         ".KWWWYWWWK.", ".KWYYYYYWK.", "KKKKKKKKKKK", "KSSSSSSSSSK", "KKKKKKKKKKK"]
MINIGLASS = ["KKKKKKK", "KSSSSSK", ".KYYYK.", "..KYK..", ".KWYWK.", "KYYYYYK", "KKKKKKK"]


def pointer(shape):
    a = Art(24, 24)
    if shape == "arrow":
        a.grid(0, 0, ARROW)
    elif shape == "hand":
        a.grid(0, 0, HAND)
    elif shape == "text":
        a.grid(0, 0, IBEAM)
    elif shape == "busy":
        a.grid(0, 0, GLASS)
    elif shape == "progress":
        a.grid(0, 0, ARROW)
        a.grid(10, 11, MINIGLASS)
    return a


HOTSPOTS = {"arrow": [0, 0], "hand": [9, 0], "text": [7, 14], "busy": [11, 14], "progress": [0, 0]}   # 48 px units


# ---- theme.json and CSS ------------------------------------------------------------------------------------
THEME = {
    "schema": 1,
    "id": "retro",
    "name": "Retro",
    "base": "light",
    "author": "Handtop",
    "description": "A 90s desktop: grey bevelled buttons, navy title bars, a teal desktop.",
    "palette": {
        "bg": HEX["S"], "surface": HEX["S"], "surface_hi": HEX["N"], "border": HEX["G"],
        "fg": HEX["K"], "fg_dim": HEX["G"], "accent": HEX["N"], "accent_fg": HEX["N"],
        "on_accent": HEX["W"], "warn": "#806000", "error": "#c00000", "brightness": HEX["O"],
        "success": HEX["E"],
    },
    "colors": {
        "taskbar.border": HEX["W"], "taskbar.apps_bg": HEX["S"], "taskbar.apps_fg": HEX["K"],
        "taskbar.active_bg": HEX["L"],
        "titlebar.active_bg": HEX["N"], "titlebar.inactive_bg": HEX["G"],
        "titlebar.active_fg": HEX["W"], "titlebar.inactive_fg": HEX["S"],
        "titlebar.active_button": HEX["W"], "titlebar.inactive_button": HEX["S"],
        "drawer.bg": HEX["S"] + "f7", "drawer.entry_bg": HEX["W"], "drawer.hover_bg": HEX["N"] + "40",
        "powermenu.backdrop": HEX["T"] + "e6", "powermenu.button_bg": HEX["S"],
        "powermenu.button_border": HEX["K"], "powermenu.hover_bg": HEX["N"],
        "powermenu.hover_border": HEX["K"], "powermenu.focus": HEX["K"],
        "notify.bg": HEX["C"], "notify.fg": HEX["K"], "notify.border": HEX["K"],
        "osk.bg": HEX["S"], "osk.key": HEX["S"], "osk.border": HEX["K"], "osk.fg": HEX["K"],
        "osk.spec": HEX["L"], "osk.spec_border": HEX["K"], "osk.spec_fg": HEX["N"],
        "osk.sel": HEX["N"], "osk.sel_border": HEX["K"], "osk.sel_fg": HEX["W"],
        "osk.latch": HEX["Y"], "osk.latch_sel": "#c0c000", "osk.latch_border": HEX["K"],
        "osk.hit": HEX["G"],
        "status.bg": HEX["T"], "status.body": HEX["S"], "status.body_edge": HEX["K"],
        "status.text": HEX["W"], "status.dim": HEX["L"], "status.ok": HEX["V"], "status.warn": HEX["Y"],
        "status.lit": HEX["Y"], "status.label": HEX["K"],
        "display.bg": HEX["S"], "display.card": HEX["L"], "display.card_hi": HEX["W"],
        "display.border": HEX["K"], "display.accent": HEX["N"], "display.desk": HEX["T"],
        "display.btn": HEX["L"],
        "terminal.bg": "#000000", "terminal.fg": "#aaaaaa", "terminal.cursor": "#aaaaaa",
        "terminal.cursor_text": "#000000", "terminal.selection_bg": "#aaaaaa",
        "terminal.selection_fg": "#000000",
        **{f"terminal.ansi{i}": c for i, c in enumerate([
            "#000000", "#aa0000", "#00aa00", "#aa5500", "#0000aa", "#aa00aa", "#00aaaa", "#aaaaaa",
            "#555555", "#ff5555", "#55ff55", "#ffff55", "#5555ff", "#ff55ff", "#55ffff", "#ffffff"])},
        "osd.bg": HEX["S"] + "f2", "osd.volume_border": HEX["K"], "osd.volume_level": HEX["N"],
        "osd.brightness_border": HEX["K"], "osd.brightness_level": HEX["O"], "osd.text": HEX["K"],
    },
    "wallpaper": {"color": HEX["T"], "image": "images/wallpaper.png", "mode": "tile"},
    "status_screen": {"style": "solid"},
    "gtk": {"color_scheme": "default", "theme": "Adwaita", "icon_theme": "Adwaita"},
    "cursor": {"size": 24, "hotspots": HOTSPOTS},
    "fonts": {"ui": "W95FA", "mono": "PxPlus IBM VGA 8x16", "scale": 1.0},
    "borders": 1,
}

RAISED = "border: 1px solid; border-color: #ffffff #000000 #000000 #ffffff; box-shadow: inset -1px -1px #808080, inset 1px 1px #dfdfdf;"
SUNKEN = "border: 1px solid; border-color: #808080 #ffffff #ffffff #808080; box-shadow: inset 1px 1px #000000, inset -1px -1px #dfdfdf;"
PRESSED = "border: 1px solid; border-color: #000000 #ffffff #ffffff #000000; box-shadow: inset 1px 1px #808080, inset -1px -1px #dfdfdf;"

CSS = {
    "taskbar": f"""/* Retro: raised Apps button and window buttons, a sunken clock. Margins 2 px above, 3 below:
   the buttons share the icons' centre line (the icons sit 1 px above the bar's middle). */
window#waybar {{ box-shadow: inset 0 1px #dfdfdf; }}
#custom-apps {{ margin: 2px 2px 3px 3px; padding: 0 8px 0 29px; background-color: #c0c0c0; {RAISED} }}
#custom-apps:hover {{ background-color: #c0c0c0; }}
#taskbar button {{ margin: 2px 2px 3px 2px; padding: 0 6px; background-color: #c0c0c0; {RAISED} }}
#taskbar button.active {{ background-color: #dfdfdf; {PRESSED} }}
#taskbar button:hover {{ background-color: #c0c0c0; }}
#clock {{ margin: 2px 3px 3px 2px; padding: 0 8px; {SUNKEN} box-shadow: none; }}
""",
    "drawer": f"""/* Retro: a grey dialog with a white sunken search field. */
entry {{ background-color: #ffffff; color: #000000; border-radius: 0; {SUNKEN} }}
/* hover: apps.css's lighter grey (it applies here too and wins), black text */
#pinned-box {{ border-bottom: 1px solid #808080; }}
""",
    "powermenu": f"""/* Retro: square raised buttons, navy when highlighted. */
button {{ border-radius: 0; {RAISED} }}
button:hover {{ color: #ffffff; {RAISED} }}
button:focus {{ outline: 1px dotted #000000; outline-offset: -8px; }}
""",
    "apps": f"""/* Retro: a 90s look for GTK 3 apps, on top of Adwaita (light). GTK applies this file to
   every GTK 3 program, the taskbar, app drawer and power menu included. */
* {{ border-radius: 0; -gtk-outline-radius: 0; }}
window, .background, dialog, popover, menu, .menu, menubar, toolbar, .toolbar, statusbar,
notebook > header, actionbar, .sidebar, placessidebar, paned > separator {{
  background-color: #c0c0c0; background-image: none; color: #000000;
}}
headerbar, .titlebar {{
  background-image: linear-gradient(to right, #000080, #1084d0); color: #ffffff;
  border: none; box-shadow: none; min-height: 24px; padding: 0 4px;
}}
headerbar label, .titlebar label, headerbar .title {{ color: #ffffff; font-weight: bold; }}
headerbar button {{ color: #000000; min-height: 16px; min-width: 16px; padding: 0 4px; }}
button, headerbar button, combobox button, spinbutton button {{
  background-color: #c0c0c0; background-image: none; color: #000000; text-shadow: none;
  -gtk-icon-shadow: none; {RAISED}
}}
button:hover {{ background-color: #c8c8c8; background-image: none; }}
button:active, button:checked {{ background-color: #dfdfdf; background-image: none; {PRESSED} }}
button:disabled {{ color: #808080; background-color: #c0c0c0; }}
button.flat {{ border-color: transparent; box-shadow: none; background-color: transparent; }}
button.flat:hover {{ {RAISED} background-color: #c0c0c0; }}
entry, spinbutton, textview, textview text, treeview, treeview.view, iconview {{
  background-color: #ffffff; color: #000000;
}}
entry, spinbutton {{ background-image: none; {SUNKEN} }}
entry:focus {{ {SUNKEN} }}
scrolledwindow.frame, frame > border {{ {SUNKEN} }}
*:selected, treeview.view:selected, row:selected, entry selection, textview text selection,
.view:selected, iconview:selected, menuitem:hover, menu menuitem:hover, modelbutton:hover,
placessidebar row:selected {{
  background-color: #000080; color: #ffffff;
}}
menuitem:hover label, menu menuitem:hover label, row:selected label {{ color: #ffffff; }}
menu, .menu, popover {{ {RAISED} padding: 2px; }}
menubar > menuitem:hover {{ background-color: #000080; color: #ffffff; }}
check, radio {{
  background-color: #ffffff; background-image: none; color: #000000; {SUNKEN}
  min-width: 13px; min-height: 13px;
}}
radio {{ border-radius: 50%; }}
switch {{ background-color: #ffffff; background-image: none; {SUNKEN} }}
switch:checked {{ background-color: #000080; }}
switch slider {{ background-color: #c0c0c0; background-image: none; {RAISED} }}
notebook > header tab {{ background-color: #c0c0c0; {RAISED} border-bottom: none; margin: 0 1px; }}
notebook > header tab:checked {{ background-color: #c0c0c0; padding-bottom: 6px; }}
notebook > stack {{ background-color: #c0c0c0; }}
scrollbar {{
  -GtkScrollbar-has-backward-stepper: true; -GtkScrollbar-has-forward-stepper: true;
  background-color: #dfdfdf; background-image: none; border: none;
}}
scrollbar slider {{
  min-width: 14px; min-height: 14px; margin: 0; background-color: #c0c0c0; {RAISED}
}}
scrollbar button {{ min-width: 14px; min-height: 14px; padding: 0; {RAISED} }}
scrollbar.overlay-indicator:not(.dragging):not(.hovering) slider {{ min-width: 6px; min-height: 6px; }}
progressbar trough {{ background-color: #ffffff; {SUNKEN} min-height: 14px; }}
progressbar progress {{ background-color: #000080; background-image: none; border: none; min-height: 10px; }}
scale trough {{ background-color: #ffffff; {SUNKEN} }}
scale highlight {{ background-color: #000080; background-image: none; }}
scale slider {{ background-color: #c0c0c0; background-image: none; {RAISED} min-width: 10px; min-height: 18px; }}
tooltip, tooltip.background {{ background-color: #ffffe1; color: #000000; border: 1px solid #000000; box-shadow: none; }}
tooltip * {{ color: #000000; }}
separator {{ background-color: #808080; min-height: 1px; min-width: 1px; }}
""",
}


# ---- wallpaper: teal bricks, one 16 px tile drawn at 2x and tiled by the desktop --------------------
def wallpaper_tile():
    """Rows of 8x4 bricks, every other row shifted half a brick: a dark mortar line on top and on
    the left, a light top edge, teal inside."""
    shade = {"mortar": (0, 96, 96), "edge": (0, 160, 160), "face": PAL["T"]}
    im = Image.new("RGB", (16, 16))
    for y in range(16):
        shift = 4 if (y // 4) % 2 else 0
        for x in range(16):
            bx = (x + shift) % 8
            part = "mortar" if y % 4 == 0 or bx == 0 else "edge" if y % 4 == 1 else "face"
            im.putpixel((x, y), shade[part])
    return im.resize((32, 32), Image.NEAREST)


def main(out):
    os.makedirs(out, exist_ok=True)
    data = dict(THEME)
    with open(os.path.join(out, "theme.json"), "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        f.write("\n")

    def save(art, rel, z=1):
        p = os.path.join(out, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        (art.scaled(z) if z > 1 else art.im).save(p)

    os.makedirs(os.path.join(out, "images"), exist_ok=True)
    wallpaper_tile().save(os.path.join(out, "images", "wallpaper.png"))
    save(panel_apps(), "icons/taskbar/apps.png")
    save(panel_power(), "icons/taskbar/power.png")
    for m in ("desktop", "gamepad", "bt", "wired"):
        save(inputmode(m).centred(), f"icons/taskbar/inputmode-{m}.png")
    for ch in (False, True):
        for low in (False, True):
            for n in range(6):
                for sv in (False, True):
                    name = f"battery{'-charging' if ch else ''}{'-low' if low else ''}-{n}{'-saver' if sv else ''}"
                    save(battery(n, ch, low, sv), f"icons/taskbar/{name}.png")
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "src", "theme"))
    from handtop_theme import schema as S
    for w in S.WIFI:
        save(wifi(w), f"icons/tray/{w}.png")
    for b in S.BLUETOOTH:
        save(bluetooth(b), f"icons/tray/{b}.png")
    for name in S.HANDTOP_APPS + S.DEFAULT_APPS:
        save(app(name).centred(), f"icons/apps/{name}.png", 2)
    for act in S.POWER_ACTIONS:
        p = power(act).centred()
        save(p, f"icons/power-menu/{act}.png", 2)
        save(p.outlined("W"), f"icons/power-menu/{act}-focus.png", 2)
    for t in S.USB_TARGETS:
        save(usbtarget(t).centred(), f"icons/controller/usbtarget-{t}.png")
    for shape in S.CURSOR_SHAPES:
        save(pointer(shape), f"cursors/{shape}.png", 2)
    for part, css in CSS.items():
        p = os.path.join(out, "css", f"{part}.css")
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            f.write(css)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "src/theme/extra/retro")
