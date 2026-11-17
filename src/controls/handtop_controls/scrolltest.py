"""Content for the Controls app's scroll test page: something that scrolls like the real thing.

article()  a web-page-like article (headings, paragraphs of different lengths, pictures with
           captions, a list, a quote) that scrolls up and down only
plan()     a large map-like plan (a lettered / numbered grid with blocks, roads and pins) that
           scrolls in every direction, so horizontal scrolling and diagonals can be tried

Everything is drawn in the window's theme colours (GTK's foreground and selection colours), so it
looks right in every Handtop theme. The text is Handtop's own (no outside material)."""
import math
import random

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Pango  # noqa: E402

PLAN_CELL, PLAN_COLS, PLAN_ROWS = 110, 20, 20       # 2200 x 2200 px plan
_SENT = [
    "A pocket-sized computer changes how often you reach for a bigger one.",
    "Most of the time you only need to read something, answer something or check something quickly.",
    "The sticks turn into a pointer and a scroll wheel, and the buttons into clicks and keys.",
    "Long pages are where the scroll speed matters most: too slow and you push the stick forever, too fast and you overshoot the part you wanted.",
    "Try a full push for one second and count how far the page moves.",
    "Then try a small push: the first part of the stick's travel should give slow, careful scrolling.",
    "Natural scrolling turns the direction around, the way a touchscreen moves under your finger.",
    "Neither way is right or wrong; it is whatever your thumb expects.",
    "A good setting lets you skim a whole article without thinking about the stick at all.",
    "Pictures and headings make it easy to see how far you went, which plain lines of text do not.",
    "On a big monitor the same push covers more of the page, because the page is longer on screen.",
    "If you change the speed while reading, the next push uses the new value straight away.",
]
_HEADS = ["Getting started", "Reading long pages", "Small pushes, big pushes", "Which way is up",
          "Pictures help", "On a monitor", "Fine tuning", "When you are done"]


def _rgba(w, name):
    ok, c = w.get_style_context().lookup_color(name)
    return c if ok else w.get_style_context().get_color(Gtk.StateFlags.NORMAL)


def _fg(w):
    return w.get_style_context().get_color(Gtk.StateFlags.NORMAL)


def _set(cr, c, a=1.0):
    cr.set_source_rgba(c.red, c.green, c.blue, c.alpha * a)


def _picture(seed, caption):
    """A drawn "photo" (hills, sun, a path) with a caption, in theme colours."""
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
    area = Gtk.DrawingArea()
    area.set_size_request(-1, 110)
    rnd = random.Random(seed)
    hills = [(rnd.uniform(0, 1), rnd.uniform(0.35, 0.7), rnd.uniform(0.25, 0.5)) for _ in range(3)]
    sun = (rnd.uniform(0.15, 0.85), rnd.uniform(0.15, 0.35))

    def draw(w, cr):
        a = w.get_allocation()
        W, H = a.width, a.height
        fg, acc = _fg(w), _rgba(w, "theme_selected_bg_color")
        _set(cr, fg, 0.08)
        cr.rectangle(0, 0, W, H)
        cr.fill()
        _set(cr, acc, 0.55)
        cr.arc(sun[0] * W, sun[1] * H, 13, 0, 2 * math.pi)
        cr.fill()
        for i, (cx, top, half) in enumerate(hills):
            _set(cr, fg, 0.18 + 0.1 * i)
            cr.move_to((cx - half) * W, H)
            cr.curve_to(cx * W - half * W / 3, top * H, cx * W + half * W / 3, top * H, (cx + half) * W, H)
            cr.close_path()
            cr.fill()
        _set(cr, acc, 0.8)
        cr.set_line_width(3)
        cr.move_to(W * 0.5, H)
        cr.curve_to(W * 0.45, H * 0.8, W * 0.6, H * 0.75, W * 0.55, H * 0.6)
        cr.stroke()
        _set(cr, fg, 0.35)
        cr.set_line_width(1)
        cr.rectangle(0.5, 0.5, W - 1, H - 1)
        cr.stroke()
        return False
    area.connect("draw", draw)
    box.pack_start(area, False, False, 0)
    cap = Gtk.Label(xalign=0)
    cap.set_markup(f"<small><i>{caption}</i></small>")
    box.pack_start(cap, False, False, 0)
    return box


def _para(text, markup=False):
    lab = Gtk.Label(xalign=0, yalign=0)
    lab.set_line_wrap(True)
    lab.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
    lab.set_max_width_chars(1)        # wrap to the column's width instead of widening it
    if markup:
        lab.set_markup(text)
    else:
        lab.set_text(text)
    return lab


def article():
    """Up / down only: the article in a box (the caller puts it in a ScrolledWindow)."""
    rnd = random.Random(7)
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8, margin=8)
    box.pack_start(_para("<span size='x-large' weight='bold'>Scrolling with a stick</span>", True), False, False, 0)
    box.pack_start(_para("<small>Handtop · a test page for the Controls app</small>", True), False, False, 0)
    fig = 1
    for n, head in enumerate(_HEADS, 1):
        box.pack_start(_para(f"<span size='large' weight='bold'>{n}. {head}</span>", True), False, False, 4)
        for _ in range(rnd.randint(2, 3)):
            box.pack_start(_para(" ".join(rnd.sample(_SENT, rnd.randint(2, 5)))), False, False, 0)
        if n % 2:
            box.pack_start(_picture(n, f"Figure {fig}: {head.lower()}"), False, False, 0)
            fig += 1
        if n == 3:
            items = ["Full push: count how far one second takes you", "Small push: should be slow and steady",
                     "Let go: the page stops at once"]
            box.pack_start(_para("\n".join("•  " + i for i in items)), False, False, 0)
        if n == 6:
            box.pack_start(_para("<i>“Change the speed while reading: the next push uses it.”</i>", True),
                           False, False, 0)
    box.pack_start(_para("<small>End of the page. Scroll back up to the top.</small>", True), False, False, 8)
    return box


def plan():
    """Every direction: a DrawingArea larger than the view (the caller puts it in a ScrolledWindow
    with both scrollbars). Draws only what is visible."""
    area = Gtk.DrawingArea()
    area.set_size_request(PLAN_CELL * PLAN_COLS, PLAN_CELL * PLAN_ROWS)
    rnd = random.Random(3)
    blocks = {(c, r): rnd.random() for c in range(PLAN_COLS) for r in range(PLAN_ROWS)}
    pins = {(rnd.randrange(PLAN_COLS), rnd.randrange(PLAN_ROWS)) for _ in range(28)}

    def draw(w, cr):
        x0, y0, x1, y1 = cr.clip_extents()
        fg, acc = _fg(w), _rgba(w, "theme_selected_bg_color")
        S = PLAN_CELL
        cr.select_font_face("Noto Sans", 0, 1)
        for c in range(max(0, int(x0 // S)), min(PLAN_COLS, int(x1 // S) + 1)):
            for r in range(max(0, int(y0 // S)), min(PLAN_ROWS, int(y1 // S) + 1)):
                x, y = c * S, r * S
                v = blocks[(c, r)]
                _set(cr, fg, 0.04 if (c + r) % 2 else 0.08)          # park / block checker
                cr.rectangle(x, y, S, S)
                cr.fill()
                _set(cr, fg, 0.16)                                    # buildings
                for i in range(int(v * 4)):
                    cr.rectangle(x + 14 + (i % 2) * 44, y + 14 + (i // 2) * 44, 34, 34)
                    cr.fill()
                _set(cr, fg, 0.55)                                    # cell name: column letter + row
                cr.set_font_size(13)
                name = f"{chr(65 + c)}{r + 1}"
                e = cr.text_extents(name)
                cr.move_to(x + S - e.width - 8, y + S - 8)
                cr.show_text(name)
                if (c, r) in pins:                                    # a pin to aim for
                    _set(cr, acc, 0.9)
                    cr.arc(x + S / 2, y + S / 2 - 6, 9, 0, 2 * math.pi)
                    cr.fill()
                    cr.move_to(x + S / 2 - 6, y + S / 2)
                    cr.line_to(x + S / 2, y + S / 2 + 14)
                    cr.line_to(x + S / 2 + 6, y + S / 2)
                    cr.fill()
        _set(cr, fg, 0.45)                                            # roads along the grid
        cr.set_line_width(4)
        for c in range(PLAN_COLS + 1):
            if x0 - 4 <= c * S <= x1 + 4:
                cr.move_to(c * S, y0)
                cr.line_to(c * S, y1)
        for r in range(PLAN_ROWS + 1):
            if y0 - 4 <= r * S <= y1 + 4:
                cr.move_to(x0, r * S)
                cr.line_to(x1, r * S)
        cr.stroke()
        return False
    area.connect("draw", draw)
    return area
