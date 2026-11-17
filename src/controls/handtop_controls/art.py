"""The RG35XX H drawn as pixel art: the External Controller status screen's handheld, shared with
the Controls app so both show exactly the same drawing in every theme.

Drawn on a half-resolution canvas (PW x PH, whole pixels, no antialiasing) and shown scaled 2x.
Painter.draw_handheld() needs report() -> (buttons, hat, sticks, triggers) and pressed(name) from
the class that uses it (the status screen reads them from the controller service; the Controls app
shows nothing pressed). The colours come from the current theme's status.* entries (theme.env);
DARK is Handtop dark's set, used until a theme has been rendered.
Moved out of rg35xxh-controller-screen unchanged (2026-11-17); a pixel comparison of every theme in
an idle and a busy state was identical before and after.
"""
import cairo

W, H = 640, 480
PW, PH = W // 2, H // 2          # pixel-art canvas (scaled 2x)

# Geometry on the half-resolution canvas, measured from Anbernic's product photo of the RG35XX H
# (body ~2.07:1 with large rounded corners; positions as fractions of the body).
BX, BY, BW, BH, BR = 30, 60, 260, 126, 18                     # body
def at(fx, fy):
    return round(BX + fx * BW), round(BY + fy * BH)
SCR = (90, 69, 140, 105)                                      # screen: centred, 4:3, ~54 % of the width
DPAD, LSTICK = at(0.118, 0.385), at(0.118, 0.76)
FACE_C, RSTICK = at(0.885, 0.385), at(0.885, 0.76)
SELECT, START, LED = at(0.164, 0.156), at(0.83, 0.156), at(0.924, 0.18)
# Shoulder buttons sit side by side on the top face. Seen from the front (as drawn here): L2 just
# inward of the corner pokes up above the top edge as a low tab with slanted sides; L1 continues
# from it over the rounded corner as a cap that peaks on top and thins to nothing down the side.
# Mirrored on the right. (x0, x1) on the canvas.
L2_X, R2_X = (at(0.094, 0)[0], at(0.179, 0)[0]), (at(0.821, 0)[0], at(0.906, 0)[0])
L2_UP, L1_UP = 6, 4                                           # height above the top edge
L1_R = 18                                                     # L1/R1 cap outer corner radius

BG = (0.071, 0.082, 0.110)
BODY, BODY_EDGE, BODY_SHADE = (0.17, 0.18, 0.21), (0.30, 0.32, 0.37), (0.12, 0.13, 0.15)
PART, PART_EDGE = (0.09, 0.10, 0.12), (0.34, 0.36, 0.42)      # black buttons, like the real one
LABEL_COL = {"X": (0.36, 0.52, 1.0), "Y": (0.35, 0.82, 0.42), "A": (0.95, 0.30, 0.30), "B": (0.98, 0.85, 0.25)}
LIT, LIT_EDGE = (0.62, 0.76, 1.0), (0.85, 0.91, 1.0)

# Handtop dark's handheld ("solid", like the real black handheld): used until a theme has been
# rendered. The current theme's colours (status.* in its theme.env) replace it at start; Handtop
# light draws a "hologram" (translucent blue body, deep-blue outlines). Colours may carry alpha.
DARK = {"BODY": BODY, "BODY_EDGE": BODY_EDGE, "BODY_SHADE": BODY_SHADE, "PART": PART,
        "PART_EDGE": PART_EDGE, "LIT": LIT, "LIT_EDGE": LIT_EDGE, "BEZEL": (0.05, 0.05, 0.06),
        "BEZEL_EDGE": (0.24, 0.26, 0.30), "SCREEN": (0.03, 0.04, 0.05), "LED": (0.30, 0.85, 0.40),
        "CAP": (0.12, 0.13, 0.15), "FACE": LABEL_COL, "LABEL": None, "LABEL_LIT": (0.071, 0.082, 0.110)}


def src(cr, c):
    """Set a cairo source from an (r, g, b) or (r, g, b, a) tuple."""
    if len(c) == 4:
        cr.set_source_rgba(*c)
    else:
        cr.set_source_rgb(*c)
# HID report (rg35xxh-btpad): bytes 0-1 buttons, 2 hat (0-7, 8 = centre), 3-6 sticks LX LY RX RY,
# 7-8 triggers. Button bits follow the Xbox layout; the handheld's face labels are Nintendo-style.
BIT = {"xa": 0, "xb": 1, "xx": 2, "xy": 3, "l1": 4, "r1": 5, "select": 6, "start": 7, "l3": 8, "r3": 9}
FACE = {"X": "xy", "A": "xb", "B": "xa", "Y": "xx"}      # physical label -> Xbox button
HAT_DIRS = {0: "u", 1: "ur", 2: "r", 3: "dr", 4: "d", 5: "dl", 6: "l", 7: "ul"}


def status_palette():
    """The current theme's handheld colours (status.* in its theme.env, rendered by rg35xxh-theme)
    as a DARK-like dict, or None if no theme has been rendered (or it lacks them)."""
    import sys
    sys.path.insert(0, "/usr/local/lib/rg35xxh-theme")
    try:
        from handtop_theme import current
    except ImportError:
        return None
    c = current.colors("status")
    try:
        r = current.rgba
        pal = {k.upper(): r(c[k]) for k in ("body", "body_edge", "body_shade", "part", "part_edge", "lit",
                                            "lit_edge", "bezel", "bezel_edge", "screen", "led", "cap",
                                            "label", "label_lit")}
        pal["FACE"] = {b: r(c[f"face_{b.lower()}"]) for b in "XYAB"}
    except (KeyError, ValueError):
        return None
    return pal


class Painter:
    """Mixin: pixel-art helpers and the handheld. self.pal is the palette (DARK or status_palette())."""

    # pixel-art helpers (canvas coordinates, whole pixels, no antialiasing)
    @staticmethod
    def rect(cr, x, y, w, h, fill, edge=None):
        cr.rectangle(x, y, w, h)
        src(cr, fill)
        cr.fill()
        if edge:
            src(cr, edge)
            cr.rectangle(x + 0.5, y + 0.5, w - 1, h - 1)
            cr.set_line_width(1)
            cr.stroke()

    def clip_outside(self, cr, path_fn):
        """Intersect the clip with 'everything outside path_fn's shape' (even-odd with the canvas)."""
        cr.new_path()
        path_fn(cr)                                   # (may start its own path: add the canvas after)
        cr.rectangle(-10, -10, PW + 20, PH + 20)
        cr.set_fill_rule(cairo.FILL_RULE_EVEN_ODD)
        cr.clip()
        cr.set_fill_rule(cairo.FILL_RULE_WINDING)

    def body_path(self, cr):
        self.rrect_path(cr, BX, BY, BW, BH, BR)

    @staticmethod
    def tab_path(cr, x0, x1):
        cr.move_to(x0, BY + 2)
        cr.line_to(x0 + 2, BY - L2_UP + 1)
        cr.line_to(x0 + 3, BY - L2_UP)
        cr.line_to(x1 - 3, BY - L2_UP)
        cr.line_to(x1 - 2, BY - L2_UP + 1)
        cr.line_to(x1, BY + 2)
        cr.close_path()

    @staticmethod
    def cross_path(cr, cx, cy, a, h):
        """Plus shape covering pixels cx-a..cx+a x cy-h..cy+h and cx-h..cx+h x cy-a..cy+a."""
        l, r, t, b = cx - a, cx + a + 1, cy - a, cy + a + 1
        il, ir, it, ib = cx - h, cx + h + 1, cy - h, cy + h + 1
        cr.move_to(il, t)                             # new sub-path (don't join the previous one)
        for x, y in ((ir, t), (ir, it), (r, it), (r, ib), (ir, ib), (ir, b), (il, b),
                     (il, ib), (l, ib), (l, it), (il, it)):
            cr.line_to(x, y)
        cr.close_path()

    @staticmethod
    def rrect_path(cr, x, y, w, h, r):
        cr.new_path()
        cr.arc(x + w - r, y + r, r, -1.5708, 0)
        cr.arc(x + w - r, y + h - r, r, 0, 1.5708)
        cr.arc(x + r, y + h - r, r, 1.5708, 3.1416)
        cr.arc(x + r, y + r, r, 3.1416, 4.7124)
        cr.close_path()

    @staticmethod
    def rrect(cr, x, y, w, h, r, fill, edge=None):
        cr.new_path()
        cr.arc(x + w - r, y + r, r, -1.5708, 0)
        cr.arc(x + w - r, y + h - r, r, 0, 1.5708)
        cr.arc(x + r, y + h - r, r, 1.5708, 3.1416)
        cr.arc(x + r, y + r, r, 3.1416, 4.7124)
        cr.close_path()
        src(cr, fill)
        if edge:
            cr.fill_preserve()
            src(cr, edge)
            cr.set_line_width(1)
            cr.stroke()
        else:
            cr.fill()

    @staticmethod
    def circle(cr, x, y, r, fill, edge=None, odd=False):
        """odd=True: centre on pixel (x, y) itself -> 2r+1 px wide, symmetric around that pixel.
        Otherwise the centre is the corner between pixels (2r wide)."""
        cr.new_path()
        c = 0.5 if odd else 0
        cr.arc(x + c, y + c, r, 0, 6.2832)
        src(cr, fill)
        if edge:
            cr.fill_preserve()
            src(cr, edge)
            cr.set_line_width(1)
            cr.stroke()
        else:
            cr.fill()

    def draw_handheld(self, cr):
        cr.set_antialias(cairo.ANTIALIAS_NONE)
        P = self.pal
        _, hat, sticks, trig = self.report()
        hat_dir = HAT_DIRS.get(hat, "")
        # L1 / R1: corner caps. Outer shape = the body's rounded rect raised by L1_UP at the top
        # with radius L1_R, so it is L1_UP thick on top and tapers to 0 down the side. Each cap
        # runs under the L2/R2 tab (drawn next, in front), so its top outline meets the tab's
        # slanted side and the two read as one continuous line.
        for lit, x0, x1 in ((self.pressed("l1"), BX - 1, L2_X[0] + 3),
                            (self.pressed("r1"), R2_X[1] - 3, BX + BW + 1)):
            cr.save()
            cr.rectangle(x0, BY - L1_UP - 1, x1 - x0, BR + L1_UP + 1)
            cr.clip()
            self.clip_outside(cr, self.body_path)                   # only the part above the body
            tab = L2_X if x0 < BX + BW // 2 else R2_X
            self.clip_outside(cr, lambda c: self.tab_path(c, *tab))  # ... and not under the tab
            self.rrect_path(cr, BX, BY - L1_UP, BW, BH + L1_UP, L1_R)
            src(cr, (P["LIT"] if lit else P["PART"]))
            cr.fill_preserve()
            edge = P["LIT_EDGE"] if lit else P["PART_EDGE"]
            src(cr, edge)
            cr.set_line_width(1)
            cr.stroke()
            cr.restore()
        # L2 / R2: slanted tabs above the top edge (the body drawn next covers their base)
        for (x0, x1), lit in ((L2_X, trig[0] > 0), (R2_X, trig[1] > 0)):
            cr.save()
            self.clip_outside(cr, self.body_path)
            cr.new_path()
            self.tab_path(cr, x0, x1)
            src(cr, (P["LIT"] if lit else P["PART"]))
            cr.fill_preserve()
            src(cr, (P["LIT_EDGE"] if lit else P["PART_EDGE"]))
            cr.set_line_width(1)
            cr.stroke()
            cr.restore()
        # body
        self.rrect(cr, BX, BY, BW, BH, BR, P["BODY"], P["BODY_EDGE"])
        # screen with its black bezel
        sx, sy, sw, sh = SCR
        self.rect(cr, sx - 3, sy - 3, sw + 6, sh + 6, P["BEZEL"], P["BEZEL_EDGE"])
        self.rect(cr, sx, sy, sw, sh, P["SCREEN"])
        # power LED
        self.rect(cr, LED[0], LED[1], 2, 2, P["LED"])
        # D-pad (upper left): one plus shape, 2*A+1 px long and T px thick (both odd, so the
        # centre pixel is DPAD itself). Edge = the 1 px ring between the plus and the plus inset
        # by 1 px (even-odd), fill = the inset plus: no seam where the bars cross, and nothing is
        # painted twice (matters for the translucent light-theme style).
        cx, cy = DPAD
        A, T = 20, 13
        h = T // 2
        cr.new_path()
        self.cross_path(cr, cx, cy, A, h)
        self.cross_path(cr, cx, cy, A - 1, h - 1)
        cr.set_fill_rule(cairo.FILL_RULE_EVEN_ODD)
        src(cr, P["PART_EDGE"])
        cr.fill()
        cr.set_fill_rule(cairo.FILL_RULE_WINDING)
        self.cross_path(cr, cx, cy, A - 1, h - 1)
        src(cr, P["PART"])
        cr.fill()
        arms = {"u": (cx - h + 1, cy - A + 1, T - 2, A - h - 1), "d": (cx - h + 1, cy + h + 1, T - 2, A - h - 1),
                "l": (cx - A + 1, cy - h + 1, A - h - 1, T - 2), "r": (cx + h + 1, cy - h + 1, A - h - 1, T - 2)}
        for d, (x, y, w, hh) in arms.items():
            if d in hat_dir:
                self.rect(cr, x, y, w, hh, P["LIT"])
        # face buttons (upper right): X top, A right, B bottom, Y left, as printed on the handheld
        fx, fy = FACE_C
        g = 14
        self.face = {}
        for label, (dx, dy) in {"X": (0, -1), "A": (1, 0), "B": (0, 1), "Y": (-1, 0)}.items():
            x, y = fx + dx * g, fy + dy * g
            lit = self.pressed(FACE[label])
            self.circle(cr, x, y, 7, P["FACE"][label] if lit else P["PART"], P["LIT_EDGE"] if lit else P["PART_EDGE"],
                        odd=True)                       # 15 px, centred on pixel (x, y)
            self.face[label] = (x, y, lit)
        # sticks (lower left / lower right): recessed ring + cap that moves
        for (x, y), (ax, ay), btn in ((LSTICK, (sticks[0], sticks[1]), "l3"),
                                      (RSTICK, (sticks[2], sticks[3]), "r3")):
            self.circle(cr, x, y, 19, P["BODY_SHADE"], P["PART_EDGE"])
            ox, oy = round((ax - 128) / 128 * 6), round((ay - 128) / 128 * 6)
            lit = self.pressed(btn)
            moved = abs(ax - 128) > 12 or abs(ay - 128) > 12
            self.circle(cr, x + ox, y + oy, 12, P["LIT"] if lit else P["PART"], P["LIT_EDGE"] if (lit or moved) else P["PART_EDGE"])
            self.circle(cr, x + ox, y + oy, 8, P["LIT"] if lit else P["CAP"])
        # Select / Start: small round buttons above the D-pad and the face buttons
        for name, (x, y) in (("select", SELECT), ("start", START)):
            lit = self.pressed(name)
            self.circle(cr, x, y, 4, P["LIT"] if lit else P["PART"], P["LIT_EDGE"] if lit else P["PART_EDGE"])
