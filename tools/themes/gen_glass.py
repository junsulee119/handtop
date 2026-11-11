"""The Glass theme: light, modern. Milky translucent panels over a blue-to-violet gradient,
rounded corners, monotone line icons in one ink colour (anti-aliased, drawn as shapes, not pixel
art; the glass tiles and buttons are their frames), a smooth pointer, Inter for text. labwc cannot blur what is behind a
panel, so the glass is tinted translucency; app windows stay opaque (Adwaita light).

Original drawings, no logos. Writes a complete theme folder except fonts/ (kept as it is).

Every drawing is centred in its image (GUIDE.md, "Drawing tips"): shapes are laid out around
the image's middle, 2 px strokes sit on whole-pixel coordinates so they stay crisp.

Usage: python3 tools/themes/gen_glass.py [theme folder]     (src/theme/extra/glass)
Needs Pillow."""
import json
import math
import os
import sys

from PIL import Image, ImageChops, ImageDraw, ImageFilter

SS = 8          # supersampling

INK = (28, 34, 51)              # line icons on the light glass
DIM = (28, 34, 51, 70)          # unlit parts (Wi-Fi arcs, empty battery)
ACCENT = (91, 91, 214)          # indigo-violet
RED = (217, 58, 58)
GREEN = (47, 158, 91)
AMBER = (224, 160, 32)
WHITE = (255, 255, 255)


def rgba(c, a=255):
    return c if len(c) == 4 else c + (a,)


class V:
    """A canvas drawn at SS times its size and scaled down (anti-aliased). Coordinates are in
    final pixels (floats allowed)."""
    def __init__(self, w, h):
        self.w, self.h = w, h
        self.im = Image.new("RGBA", (w * SS, h * SS), (0, 0, 0, 0))
        self.d = ImageDraw.Draw(self.im)

    def _p(self, pts):
        return [(x * SS, y * SS) for x, y in pts]

    def line(self, pts, width, c, joint="curve", caps=True):
        self.d.line(self._p(pts), fill=rgba(c), width=round(width * SS), joint=joint)
        if caps:
            r = width * SS / 2
            for x, y in (pts[0], pts[-1]):
                self.d.ellipse((x * SS - r, y * SS - r, x * SS + r, y * SS + r), fill=rgba(c))

    def arc(self, cx, cy, r, a0, a1, width, c, caps=True):
        """Arc of radius r (stroke centre) from angle a0 to a1 degrees (0 = right, clockwise)."""
        R = r + width / 2
        self.d.arc(((cx - R) * SS, (cy - R) * SS, (cx + R) * SS, (cy + R) * SS), a0, a1,
                   fill=rgba(c), width=round(width * SS))
        if caps:
            for a in (a0, a1):
                x, y = cx + r * math.cos(math.radians(a)), cy + r * math.sin(math.radians(a))
                q = width * SS / 2
                self.d.ellipse((x * SS - q, y * SS - q, x * SS + q, y * SS + q), fill=rgba(c))

    def rrect(self, x0, y0, x1, y1, r, fill=None, outline=None, width=0):
        self.d.rounded_rectangle((x0 * SS, y0 * SS, x1 * SS, y1 * SS), radius=r * SS,
                                 fill=rgba(fill) if fill else None,
                                 outline=rgba(outline) if outline else None, width=round(width * SS))

    def ellipse(self, x0, y0, x1, y1, fill=None, outline=None, width=0):
        self.d.ellipse((x0 * SS, y0 * SS, x1 * SS, y1 * SS), fill=rgba(fill) if fill else None,
                       outline=rgba(outline) if outline else None, width=round(width * SS))

    def poly(self, pts, fill):
        self.d.polygon(self._p(pts), fill=rgba(fill))

    def paste(self, other, x=0, y=0):
        self.im.alpha_composite(other.im, (round(x * SS), round(y * SS)))

    def final(self):
        return self.im.resize((self.w, self.h), Image.LANCZOS)


class VSharp(V):
    """V with square line ends and sharp (mitred) corners: the app and power-menu glyphs
    (Jason 2026-11-11: edges instead of rounded tips). Each segment is painted as a quad and each
    corner filled with its mitre (bevelled when the angle is very sharp, so a Bluetooth rune gets
    no spikes); arcs end square too."""
    def line(self, pts, width, c, joint=None, caps=False):
        h = width / 2
        closed = len(pts) > 2 and pts[0] == pts[-1]
        P = pts[:-1] if closed else list(pts)
        n = len(P)
        if n < 2:
            return

        def normal(a, b):
            dx, dy = b[0] - a[0], b[1] - a[1]
            L = math.hypot(dx, dy) or 1
            return -dy / L * h, dx / L * h
        segs = [(i, (i + 1) % n) for i in range(n if closed else n - 1)]
        for i, j in segs:
            nx, ny = normal(P[i], P[j])
            a, b = P[i], P[j]
            self.poly([(a[0] + nx, a[1] + ny), (b[0] + nx, b[1] + ny), (b[0] - nx, b[1] - ny),
                       (a[0] - nx, a[1] - ny)], c)
        corners = range(n) if closed else range(1, n - 1)
        for i in corners:
            p0, p, p1 = P[i - 1], P[i], P[(i + 1) % n]
            n0, n1 = normal(p0, p), normal(p, p1)
            for sgn in (1, -1):
                e0 = (p[0] + sgn * n0[0], p[1] + sgn * n0[1])
                e1 = (p[0] + sgn * n1[0], p[1] + sgn * n1[1])
                mx, my = n0[0] + n1[0], n0[1] + n1[1]
                L = math.hypot(mx, my)
                pts_ = [p, e0]
                if L > 1e-6:
                    cos_half = L / (2 * h)
                    k = 1 / max(cos_half, 1e-6)
                    if k <= 2.0:                                     # mitre
                        pts_.append((p[0] + sgn * mx / L * h * k, p[1] + sgn * my / L * h * k))
                pts_.append(e1)
                self.poly(pts_, c)

    def arc(self, cx, cy, r, a0, a1, width, c, caps=False):
        V.arc(self, cx, cy, r, a0, a1, width, c, caps=False)


def stroke_shape(v, draw, w, c):
    """Outline of a filled shape: draw(ImageDraw, k) paints the shape (k = supersampling factor)
    into a mask; the outline is the mask minus the mask shrunk by w. Gives even strokes on
    combined shapes (gamepad, leaf, crescent) with no seams."""
    S = (v.w * SS, v.h * SS)
    m = Image.new("L", S, 0)
    draw(ImageDraw.Draw(m), SS)
    inner = m.filter(ImageFilter.MinFilter(2 * round(w * SS) + 1))
    layer = Image.new("RGBA", S, rgba(c))
    layer.putalpha(ImageChops.subtract(m, inner))
    v.im.alpha_composite(layer)


def save(img, out, rel):
    p = os.path.join(out, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    img.save(p)


def centred(img):
    """The drawing moved so its bounding box (alpha > 24) sits in the middle (rounded down)."""
    a = img.split()[3].point(lambda v: 255 if v > 24 else 0)
    b = a.getbbox()
    if not b:
        return img
    dx = (img.width - (b[2] - b[0])) // 2 - b[0]
    dy = (img.height - (b[3] - b[1])) // 2 - b[1]
    out = Image.new("RGBA", img.size, (0, 0, 0, 0))
    out.paste(img, (dx, dy))
    return out


# ---- glyphs (drawn into a V at a given box) ---------------------------------------------------------
def g_power(v, cx, cy, r, w, c):
    v.arc(cx, cy, r, -60, 240, w, c)
    v.line([(cx, cy - r - w * 0.4), (cx, cy - r * 0.15)], w, c)


def g_handheld(v, cx, cy, s, w, c, screen=None):
    """A handheld outline, s = half width."""
    h = s * 0.62
    v.rrect(cx - s, cy - h, cx + s, cy + h, h * 0.45, outline=c, width=w)
    sx = s * 0.36
    v.rrect(cx - sx, cy - h * 0.55, cx + sx, cy + h * 0.35, 1.2, fill=screen, outline=c, width=w * 0.8)
    d = s * 0.66
    v.line([(cx - d - s * 0.13, cy), (cx - d + s * 0.13, cy)], w * 0.8, c)
    v.line([(cx - d, cy - s * 0.13), (cx - d, cy + s * 0.13)], w * 0.8, c)
    v.ellipse(cx + d - s * 0.1, cy - s * 0.1, cx + d + s * 0.1, cy + s * 0.1, fill=c)


def g_bt(v, cx, cy, h, w, c):
    t, b = cy - h / 2, cy + h / 2
    q = h / 4
    v.line([(cx - q, cy - q), (cx + q, cy + q), (cx, b), (cx, t), (cx + q, cy - q), (cx - q, cy + q)],
           w, c, joint="curve")


def g_mouse(v, cx, cy, s, w, c):
    v.rrect(cx - s * 0.62, cy - s, cx + s * 0.62, cy + s, s * 0.62, outline=c, width=w)
    v.line([(cx, cy - s * 0.62), (cx, cy - s * 0.2)], w, c)


def g_monitor(v, cx, cy, s, w, c, fill=None):
    h = s * 0.7
    v.rrect(cx - s, cy - h, cx + s, cy + h * 0.6, 2, fill=fill, outline=c, width=w)
    v.line([(cx, cy + h * 0.6), (cx, cy + h * 0.95)], w, c)
    v.line([(cx - s * 0.45, cy + h * 1.0), (cx + s * 0.45, cy + h * 1.0)], w, c)


def g_lock(v, cx, cy, s, c):
    v.arc(cx, cy - s * 0.35, s * 0.42, 180, 360, s * 0.28, c, caps=False)
    v.rrect(cx - s * 0.62, cy - s * 0.35, cx + s * 0.62, cy + s * 0.55, s * 0.18, fill=c)


# ---- taskbar ----------------------------------------------------------------------------------------
def panel_apps():
    v = V(16, 16)
    for x in (4, 10):
        for y in (4, 10):
            v.rrect(x - 2.5, y - 2.5, x + 2.5, y + 2.5, 1.4, fill=INK)
    return v.final()


def panel_power():
    v = V(24, 24)
    g_power(v, 12, 12.5, 7, 2, INK)
    return centred(v.final())


def handheld23(v, y):
    """The handheld at taskbar size: body outline, a filled screen, D-pad and a button."""
    v.rrect(1.8, y, 21.2, y + 10.5, 3.2, outline=INK, width=1.6)
    v.rrect(8, y + 2.6, 15, y + 7.9, 1, fill=INK)
    v.line([(4.4, y + 5.25), (7.0, y + 5.25)], 1.3, INK)
    v.line([(5.7, y + 3.95), (5.7, y + 6.55)], 1.3, INK)
    v.ellipse(16.6, y + 4.2, 18.8, y + 6.4, fill=INK)


def inputmode(mode):
    v = V(23, 23)
    if mode == "desktop":
        g_mouse(v, 11.5, 11.5, 7, 1.7, INK)
    else:
        handheld23(v, 8 if mode != "gamepad" else 6.25)
        if mode == "bt":
            g_bt(v, 11.5, 3.3, 5.6, 1.3, INK)
        elif mode == "wired":
            v.line([(11.5, 0.8), (11.5, 6.6)], 1.6, INK)
            v.rrect(9.5, 0.6, 13.5, 3.4, 0.8, fill=INK)
    return centred(v.final())


def battery(n, charging=False, low=False, saver=False):
    v = V(20, 11)
    edge = GREEN if saver else INK
    v.rrect(0.75, 0.75, 17.25, 10.25, 2.6, outline=edge, width=1.5)
    v.rrect(17.6, 3.6, 19.4, 7.4, 0.8, fill=edge)
    fill = RED if low else (GREEN if saver else INK)
    if n:
        v.rrect(2.6, 2.6, 2.6 + 12.8 * n / 5, 8.4, 1.4, fill=fill)
    if charging:
        bolt = [(10.4, 1.2), (6.6, 6.0), (9.3, 6.0), (8.4, 9.8), (12.4, 4.8), (9.7, 4.8)]
        for dx, dy in ((-0.9, 0), (0.9, 0), (0, -0.9), (0, 0.9)):     # white rim for contrast
            v.poly([(x + dx, y + dy) for x, y in bolt], WHITE)
        v.poly(bolt, AMBER)
    return v.final()


# ---- tray -------------------------------------------------------------------------------------------
def wifi_fan(v, lit, dim_all=False):
    cx, cy = 11.5, 16.5
    for i, r in enumerate((5, 9.5)):
        on = (i + 1) < lit and not dim_all
        v.arc(cx, cy, r, 225, 315, 2, INK if on else DIM)
    v.ellipse(cx - 1.6, cy - 1.6, cx + 1.6, cy + 1.6, fill=INK if (lit >= 1 and not dim_all) else DIM)


def wifi(name):
    v = V(23, 23)
    secure = name.endswith("-secure")
    base = name[:-7] if secure else name
    if base.startswith("nm-signal-"):
        wifi_fan(v, {"00": 0, "25": 1, "50": 2, "75": 3, "100": 3}[base.split("-")[2]])
    elif base == "nm-no-connection":
        wifi_fan(v, 0, dim_all=True)
        v.line([(16.5, 15.5), (20.5, 19.5)], 1.6, RED)
        v.line([(20.5, 15.5), (16.5, 19.5)], 1.6, RED)
    elif base.startswith("nm-stage"):
        frame = int(base[-2:])
        wifi_fan(v, frame % 4)
    elif base.startswith("nm-device-wired"):
        # wired network: one box above two, joined by lines
        v.rrect(8.5, 3.5, 14.5, 8.5, 1.4, outline=INK, width=1.6)
        v.rrect(2.5, 14.5, 8.5, 19.5, 1.4, outline=INK, width=1.6)
        v.rrect(14.5, 14.5, 20.5, 19.5, 1.4, outline=INK, width=1.6)
        v.line([(11.5, 8.5), (11.5, 11.5)], 1.6, INK, caps=False)
        v.line([(5.5, 14.5), (5.5, 11.5), (17.5, 11.5), (17.5, 14.5)], 1.6, INK, joint=None, caps=False)
    img = v.final()
    if secure:
        lk = V(23, 23)
        g_lock(lk, 18.5, 5.5, 4.2, INK)
        img.alpha_composite(lk.final())
    return img


def bluetooth(state):
    v = V(23, 23)
    c = DIM if state == "blueman-disabled" else INK
    g_bt(v, 11.5, 11.5, 15, 1.8, c)
    img = centred(v.final())
    if state == "blueman-active":
        dot = V(23, 23)
        dot.ellipse(15.5, 15.5, 21.5, 21.5, fill=GREEN)
        img.alpha_composite(dot.final())
    return img


def usbtarget(t):
    v = V(23, 23)
    if t == "pc":
        g_monitor(v, 11.5, 9, 9, 1.6, INK)
        v.rrect(3.5, 17.5, 19.5, 21.5, 1.5, outline=INK, width=1.4)
    else:
        v.rrect(2.5, 1.5, 20.5, 13.5, 2, outline=INK, width=1.6)
        v.line([(9, 15.5), (14, 15.5)], 1.6, INK)
        v.rrect(5.5, 17, 17.5, 22, 2.5, outline=INK, width=1.4)
    return centred(v.final())


# ---- app icons: the line glyph alone (the drawer's glass tile frames it) ---------------------------
def app_glyph(name, c=INK, w=3):
    v = VSharp(56, 56)
    t = w * 0.8             # thinner detail lines
    cx, cy = 28, 28
    if name == "theme":
        # appearance: a circle, its right half filled
        v.ellipse(14.5, 14.5, 41.5, 41.5, outline=c, width=w)
        v.d.pieslice((14.5 * SS, 14.5 * SS, 41.5 * SS, 41.5 * SS), -90, 90, fill=rgba(c))
    elif name == "external-controller":
        # a gamepad: body and two grips as one outline, D-pad and two buttons
        def pad(d, k):
            d.rounded_rectangle((11 * k, 18 * k, 45 * k, 34 * k), radius=8 * k, fill=255)
            d.ellipse((10 * k, 24 * k, 23 * k, 42 * k), fill=255)
            d.ellipse((33 * k, 24 * k, 46 * k, 42 * k), fill=255)
        stroke_shape(v, pad, w, c)
        v.line([(16.5, 27), (23.5, 27)], t, c)
        v.line([(20, 23.5), (20, 30.5)], t, c)
        v.ellipse(33, 22.5, 37, 26.5, fill=c)
        v.ellipse(37, 26.5, 41, 30.5, fill=c)
    elif name == "display":
        g_monitor(v, cx, 26, 14, w, c)
    elif name == "enable-ssh":
        # a key: round bow, shaft, two teeth
        v.ellipse(8, 19, 26, 37, outline=c, width=w)
        v.line([(26, 28), (48, 28)], w, c)
        v.line([(41.5, 28), (41.5, 35)], w, c)
        v.line([(46.5, 28), (46.5, 34)], w, c)
    elif name == "recenter-sticks":
        v.ellipse(16, 16, 40, 40, outline=c, width=w)
        v.ellipse(25, 25, 31, 31, fill=c)
        for a, b in (((28, 11), (28, 18)), ((28, 38), (28, 45)), ((11, 28), (18, 28)), ((38, 28), (45, 28))):
            v.line([a, b], w, c)
    elif name == "foot":
        v.line([(17, 21), (24, 28), (17, 35)], w, c)
        v.line([(28, 36), (39, 36)], w, c)
    elif name == "thunar":
        v.line([(14, 20), (14, 38), (42, 38), (42, 23), (27, 23), (24, 19), (15, 19)], w, c, joint="curve")
    elif name == "mousepad":
        v.rrect(16, 13, 38, 43, 0, outline=c, width=w)
        for y in (21, 27, 33):
            v.line([(21, y), (33, y)], t, c)
    elif name == "chromium":
        # a globe: outline, one meridian, the equator and two parallels
        r, gx, gy = 13.5, 28, 28
        v.ellipse(gx - r, gy - r, gx + r, gy + r, outline=c, width=w)
        v.ellipse(gx - 6, gy - r, gx + 6, gy + r, outline=c, width=t)
        v.line([(gx - r, gy), (gx + r, gy)], t, c)
        for dy in (-6.5, 6.5):
            hw = math.sqrt(r * r - dy * dy) - 0.5
            v.line([(gx - hw, gy + dy), (gx + hw, gy + dy)], t, c)
    elif name == "htop":
        v.line([(13, 30), (20, 30), (24, 20), (30, 38), (35, 26), (38, 30), (43, 30)], w, c)
    elif name == "micro":
        v.line([(23, 18), (16, 28), (23, 38)], w, c)
        v.line([(33, 18), (40, 28), (33, 38)], w, c)
        v.line([(30, 16), (26, 40)], t, c)
    elif name == "qpdfview":
        v.line([(17, 13), (31, 13), (39, 21), (39, 43), (17, 43), (17, 13)], w, c, joint="curve")
        v.line([(31, 13), (31, 21), (39, 21)], t, c)
        for y in (29, 35):
            v.line([(22, y), (34, y)], t, c)
    elif name == "xarchiver":
        v.rrect(14, 15, 42, 23, 0, outline=c, width=w)
        v.line([(16, 23), (16, 40), (40, 40), (40, 23)], w, c, joint="curve")
        v.line([(24, 29), (32, 29)], w, c)
    elif name == "blueman":
        g_bt(v, cx, cy, 26, w, c)
    return v.final()


def app(name):
    """Just the line glyph, in ink: the drawer's glass tile is the frame (Jason 2026-11-11)."""
    return centred_in(app_glyph(name), (0, 0, 56, 56))


def app_small(name, size):
    """The 22 / 20 px copies (taskbar window buttons, title bars): drawn with heavier lines and
    cropped to the drawing, so they stay readable instead of a thin scaled-down 56 px icon."""
    g = app_glyph(name, w=3.6)
    b = g.split()[3].point(lambda v: 255 if v > 24 else 0).getbbox()
    g = g.crop(b)
    fit = size - 4
    k = fit / max(g.width, g.height)
    g = g.resize((max(1, round(g.width * k)), max(1, round(g.height * k))), Image.LANCZOS)
    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    out.alpha_composite(g, ((size - g.width) // 2, (size - g.height) // 2))
    return out


def centred_in(img, box):
    """Centre the drawing inside box (x0, y0, x1, y1) of the same-size image."""
    a = img.split()[3].point(lambda v: 255 if v > 24 else 0)
    b = a.getbbox()
    if not b:
        return img
    dx = (box[0] + box[2] - b[0] - b[2]) // 2
    dy = (box[1] + box[3] - b[1] - b[3]) // 2
    out = Image.new("RGBA", img.size, (0, 0, 0, 0))
    out.paste(img, (dx, dy))
    return out


# ---- power menu: 72 px line glyphs in ink (the glass button frames them) --------------------------------
def power(action, c):
    v = VSharp(72, 72)
    w = 4
    if action == "sleep":
        # a crescent outline: circle minus an offset circle, stroked by eroding the filled shape
        S = 72 * SS
        m = Image.new("L", (S, S), 0)
        d = ImageDraw.Draw(m)
        d.ellipse((14 * SS, 16 * SS, 56 * SS, 58 * SS), fill=255)
        d.ellipse((27 * SS, 6 * SS, 63 * SS, 42 * SS), fill=0)
        inner = m.filter(ImageFilter.MinFilter(2 * round(w * SS * 0.8) + 1))   # a crescent reads heavier: 0.8 of the stroke
        ring = Image.eval(Image.merge("L", [m]), lambda v: v)
        ring = Image.composite(Image.new("L", (S, S), 0), m, inner)
        layer = Image.new("RGBA", (S, S), rgba(c))
        layer.putalpha(ring)
        v.im.alpha_composite(layer)
        v.line([(53, 18), (53, 26)], 2.8, c)
        v.line([(49, 22), (57, 22)], 2.8, c)
    elif action == "reboot":
        v.arc(36, 37, 18, -40, 250, w, c, caps=False)
        a0 = math.radians(-40)
        ex, ey = 36 + 18 * math.cos(a0), 37 + 18 * math.sin(a0)
        tx, ty = -math.sin(a0), math.cos(a0)              # clockwise tangent at the end
        nx, ny = math.cos(a0), math.sin(a0)               # outward normal
        # head pointing back along the ring (anticlockwise direction = -tangent)
        tip = (ex - tx * 9, ey - ty * 9)
        v.poly([tip, (ex + nx * 8 + tx * 2, ey + ny * 8 + ty * 2), (ex - nx * 8 + tx * 2, ey - ny * 8 + ty * 2)], c)
        x1, y1 = 36 + 18 * math.cos(math.radians(250)), 37 + 18 * math.sin(math.radians(250))
        v.ellipse(x1 - w / 2, y1 - w / 2, x1 + w / 2, y1 + w / 2, fill=c)
    elif action == "logout":
        v.line([(32, 16), (18, 16), (18, 56), (32, 56)], w, c, joint="curve")
        v.line([(29, 36), (54, 36)], w, c)
        v.line([(46, 28), (54, 36), (46, 44)], w, c, joint="curve")
    elif action == "shutdown":
        g_power(v, 36, 38, 18, w, c)
    elif action == "saver":
        # a leaf: the lens between two circles, a midrib running out into the stem
        def leaf(d, k):
            m1 = Image.new("L", (72 * k, 72 * k), 0)
            ImageDraw.Draw(m1).ellipse((-9.3 * k, -13.3 * k, 58.7 * k, 54.7 * k), fill=255)
            m2 = Image.new("L", (72 * k, 72 * k), 0)
            ImageDraw.Draw(m2).ellipse((17.3 * k, 13.3 * k, 85.3 * k, 81.3 * k), fill=255)
            d._image.paste(255, (0, 0), ImageChops.multiply(m1, m2))
        stroke_shape(v, leaf, w, c)
        v.line([(12, 60), (44, 28)], w, c)
    return centred(v.final())


def power_button(action, focus):
    """Just the glyph, in ink: the power menu's glass button is the frame (Jason 2026-11-11).
    Highlighted, the button itself brightens; the glyph stays the same."""
    return power(action, INK)


# ---- pointer: 48 px (drawn at 2x of 24) ---------------------------------------------------------------
def pointer(shape):
    v = V(48, 48)
    K, Wt = (20, 22, 30), WHITE
    arrow = [(3, 2), (3, 34), (11, 26.5), (16.5, 38.5), (21.5, 36.5), (16.5, 25), (27, 25)]
    if shape in ("arrow", "progress"):
        sh = V(48, 48)
        sh.poly([(x + 1.5, y + 2) for x, y in arrow], (0, 0, 0, 90))
        img = sh.final().filter(ImageFilter.GaussianBlur(1.6))
        v.line(arrow + [arrow[0]], 4, Wt, joint="curve")
        v.poly(arrow, K)
        img.alpha_composite(v.final())
        if shape == "progress":
            s = V(48, 48)
            s.ellipse(27, 27, 45, 45, fill=Wt)
            s.arc(36, 36, 6, -90, 180, 3.2, ACCENT)
            img.alpha_composite(s.final())
        return img
    if shape == "hand":
        v.line([(16, 18), (16, 6), (20, 6), (20, 22), (20, 14), (24, 14), (24, 22), (24, 15), (28, 15),
                (28, 23), (28, 17), (32, 17), (32, 32), (28, 40), (17, 40), (9, 27), (12, 24), (16, 28),
                (16, 18)], 4.4, Wt, joint="curve")
        v.poly([(16, 18), (16, 6), (20, 6), (20, 14), (24, 14), (24, 15), (28, 15), (28, 17), (32, 17),
                (32, 32), (28, 40), (17, 40), (9, 27), (12, 24), (16, 28)], K)
        v.line([(20, 14), (20, 22)], 1.2, Wt)
        v.line([(24, 15), (24, 22)], 1.2, Wt)
        v.line([(28, 17), (28, 23)], 1.2, Wt)
        return v.final()
    if shape == "text":
        for c, w in ((Wt, 5.5), (K, 2.4)):
            v.line([(14, 5), (16.5, 5), (18, 7), (19.5, 5), (22, 5)], w, c)
            v.line([(18, 7), (18, 33)], w, c)
            v.line([(14, 35), (16.5, 35), (18, 33), (19.5, 35), (22, 35)], w, c)
        return v.final()
    if shape == "busy":
        v.ellipse(4, 4, 40, 40, fill=Wt)
        v.arc(22, 22, 12, 0, 360, 4.5, (200, 205, 220), caps=False)
        v.arc(22, 22, 12, -90, 150, 4.5, ACCENT)
        return v.final()


HOTSPOTS = {"arrow": [3, 2], "hand": [17, 5], "text": [18, 20], "busy": [22, 22], "progress": [3, 2]}


# ---- wallpaper ----------------------------------------------------------------------------------------
def wallpaper(w=960, h=720):
    """Blue to violet with soft flowing bands of light (original), smooth and noise-dithered."""
    import random
    top, bottom = (84, 140, 246), (134, 92, 232)
    base = Image.new("RGB", (w, h))
    px = base.load()
    for y in range(h):
        for x in range(w):
            t = min(1, max(0, 0.7 * y / h + 0.3 * x / w))
            px[x, y] = tuple(round(top[i] + (bottom[i] - top[i]) * t) for i in range(3))
    out = base.convert("RGBA")
    for (amp, phase, y0, thick, col) in ((0.10, 0.0, 0.42, 0.18, (170, 220, 255, 190)),
                                         (0.08, 1.7, 0.58, 0.14, (246, 160, 236, 170)),
                                         (0.12, 3.1, 0.74, 0.20, (186, 146, 255, 180)),
                                         (0.06, 4.4, 0.28, 0.10, (255, 255, 255, 140))):
        band = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        d = ImageDraw.Draw(band)
        top_pts, bot_pts = [], []
        for i in range(0, w + 1, 8):
            u = i / w
            yc = (y0 + amp * math.sin(2 * math.pi * (u * 0.9) + phase)) * h
            th = thick * h * (0.6 + 0.4 * math.sin(2 * math.pi * u + phase * 0.7))
            top_pts.append((i, yc - th / 2))
            bot_pts.append((i, yc + th / 2))
        d.polygon(top_pts + bot_pts[::-1], fill=col)
        out.alpha_composite(band.filter(ImageFilter.GaussianBlur(h * 0.05)))
    rnd = random.Random(7)
    noise = Image.frombytes("L", (w, h), bytes(rnd.randrange(124, 133) for _ in range(w * h)))
    return Image.merge("RGB", [ImageChops.add(ch, noise, 1, -128) for ch in out.convert("RGB").split()])


# ---- theme.json and CSS ---------------------------------------------------------------------------------
def hx(c, a=None):
    s = "#%02x%02x%02x" % c[:3]
    return s + ("%02x" % a if a is not None else "")


A = hx(ACCENT)
THEME = {
    "schema": 1, "id": "glass", "name": "Glass", "base": "light", "author": "Handtop",
    "description": "Light, modern: milky glass panels over a blue-violet gradient, monotone line icons, Inter.",
    "palette": {
        "bg": "#f4f6fb", "surface": "#ffffff", "surface_hi": "#e3e7f6", "border": "#cdd4e6",
        "fg": hx(INK), "fg_dim": "#5b6478", "accent": A, "accent_fg": "#4a49c4", "on_accent": "#ffffff",
        "warn": "#b86e00", "error": hx(RED), "brightness": hx(AMBER), "success": hx(GREEN),
    },
    "colors": {
        "taskbar.bg": "#00000000", "taskbar.border": "#00000000",
        "taskbar.apps_bg": "#00000000", "taskbar.apps_fg": hx(INK), "taskbar.active_bg": "#ffffffe6",
        "titlebar.active_bg": "#f4f6fb", "titlebar.inactive_bg": "#e6e9f2",
        "titlebar.active_fg": hx(INK), "titlebar.inactive_fg": "#6b7385",
        "titlebar.active_button": hx(INK), "titlebar.inactive_button": "#8a92a6",
        "drawer.bg": "#eef1fab8", "drawer.entry_bg": "#ffffffb3", "drawer.hover_bg": "#ffffffcc",
        "powermenu.backdrop": "#e6eaf7b3", "powermenu.button_bg": "#ffffff73",
        "powermenu.button_border": "#ffffffd9", "powermenu.hover_bg": "#ffffffd9", "powermenu.hover_border": "#ffffff",
        "powermenu.focus": A,
        "notify.bg": "#ffffffcc", "notify.border": "#ffffffe6",
        "osd.bg": "#ffffffcc", "osd.volume_border": A, "osd.volume_level": A,
        "osd.brightness_border": hx(AMBER), "osd.brightness_level": hx(AMBER), "osd.text": hx(INK),
        "osk.bg": "#eef1f8", "osk.key": "#ffffff", "osk.border": "#d5dbea",
        "status.bg": "#eef1f8",
        "terminal.bg": "#fbfcfe", "terminal.fg": hx(INK), "terminal.cursor": A,
        "terminal.cursor_text": "#ffffff", "terminal.selection_bg": "#c9ccf5", "terminal.selection_fg": hx(INK),
    },
    "wallpaper": {"color": "#5a5cd6", "image": "images/wallpaper.png", "mode": "fill"},
    "status_screen": {"style": "solid"},
    "gtk": {"color_scheme": "default", "theme": "Adwaita", "icon_theme": "Adwaita"},
    "cursor": {"size": 24, "hotspots": HOTSPOTS},
    "fonts": {"ui": "Inter Variable", "mono": "Noto Sans Mono", "scale": 1.0},
    "borders": 1,
}

GLASS = ("background-color: rgba(255, 255, 255, 0.55); border: 1px solid rgba(255, 255, 255, 0.75); "
         "box-shadow: inset 0 1px rgba(255, 255, 255, 0.95), inset 0 -1px rgba(255, 255, 255, 0.25), "
         "0 2px 6px rgba(16, 20, 48, 0.18);")
CSS = {
    "taskbar": f"""/* Glass: the bar itself is clear; its two ends float as glass capsules (a bright top edge,
   a soft shadow), like a dock. No background-image here: it would replace the Apps button's
   icon, which Handtop's own rule sets as a background image. */
window#waybar {{ background: transparent; border: none; }}
.modules-left, .modules-right {{ border-radius: 14px; margin: 3px 4px; {GLASS} }}
#custom-apps {{ border-radius: 9px; margin: 2px 1px 2px 2px; padding: 0 10px 0 29px; font-weight: 600; }}
#taskbar button {{ border-radius: 9px; margin: 2px 1px; }}
/* one look for every button under the pointer and for the active window: a brighter glass chip */
#custom-apps:hover, #taskbar button:hover, #taskbar button.active {{
  background-color: rgba(255, 255, 255, 0.85);
  box-shadow: inset 0 1px rgba(255, 255, 255, 1), 0 1px 2px rgba(16, 20, 48, 0.15);
}}
#clock {{ font-weight: 600; }}
""",
    "drawer": f"""/* Glass: a capsule search field and glass app tiles. */
entry {{ border-radius: 16px; {GLASS} }}
button {{ border-radius: 18px; margin: 4px; {GLASS} }}
button:hover {{ background-color: rgba(255, 255, 255, 0.85); }}
""",
    "powermenu": f"""/* Glass: large rounded glass tiles; the round icon lights up in its colour when highlighted. */
button {{ border-radius: 26px; {GLASS} }}
button:hover {{ box-shadow: inset 0 1px rgba(255, 255, 255, 1), 0 4px 12px rgba(16, 20, 48, 0.22); }}
""",
    "apps": f"""/* Glass: the accent for selections and main buttons in GTK 3 apps (Adwaita light). GTK also
   reads this in the taskbar, app drawer and power menu: the selectors are kept to lists, views
   and suggested buttons, which those three do not have. (@define-color does not reach
   Adwaita's built-in colours, so the rules are written out.) */
treeview.view:selected, .view:selected, iconview:selected, row:selected, list row:selected,
placessidebar row:selected, textview text selection, entry selection {{
  background-color: {A}; color: #ffffff;
}}
row:selected label, row:selected image {{ color: #ffffff; }}
button.suggested-action {{ background-image: none; background-color: {A}; border-color: #4a49c4; color: #ffffff; }}
button.suggested-action:hover {{ background-color: #6a6ae0; }}
check:checked, radio:checked, switch:checked {{ background-image: none; background-color: {A}; border-color: #4a49c4; }}
progressbar progress, scale highlight {{ background-image: none; background-color: {A}; border-color: {A}; }}
""",
}


def main(out):
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, "theme.json"), "w", encoding="utf-8") as f:
        json.dump(THEME, f, indent=2)
        f.write("\n")
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "src", "theme"))
    from handtop_theme import schema as S
    save(panel_apps(), out, "icons/taskbar/apps.png")
    save(panel_power(), out, "icons/taskbar/power.png")
    for m in S.INPUT_MODES:
        save(inputmode(m), out, f"icons/taskbar/inputmode-{m}.png")
    for ch in (False, True):
        for low in (False, True):
            for n in range(6):
                for sv in (False, True):
                    name = f"battery{'-charging' if ch else ''}{'-low' if low else ''}-{n}{'-saver' if sv else ''}"
                    save(battery(n, ch, low, sv), out, f"icons/taskbar/{name}.png")
    for w in S.WIFI:
        save(wifi(w), out, f"icons/tray/{w}.png")
    for b in S.BLUETOOTH:
        save(bluetooth(b), out, f"icons/tray/{b}.png")
    for name in S.HANDTOP_APPS + S.DEFAULT_APPS:
        save(app(name), out, f"icons/apps/{name}.png")
        for size in (22, 20):
            save(app_small(name, size), out, f"icons/apps/{name}@{size}.png")
    for act in S.POWER_ACTIONS:
        save(power_button(act, False), out, f"icons/power-menu/{act}.png")
        save(power_button(act, True), out, f"icons/power-menu/{act}-focus.png")
    for t in S.USB_TARGETS:
        save(usbtarget(t), out, f"icons/controller/usbtarget-{t}.png")
    for shape in S.CURSOR_SHAPES:
        save(pointer(shape), out, f"cursors/{shape}.png")
    save(wallpaper(), out, "images/wallpaper.png")
    for part, css in CSS.items():
        p = os.path.join(out, "css", f"{part}.css")
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            f.write(css)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "src/theme/extra/glass")
