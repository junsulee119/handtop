"""The Signal theme: a minimal design object. Warm white and black on a strict grid, one
signal-red accent (one red element per drawing at most), geometric icons built from squares,
circles and straight lines, bold Space Grotesk text, Space Mono in the terminal, an abstract
poster as the wallpaper (rings and one red disc, no text). Writes a complete theme folder except fonts/ (kept as it is).

Drawings are new for Signal; only the drawing helpers come from gen_glass.py (V / VSharp:
anti-aliased shapes, square line ends). Images External Controller enlarges with hard pixel
scaling (Bluetooth / wired input modes, battery, USB cable pictures) are drawn pixel-exact.
Every drawing is centred in its image.

Usage: python3 tools/themes/gen_signal.py [theme folder]      (src/theme/extra/signal)
Needs Pillow."""
import json
import math
import os
import sys

from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gen_glass import V, VSharp, centred, centred_in  # noqa: E402  (drawing helpers only)

INK = (17, 17, 17)
RED = (232, 50, 29)
PAPER = (242, 242, 239)
WHITE = (255, 255, 255)
GREY = (150, 150, 146)
LINE = (214, 214, 209)
HEX = lambda c, a=None: "#%02x%02x%02x" % c + ("%02x" % a if a is not None else "")  # noqa: E731

# ---- pixel-exact helper -------------------------------------------------------------------------------
COL = {"K": INK, "R": RED, "W": WHITE, "G": GREY}


def grid(rows, w=None, h=None):
    gw, gh = len(rows[0]), len(rows)
    assert all(len(r) == gw for r in rows), rows
    out = Image.new("RGBA", (w or gw, h or gh), (0, 0, 0, 0))
    ox, oy = ((w or gw) - gw) // 2, ((h or gh) - gh) // 2
    for y, r in enumerate(rows):
        for x, ch in enumerate(r):
            if ch in COL:
                out.putpixel((ox + x, oy + y), COL[ch] + (255,))
    return out


# ---- taskbar --------------------------------------------------------------------------------------------
def panel_apps():
    """Four squares, the first one red (the Apps button is a black block: drawn in white)."""
    return grid(["................", "................", "..RRRRR..WWWWW..", "..RRRRR..WWWWW..",
                 "..RRRRR..WWWWW..", "..RRRRR..WWWWW..", "..RRRRR..WWWWW..", "................",
                 "................", "..WWWWW..WWWWW..", "..WWWWW..WWWWW..", "..WWWWW..WWWWW..",
                 "..WWWWW..WWWWW..", "..WWWWW..WWWWW..", "................", "................"])


def panel_power():
    v = VSharp(24, 24)
    v.arc(12, 12.5, 7, -55, 235, 2.4, INK)
    v.line([(12, 3.5), (12, 11)], 2.4, RED)
    return centred(v.final())


HANDHELD = [
    "KKKKKKKKKKKKKKKKKKK",
    "KKKKKKKKKKKKKKKKKKK",
    "KK...............KK",
    "KK.....KKKKK.....KK",
    "KK..K..KKKKK.....KK",
    "KK.KKK.KKKKK..RR.KK",
    "KK..K..KKKKK..RR.KK",
    "KK.....KKKKK.....KK",
    "KK...............KK",
    "KKKKKKKKKKKKKKKKKKK",
    "KKKKKKKKKKKKKKKKKKK",
]
MOUSE = ["KKKKKKKKK", "KKKKKKKKK", "KK..R..KK", "KK..R..KK", "KK.....KK", "KKKKKKKKK"] + \
        ["KK.....KK"] * 7 + ["KKKKKKKKK", "KKKKKKKKK"]
BT = ["..K..", "..KK.", "K.K.K", ".KKK.", "..K..", ".KKK.", "K.K.K", "..KK.", "..K.."]
PLUG = [".K.K.", "KKKKK", "KKKKK", "KKKKK", "..K..", "..K..", "..K.."]


def inputmode(mode):
    if mode == "desktop":
        return grid(MOUSE, 23, 23)
    if mode == "gamepad":
        return grid(HANDHELD, 23, 23)
    badge = [r.replace("K", "R") for r in BT] if mode == "bt" else PLUG
    pad = [r.center(19, ".") for r in badge]
    return grid(pad + ["." * 19] * (2 if mode == "bt" else 0) + HANDHELD, 23, 23)


def battery(n, charging=False, low=False, saver=False):
    """Five square segments in a black frame: red when low, hollow in Battery saver, a red
    bolt while charging."""
    rows = ["KKKKKKKKKKKKKKKKKK..", "K................K..", "K................KKK",
            "K................KKK", "K................KKK", "K................KKK",
            "K................KKK", "K................KKK", "K................KKK",
            "K................K..", "KKKKKKKKKKKKKKKKKK.."]
    rows = [list(r) for r in rows]
    seg = "R" if low else "K"
    for i in range(n):
        x0 = 2 + i * 3
        for y in range(2, 9):
            for x in (x0, x0 + 1):
                hollow = saver and 2 < y < 8 and x == x0 + 1
                rows[y][x] = "." if hollow else seg
    if charging:
        bolt = ["...RR", "..RR.", ".RRRR", "..RR.", ".RR..", "RR..."]
        for j, r in enumerate(bolt):
            for i, ch in enumerate(r):
                if ch == "R":
                    rows[2 + j][7 + i] = "R"
    return grid(["".join(r) for r in rows])


# ---- tray (taskbar only) ----------------------------------------------------------------------------
def wifi(name):
    v = V(23, 23)
    secure = name.endswith("-secure")
    base = name[:-7] if secure else name
    lit = 0
    if base.startswith("nm-signal-"):
        lit = {"00": 0, "25": 1, "50": 2, "75": 3, "100": 3}[base.split("-")[2]]
    elif base.startswith("nm-stage"):
        lit = int(base[-2:]) % 4
    if base.startswith("nm-device-wired"):
        v.rrect(4, 4, 19, 13, 0, outline=INK, width=2)
        v.rrect(9.5, 13, 13.5, 16, 0, fill=INK)
        v.rrect(4, 17, 19, 19, 0, fill=INK)
    else:
        for i in range(3):                                         # three rising bars
            h = 5 + 4 * i
            x0 = 5 + 5 * i
            on = i < lit and base != "nm-no-connection"
            v.rrect(x0, 19 - h, x0 + 3, 19, 0, fill=INK if on else LINE)
        if base == "nm-no-connection":
            v.line([(16, 3), (20, 7)], 2, RED, caps=False)
            v.line([(20, 3), (16, 7)], 2, RED, caps=False)
    img = centred(v.final()) if not secure else v.final()
    if secure:
        lk = V(23, 23)
        lk.rrect(16, 2, 21, 7, 0, fill=RED)
        img.alpha_composite(lk.final())
    return img


def bluetooth(state):
    v = VSharp(23, 23)
    c = GREY if state == "blueman-disabled" else INK
    h = 15
    cx, cy = 11.5, 11.5
    q = h / 4
    v.line([(cx - q, cy - q), (cx + q, cy + q), (cx, cy + h / 2), (cx, cy - h / 2), (cx + q, cy - q),
            (cx - q, cy + q)], 2, c)
    img = centred(v.final())
    if state == "blueman-active":
        d = V(23, 23)
        d.rrect(17, 17, 21, 21, 0, fill=RED)
        img.alpha_composite(d.final())
    return img


def usbtarget(t):
    if t == "pc":
        rows = ["KKKKKKKKKKKKKKKKKKK"] * 2 + ["KK...............KK"] * 8 + \
               ["KKKKKKKKKKKKKKKKKKK"] * 2 + ["........KKK........", "......KKKKKKK......",
                                             "...................", "KKKKKKKKKKKKKKKKKKK",
                                             "K.K.K.K.K.K.K.K.K.K", "KKKKKKKKKKKKKKKKKKK"]
        rows[2] = "KK.............RRKK"                                    # a red power light
    else:
        rows = ["KKKKKKKKKKKKKKKKKKKKK"] * 2 + ["KK.................KK"] * 7 + \
               ["KKKKKKKKKKKKKKKKKKKKK"] * 2 + [".....KK.......KK.....", ".....................",
                                                 "....KKKKKKKKKKKKK....", "....K...........K....",
                                                 "....K.KKK...RR..K....", "....K..K....RR..K....",
                                                 "....K...........K....", "....KKKKKKKKKKKKK...."]
    return grid(rows, 23, 23)


# ---- app icons: geometric, black, one red element ------------------------------------------------------
def app_glyph(name, w=3.2):
    v = VSharp(56, 56)
    if name == "theme":                                            # three swatches
        v.rrect(12, 12, 27, 27, 0, fill=INK)
        v.rrect(29, 12, 44, 27, 0, outline=INK, width=w)
        v.rrect(12, 29, 27, 44, 0, outline=INK, width=w)
        v.rrect(29, 29, 44, 44, 0, fill=RED)
    elif name == "external-controller":                            # a pad: D-pad and one red button
        v.rrect(6, 17, 50, 39, 0, outline=INK, width=w)
        v.line([(12, 28), (24, 28)], w, INK)                        # D-pad
        v.line([(18, 22), (18, 34)], w, INK)
        v.ellipse(32, 22, 44, 34, fill=RED)                         # button
    elif name == "display":
        v.rrect(9, 11, 47, 37, 0, outline=INK, width=w)
        v.line([(28, 37), (28, 44)], w, INK)
        v.line([(18, 45.5), (38, 45.5)], w, RED)
    elif name == "enable-ssh":                                     # a shell, linked to a far end
        v.rrect(6, 16, 30, 40, 0, fill=INK)
        v.line([(12, 22), (19, 28), (12, 34)], w, WHITE)
        v.line([(30, 28), (40, 28)], w, INK)
        v.rrect(40, 22, 52, 34, 0, fill=RED)
    elif name == "recenter-sticks":
        v.ellipse(14, 14, 42, 42, outline=INK, width=w)
        v.ellipse(23.5, 23.5, 32.5, 32.5, fill=RED)
        for a, b in (((28, 6), (28, 14)), ((28, 42), (28, 50)), ((6, 28), (14, 28)), ((42, 28), (50, 28))):
            v.line([a, b], w, INK)
    elif name == "foot":
        v.rrect(9, 11, 47, 45, 0, fill=INK)
        v.line([(16, 21), (23, 28), (16, 35)], w, WHITE)
        v.rrect(27, 33, 38, 36.5, 0, fill=RED)
    elif name == "thunar":
        v.rrect(9, 17, 47, 44, 0, outline=INK, width=w)
        v.rrect(9, 11, 25, 17, 0, fill=RED)
    elif name == "mousepad":
        v.rrect(13, 9, 43, 47, 0, outline=INK, width=w)
        for y in (19, 26, 33):
            v.line([(19, y), (37, y)], w * 0.8, INK)
        v.line([(19, 40), (30, 40)], w * 0.8, RED)
    elif name == "chromium":                                       # a browser window with its address bar
        v.rrect(8, 10, 48, 46, 0, outline=INK, width=w)
        v.rrect(8, 10, 48, 20, 0, fill=INK)
        v.rrect(12, 13.5, 16, 16.5, 0, fill=RED)
        v.line([(14, 28), (42, 28)], w * 0.8, INK)
        v.line([(14, 35), (34, 35)], w * 0.8, INK)
    elif name == "htop":
        for i, h in enumerate((14, 24, 18, 30)):
            v.rrect(10 + i * 10, 46 - h, 16 + i * 10, 46, 0, fill=RED if i == 3 else INK)
    elif name == "micro":
        v.line([(21, 16), (10, 28), (21, 40)], w, INK)
        v.line([(35, 16), (46, 28), (35, 40)], w, INK)
        v.line([(32, 12), (24, 44)], w, RED)
    elif name == "qpdfview":
        v.line([(13, 8), (33, 8), (43, 18), (43, 48), (13, 48), (13, 8)], w, INK)
        v.rrect(13, 28, 43, 38, 0, fill=RED)
    elif name == "xarchiver":
        v.rrect(9, 13, 47, 22, 0, outline=INK, width=w)
        v.line([(12, 22), (12, 45), (44, 45), (44, 22)], w, INK)
        v.rrect(23, 28, 33, 32, 0, fill=RED)
    elif name == "blueman":
        h, cx, cy = 34, 26, 28
        q = h / 4
        v.line([(cx - q, cy - q), (cx + q, cy + q), (cx, cy + h / 2), (cx, cy - h / 2), (cx + q, cy - q),
                (cx - q, cy + q)], w, INK)
        v.ellipse(38, 36, 46, 44, fill=RED)
    return v.final()


def app(name):
    return centred_in(app_glyph(name), (0, 0, 56, 56))


def app_small(name, size):
    """22 / 20 px: heavier lines, cropped to the drawing, centred."""
    g = app_glyph(name, w=4.4)
    b = g.split()[3].point(lambda v: 255 if v > 24 else 0).getbbox()
    g = g.crop(b)
    k = (size - 4) / max(g.width, g.height)
    g = g.resize((max(1, round(g.width * k)), max(1, round(g.height * k))), Image.LANCZOS)
    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    out.alpha_composite(g, ((size - g.width) // 2, (size - g.height) // 2))
    return out


# ---- power menu (72 px): black with one red element; highlighted (red button): all white ------------
def power(action, focus):
    v = VSharp(72, 72)
    k = WHITE if focus else INK
    r = WHITE if focus else RED
    w = 4
    if action == "sleep":                                          # a solid crescent and a red star point
        S = 72 * 8
        m = Image.new("L", (S, S), 0)
        dm = ImageDraw.Draw(m)
        dm.ellipse((14 * 8, 16 * 8, 54 * 8, 56 * 8), fill=255)
        dm.ellipse((26 * 8, 8 * 8, 62 * 8, 44 * 8), fill=0)
        layer = Image.new("RGBA", (S, S), k + (255,))
        layer.putalpha(m)
        v.im.alpha_composite(layer)
        v.rrect(52, 12, 58, 18, 0, fill=r)
    elif action == "reboot":                                       # a ring ending in a clean arrowhead
        # The ring runs clockwise from the right (-20 degrees) round to the top (270), where it
        # ends square; the head starts exactly there: its base lies across the stroke (vertical,
        # centred on the stroke's middle line) and its tip points on clockwise, i.e. straight right.
        cx, cy, rr, e0 = 36, 38, 19, 270
        v.arc(cx, cy, rr, -20, e0, w, k)
        ex, ey = cx, cy - rr                                       # top of the middle line
        half, length = 8, 13
        v.poly([(ex, ey - half), (ex, ey + half), (ex + length, ey)], r)
    elif action == "logout":
        v.line([(34, 14), (16, 14), (16, 58), (34, 58)], w, k)
        v.line([(28, 36), (54, 36)], w, r)
        v.line([(46, 27), (55, 36), (46, 45)], w, r)
    elif action == "shutdown":
        v.arc(36, 38, 19, -55, 235, w, k)
        v.line([(36, 12), (36, 34)], w, r)
    elif action == "saver":
        v.rrect(12, 24, 54, 48, 0, outline=k, width=w)
        v.rrect(54, 31, 59, 41, 0, fill=k)
        v.rrect(18, 30, 30, 42, 0, fill=r)
    return centred(v.final())


# ---- pointer: 48 px (2x of 24) --------------------------------------------------------------------------
def pointer(shape):
    v = V(48, 48)
    arrow = [(4, 3), (4, 35), (13, 27), (19, 40), (25, 37.5), (19, 25), (31, 25)]
    if shape in ("arrow", "progress"):
        v.line(arrow + [arrow[0]], 4, WHITE, joint="curve")
        v.poly(arrow, INK)
        img = v.final()
        if shape == "progress":
            s = V(48, 48)
            s.ellipse(28, 28, 46, 46, fill=WHITE)
            s.arc(37, 37, 5.5, -90, 180, 3.4, RED)
            img.alpha_composite(s.final())
        return img
    if shape == "hand":                                            # a square-cut pointing hand
        pts = [(16, 4), (22, 4), (22, 17), (34, 17), (34, 36), (26, 44), (16, 44), (10, 30), (16, 26)]
        v.line(pts + [pts[0]], 4, WHITE, joint="curve")
        v.poly(pts, INK)
        v.rrect(17.5, 5.5, 20.5, 9, 0, fill=RED)
        return v.final()
    if shape == "text":
        for c, w in ((WHITE, 5.5), (INK, 2.6)):
            v.line([(13, 6), (23, 6)], w, c)
            v.line([(18, 6), (18, 34)], w, c)
            v.line([(13, 34), (23, 34)], w, c)
        return v.final()
    if shape == "busy":
        v.ellipse(4, 4, 40, 40, fill=WHITE)
        v.arc(22, 22, 12, 0, 360, 5, LINE, caps=False)
        v.arc(22, 22, 12, -90, 0, 5, RED, caps=False)
        return v.final()


HOTSPOTS = {"arrow": [4, 3], "hand": [19, 4], "text": [18, 20], "busy": [22, 22], "progress": [4, 3]}


# ---- wallpaper: an abstract poster: rings of rhythm and one red point -------------------------------------
def wallpaper(w=960, h=720, ss=3):
    """Concentric black rings spreading from beyond the lower-left corner, their weight falling
    off with distance like a rhythm, and one red disc set where it breaks the pattern. No text,
    no layout boxes: a poster, not a page."""
    W, H = w * ss, h * ss
    im = Image.new("RGB", (W, H), PAPER)
    d = ImageDraw.Draw(im)
    cx, cy = -0.12 * W, 1.18 * H                                   # centre outside the frame
    r = 0.30 * W
    i = 0
    while r < 1.9 * W:
        weight = max(2 * ss, int((26 - i * 2.1) * ss)) if i % 3 != 2 else 2 * ss
        d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=INK, width=weight)
        r += (0.055 + 0.006 * i) * W
        i += 1
    # the red disc: sits across two rings, upper right of centre
    rx, ry, rr = 0.70 * W, 0.30 * H, 0.085 * W
    d.ellipse((rx - rr, ry - rr, rx + rr, ry + rr), fill=RED)
    return im.resize((w, h), Image.LANCZOS)


# ---- theme.json and CSS -------------------------------------------------------------------------------------
I, R, P, W, G = HEX(INK), HEX(RED), HEX(PAPER), HEX(WHITE), HEX(GREY)
THEME = {
    "schema": 1, "id": "signal", "name": "Signal", "base": "light", "author": "Handtop",
    "description": "A minimal design object: black and white on a grid, one signal red, bold type.",
    "palette": {"bg": P, "surface": W, "surface_hi": "#e4e4df", "border": I, "fg": I, "fg_dim": "#6b6b67",
                "accent": R, "accent_fg": R, "on_accent": W, "warn": R, "error": R, "brightness": I,
                "success": I},
    "colors": {
        "taskbar.bg": P, "taskbar.fg": I, "taskbar.border": I, "taskbar.apps_bg": I, "taskbar.apps_fg": W,
        "taskbar.active_bg": P, "taskbar.warn": R, "taskbar.critical": R,
        "titlebar.active_bg": I, "titlebar.inactive_bg": "#e4e4df", "titlebar.active_fg": W,
        "titlebar.inactive_fg": "#6b6b67", "titlebar.active_button": W, "titlebar.inactive_button": "#6b6b67",
        "drawer.bg": P, "drawer.fg": I, "drawer.entry_bg": W, "drawer.hover_bg": I,
        "powermenu.backdrop": P + "f2", "powermenu.button_bg": W, "powermenu.button_border": I,
        "powermenu.fg": I, "powermenu.hover_bg": R, "powermenu.hover_border": R, "powermenu.focus": R,
        "notify.bg": W, "notify.fg": I, "notify.border": I,
        "osk.bg": P, "osk.key": W, "osk.border": I, "osk.fg": I, "osk.spec": "#e4e4df", "osk.spec_border": I,
        "osk.spec_fg": I, "osk.sel": I, "osk.sel_border": I, "osk.sel_fg": W, "osk.latch": R,
        "osk.latch_sel": R, "osk.latch_border": I, "osk.badge": R, "osk.hit": "#d0d0cb", "osk.hit_border": I,
        "osk.hit_fg": I,
        "terminal.bg": W, "terminal.fg": I, "terminal.cursor": R, "terminal.cursor_text": W,
        "terminal.selection_bg": I, "terminal.selection_fg": W,
        "osd.bg": W, "osd.volume_border": I, "osd.volume_level": I, "osd.brightness_border": I,
        "osd.brightness_level": R, "osd.text": I,
    },
    "wallpaper": {"color": P, "image": "images/wallpaper.png", "mode": "fill"},
    "status_screen": {"style": "solid"},
    "gtk": {"color_scheme": "default", "theme": "Adwaita", "icon_theme": "Adwaita"},
    "cursor": {"size": 24, "hotspots": HOTSPOTS},
    "fonts": {"ui": "Space Grotesk", "mono": "Space Mono", "scale": 1.0},
    "borders": 2,
}

CSS = {
    "taskbar": f"""/* Signal: a white strip under a black rule; Apps is a black block; the active window is
   underlined in red; bold numbers for the clock and battery. */
#custom-apps {{ margin: 0; padding: 0 12px 0 31px; font-weight: bold; }}
#custom-apps:hover {{ background-color: {R}; }}
#taskbar button {{ margin: 0 1px; padding: 0 8px; border-bottom: 3px solid transparent; }}
#taskbar button.active {{ border-bottom-color: {R}; }}
#taskbar button:hover {{ background-color: #e4e4df; }}
#clock {{ font-weight: bold; font-size: 14px; }}
#battery {{ font-weight: bold; }}
""",
    "drawer": f"""/* Signal: a plain grid; the chosen app turns into a black block. The hover itself comes
   from css/apps.css (GTK applies it here too, and it wins). */
entry {{ border-radius: 0; border: none; border-bottom: 2px solid {I}; background-color: {W}; }}
button {{ border-radius: 0; }}
""",
    "powermenu": f"""/* Signal: square tiles with a black frame; the chosen one fills red. */
button {{ border-radius: 0; font-weight: bold; }}
button:hover {{ color: {W}; }}
""",
    "apps": f"""/* Signal: square corners and the red accent in GTK 3 apps (Adwaita light). GTK also reads this
   in the taskbar, app drawer and power menu. */
* {{ border-radius: 0; -gtk-outline-radius: 0; }}
button {{ background-image: none; background-color: {W}; border: 2px solid {I}; box-shadow: none; text-shadow: none; }}
button:hover {{ background-color: {I}; color: {W}; }}
button:hover label, button:hover image {{ color: {W}; }}
button:active, button:checked {{ background-color: {R}; border-color: {R}; color: {W}; }}
button.flat {{ border-color: transparent; background-color: transparent; }}
button.flat:hover {{ background-color: {I}; }}
/* Adwaita paints these two with white text: the main action is a red block, delete a red frame. */
button.suggested-action {{ background-image: none; box-shadow: none; background-color: {R}; border-color: {R}; color: {W}; }}
button.destructive-action {{ background-image: none; box-shadow: none; background-color: {W}; border-color: {R}; color: {R}; }}
button.suggested-action:hover, button.destructive-action:hover {{ background-color: {I}; border-color: {I}; color: {W}; }}
entry {{ background-image: none; border: 2px solid {I}; box-shadow: none; }}
treeview.view:selected, .view:selected, iconview:selected, row:selected, placessidebar row:selected,
textview text selection, entry selection, menuitem:hover, modelbutton:hover {{
  background-color: {R}; color: {W};
}}
row:selected label, menuitem:hover label {{ color: {W}; }}
check:checked, radio:checked, switch:checked {{ background-image: none; background-color: {R}; border-color: {R}; }}
progressbar progress, scale highlight {{ background-image: none; background-color: {R}; border-color: {R}; }}
headerbar {{ background-image: none; background-color: {I}; color: {W}; box-shadow: none; }}
headerbar label {{ color: {W}; }}
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
    save(panel_apps(), "icons/taskbar/apps.png")
    save(panel_power(), "icons/taskbar/power.png")
    for m in S.INPUT_MODES:
        save(inputmode(m), f"icons/taskbar/inputmode-{m}.png")
    for ch in (False, True):
        for low in (False, True):
            for n in range(6):
                for sv in (False, True):
                    name = f"battery{'-charging' if ch else ''}{'-low' if low else ''}-{n}{'-saver' if sv else ''}"
                    save(battery(n, ch, low, sv), f"icons/taskbar/{name}.png")
    for w_ in S.WIFI:
        save(wifi(w_), f"icons/tray/{w_}.png")
    for b in S.BLUETOOTH:
        save(bluetooth(b), f"icons/tray/{b}.png")
    for name in S.HANDTOP_APPS + S.DEFAULT_APPS:
        save(app(name), f"icons/apps/{name}.png")
        for size in (22, 20):
            save(app_small(name, size), f"icons/apps/{name}@{size}.png")
    for act in S.POWER_ACTIONS:
        save(power(act, False), f"icons/power-menu/{act}.png")
        save(power(act, True), f"icons/power-menu/{act}-focus.png")
    for t in S.USB_TARGETS:
        save(usbtarget(t), f"icons/controller/usbtarget-{t}.png")
    for shape in S.CURSOR_SHAPES:
        save(pointer(shape), f"cursors/{shape}.png")
    save(wallpaper(), "images/wallpaper.png")
    for part, css in CSS.items():
        p = os.path.join(out, "css", f"{part}.css")
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            f.write(css)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "src/theme/extra/signal")
