"""The Controls app's window (rg35xxh-controls). 640x480, everything reachable with the pointer (stick /
D-pad) and A; Escape (L1) goes back from a sub-page.

  Buttons          the handheld drawn as on the External Controller status screen (art.py) at 2x;
                   the button under the pointer lights up as pressed when it can be changed;
                   click it to pick what it does (a list; a key; a key combination; an app)
  Pointer & more   pointer speed, acceleration, scroll speed, natural scrolling, gamepad layout,
                   vibration (buzzes as you set it), Re-center sticks

Every change is written to the active profile (store.py) and the input daemon applies it within
0.1 s. Changes to buttons or to how the pointer moves first run as a trial: "Keep these controls?"
with a 15 s countdown, undone unless kept (by the daemon itself if this app is gone). A change that
leaves no left click or no pointer movement gets a warning before that. Keys set in the boot
partition's rg35xxh-input.conf are locked here; with its use_app_settings = no nothing is editable.
"""
import subprocess

import cairo
import gi
gi.require_version("Gdk", "3.0")
gi.require_version("Gtk", "3.0")
from gi.repository import Gdk, GLib, Gtk, Pango  # noqa: E402

from . import actions as A  # noqa: E402
from . import art  # noqa: E402
from . import scrolltest  # noqa: E402
from .advanced import AdvancedMixin  # noqa: E402
from . import store  # noqa: E402

K = 2                                            # the drawing's scale (pixel art: whole steps only)
CX0, CY0 = art.BX - 4, art.BY - 13               # the part of the half-resolution canvas shown
CW, CH = art.BW + 8, art.BH + 15
ACCEL = [(1.0, "Off"), (2.0, "Normal"), (3.0, "Precise")]
CSS = b"""
.rg-banner { border: 1px solid alpha(@theme_fg_color, 0.6); border-radius: 4px; padding: 6px 8px; }
.rg-dim { opacity: 0.75; }
.rg-mapping { border: 1px solid alpha(@theme_fg_color, 0.35); border-radius: 4px; padding: 4px 8px; }
"""


def _label(text="", markup=None, dim=False, **kw):
    lab = Gtk.Label(xalign=0, **kw)
    if markup:
        lab.set_markup(markup)
    else:
        lab.set_text(text)
    if dim:
        lab.get_style_context().add_class("rg-dim")
    lab.set_line_wrap(True)
    lab.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
    return lab


# Our button names -> the status screen's names for the same controls (art.BIT / art.FACE).
LIT_NAME = {"a": "xb", "b": "xa", "x": "xy", "y": "xx", "l1": "l1", "r1": "r1", "l3": "l3", "r3": "r3",
            "select": "select", "start": "start"}


class Handheld(art.Painter):
    """The drawing, with the button under the pointer drawn as pressed (the status screen's own
    "pressed" look in the theme's colours): that is how the app shows what can be clicked."""
    def __init__(self, pal):
        self.pal = pal
        self.hover = None

    def report(self):
        trig = [255 if self.hover == "l2" else 0, 255 if self.hover == "r2" else 0]
        return 0, 8, [128, 128, 128, 128], trig

    def pressed(self, name):
        return self.hover is not None and LIT_NAME.get(self.hover) == name


def hit_areas(face):
    """Button -> (x0, y0, x1, y1) on the half-resolution canvas, for clicks and the focus ring."""
    a = {}
    for label, (x, y, _lit) in face.items():
        a[label.lower()] = (x - 9, y - 9, x + 10, y + 10)
    for name, (x, y) in (("l3", art.LSTICK), ("r3", art.RSTICK)):
        a[name] = (x - 20, y - 20, x + 20, y + 20)
    for name, (x, y) in (("select", art.SELECT), ("start", art.START)):
        a[name] = (x - 9, y - 7, x + 9, y + 7)
    a["l2"] = (art.L2_X[0], art.BY - art.L2_UP - 6, art.L2_X[1], art.BY + 2)
    a["r2"] = (art.R2_X[0], art.BY - art.L2_UP - 6, art.R2_X[1], art.BY + 2)
    a["l1"] = (art.BX - 2, art.BY - art.L1_UP - 6, art.L2_X[0] - 1, art.BY + 10)
    a["r1"] = (art.R2_X[1] + 1, art.BY - art.L1_UP - 6, art.BX + art.BW + 2, art.BY + 10)
    return a


class App(AdvancedMixin):
    def __init__(self):
        self.loop = GLib.MainLoop()
        prov = Gtk.CssProvider()
        prov.load_from_data(CSS)
        Gtk.StyleContext.add_provider_for_screen(Gdk.Screen.get_default(), prov,
                                                 Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        self.hh = Handheld(art.status_palette() or art.DARK)
        self.sel = "a"
        self.app_names = dict(A.apps())
        self.busy = False                  # a trial dialog is open
        self.timers = {}
        self.action_from = self.scroll_from = "main"   # where Back goes from those pages
        self.pending, self.last_run = {}, {}       # _throttle
        self._filling_settings = False
        self.win = Gtk.Window(title="Controls")
        self.win.set_default_size(640, 440)
        self.win.connect("destroy", lambda *a: self.loop.quit())
        self.win.connect("key-press-event", self._key)
        self.stack = Gtk.Stack()
        self.win.add(self.stack)
        self.stack.add_named(self._main_page(), "main")
        self.stack.add_named(self._action_page(), "action")
        self.stack.add_named(self._keys_page(), "keys")
        self.stack.add_named(self._apps_page(), "apps")
        self.stack.add_named(self._scroll_test_page(), "scrolltest")
        self.stack.add_named(self._advanced_page(), "advanced")
        self.stack.add_named(self._macro_page(), "macro")
        self.stack.add_named(self._macro_pick_page(), "macropick")
        self.refresh()

    def run(self):
        self.win.show_all()
        self.stack.set_visible_child_name("main")
        self.loop.run()

    # ---- state -----------------------------------------------------------------------------------
    def refresh(self):
        """Read the profile layers again and show them."""
        self.values, self.cfg = store.effective()
        self.locked = self.cfg.locked
        off = not self.cfg.app_settings
        self.rescue.set_visible(off)
        self.rescue_text.set_text("Controls are in rescue mode: the boot partition's rg35xxh-input.conf "
                                  "says use_app_settings = no, so nothing set here is used. Put the # back "
                                  "in front of that line to use this app again.")
        self.tabs.set_sensitive(not off)
        self._fill_profiles()
        self._fill_settings()
        self.area.queue_draw()
        self._show_mapping()
        self.advanced_refresh()

    def is_locked(self, sec, key):
        return f"{sec}.{key}" in self.locked

    def change(self, sec, key, value, preview=False):
        """One setting changed by the user: save it (trial first where needed)."""
        if self.busy or self.values.get(sec, key) == value:
            return
        new = self.values.copy()
        new.set(sec, key, value)
        if store.needs_trial(sec, key):
            self.trial(new)
        else:
            store.write_profile(store.active(), new)
            self.values = new
            if preview:
                store.request_vibration_preview()

    def trial(self, new, profile=None, save=False, on_keep=None):
        """Warn if the minimal controls break, then run the change for 15 s with Keep / Undo."""
        probs = store.problems(new)
        if probs and not self._warn(probs):
            self.refresh()
            return
        self.busy = True
        until = store.start_trial(new)
        d = Gtk.MessageDialog(transient_for=self.win, modal=True, message_type=Gtk.MessageType.QUESTION,
                              buttons=Gtk.ButtonsType.NONE, text="Keep these controls?")
        d.add_buttons("Undo", Gtk.ResponseType.CANCEL, "Keep", Gtk.ResponseType.OK)
        d.set_default_response(Gtk.ResponseType.CANCEL)

        state = {"tid": None}

        def tick():
            left = int(round(until - GLib.get_real_time() / 1e6))
            if left <= 0:
                state["tid"] = None
                d.response(Gtk.ResponseType.CANCEL)
                return False
            d.format_secondary_text(f"They are on now. Undone in {left} s unless you choose Keep.")
            return True
        tick()
        state["tid"] = GLib.timeout_add(250, tick)
        r = d.run()
        if state["tid"]:
            GLib.source_remove(state["tid"])
        d.destroy()
        # Keep counts only before the end time: after it the daemon has already undone the change.
        if r == Gtk.ResponseType.OK and until > GLib.get_real_time() / 1e6:
            if profile:                    # switching profiles: the profile file holds the values
                if save:                   # ... unless they are new (Reset everything)
                    store.write_profile(profile, new)
                store.set_active(profile)
                store.cancel()
            else:
                store.keep(new)
            if on_keep:
                on_keep()
        else:
            store.cancel()
        self.busy = False
        self.refresh()

    def _warn(self, probs):
        d = Gtk.MessageDialog(transient_for=self.win, modal=True, message_type=Gtk.MessageType.WARNING,
                              buttons=Gtk.ButtonsType.NONE, text="This leaves you without basic controls")
        d.format_secondary_text("\n".join(probs) + "\n\nIt is undone after 15 s unless you keep it. "
                                "Rescue: uncomment use_app_settings = no in rg35xxh-input.conf on the boot partition.")
        d.add_buttons("Cancel", Gtk.ResponseType.CANCEL, "Try it", Gtk.ResponseType.OK)
        d.set_default_response(Gtk.ResponseType.CANCEL)
        r = d.run()
        d.destroy()
        return r == Gtk.ResponseType.OK

    PARENT = {"keys": "action", "apps": "action", "macropick": "action", "advanced": "main", "macro": "advanced"}

    def back(self):
        page = self.stack.get_visible_child_name()
        parent = {"action": self.action_from, "scrolltest": self.scroll_from}.get(page) or self.PARENT.get(page, "main")
        self.stack.set_visible_child_name(parent)

    def _key(self, _w, ev):
        if ev.keyval == Gdk.KEY_Escape and self.stack.get_visible_child_name() != "main":
            self.back()
            return True
        return False

    # ---- main page -------------------------------------------------------------------------------
    def _main_page(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6, margin=6)
        self.rescue = Gtk.Box(no_show_all=True)
        self.rescue.get_style_context().add_class("rg-banner")
        self.rescue_text = _label()
        self.rescue_text.show()
        self.rescue.pack_start(self.rescue_text, True, True, 0)
        box.pack_start(self.rescue, False, False, 0)
        # The profile picker sits at the end of the tab row: 640x480 has no room for its own row.
        head = Gtk.Box(spacing=6, margin_end=4)
        head.pack_start(_label("Profile"), False, False, 0)
        self.profile_combo = Gtk.ComboBoxText()
        self.profile_combo.connect("changed", self._profile_changed)
        head.pack_start(self.profile_combo, False, False, 0)
        adv = Gtk.Button(label="Advanced ›")
        adv.connect("clicked", lambda *_: self.open_advanced())
        head.pack_start(adv, False, False, 0)
        head.show_all()
        self.tabs = Gtk.Notebook()
        self.tabs.append_page(self._buttons_tab(), Gtk.Label(label="Buttons"))
        self.tabs.append_page(self._pointer_tab(), Gtk.Label(label="Pointer & more"))
        self.tabs.set_action_widget(head, Gtk.PackType.END)
        box.pack_start(self.tabs, True, True, 0)
        return box

    def _fill_profiles(self):
        self._filling = True
        self.profile_combo.remove_all()
        names = store.profiles()
        for n in names:
            self.profile_combo.append(n, "Default" if n == "default" else n)
        self.profile_combo.set_active_id(store.active() if store.active() in names else "default")
        self._filling = False

    def _profile_changed(self, combo):
        if getattr(self, "_filling", False) or self.busy:
            return
        name = combo.get_active_id()
        if not name or name == store.active():
            return
        s, b, h = store.read_profile(name)
        new = store.system_values()
        new.settings.update(s)
        new.bindings.update(b)
        new.hardware.update(h)
        self.trial(new, profile=name)

    # ---- Buttons tab -----------------------------------------------------------------------------
    def _buttons_tab(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4, margin=4)
        self.area = Gtk.DrawingArea()
        self.area.set_size_request(CW * K, CH * K)
        self.area.add_events(Gdk.EventMask.BUTTON_PRESS_MASK | Gdk.EventMask.POINTER_MOTION_MASK
                             | Gdk.EventMask.LEAVE_NOTIFY_MASK)
        self.area.connect("motion-notify-event", self._hover)
        self.area.connect("leave-notify-event", self._hover)
        self.area.connect("draw", self._draw)
        self.area.connect("button-press-event", self._click)
        box.pack_start(self.area, False, False, 0)
        row = Gtk.Box(spacing=8)
        row.get_style_context().add_class("rg-mapping")
        self.map_label = _label()
        self.map_label.set_line_wrap(False)
        self.map_label.set_ellipsize(Pango.EllipsizeMode.END)
        row.pack_start(self.map_label, True, True, 0)
        row.pack_start(_label("D-pad, Volume, F, Power: Advanced", dim=True), False, False, 0)
        self.change_btn = Gtk.Button(label="Change…")
        self.change_btn.connect("clicked", lambda *_: self.open_action(self.sel))
        row.pack_start(self.change_btn, False, False, 0)
        box.pack_start(row, False, False, 0)
        return box

    def _draw(self, w, cr):
        alloc = w.get_allocation()
        ox = max(0, (alloc.width - CW * K) // 2)
        self.origin = ox
        canvas = cairo.ImageSurface(cairo.FORMAT_ARGB32, art.PW, art.PH)
        self.hh.draw_handheld(cairo.Context(canvas))
        cr.save()
        cr.translate(ox, 0)
        cr.scale(K, K)
        cr.set_source_surface(canvas, -CX0, -CY0)
        cr.get_source().set_filter(cairo.FILTER_NEAREST)
        cr.paint()
        cr.restore()
        self.areas = hit_areas(self.hh.face)
        P = self.hh.pal
        fg = w.get_style_context().get_color(Gtk.StateFlags.NORMAL)

        def at(x, y):
            return ox + (x - CX0 + 0.5) * K, (y - CY0 + 0.5) * K

        def text(s, x, y, size, color, bold=True):
            cr.select_font_face("Noto Sans", cairo.FONT_SLANT_NORMAL,
                                cairo.FONT_WEIGHT_BOLD if bold else cairo.FONT_WEIGHT_NORMAL)
            cr.set_font_size(size)
            e = cr.text_extents(s)
            cr.move_to(round(x - e.x_bearing - e.width / 2), round(y - e.y_bearing - e.height / 2))
            if isinstance(color, Gdk.RGBA):
                cr.set_source_rgba(color.red, color.green, color.blue, color.alpha)
            else:
                art.src(cr, color)
            cr.show_text(s)
        for label, (x, y, _lit) in self.hh.face.items():           # letters on the face buttons
            lit = self.hh.hover == label.lower()
            text(label, *at(x, y), 15, P["LABEL_LIT"] if lit else (P["LABEL"] or art.LABEL_COL[label]))
        tags = {"l2": ((art.L2_X[0] + art.L2_X[1]) / 2, art.BY - art.L2_UP - 5),
                "r2": ((art.R2_X[0] + art.R2_X[1]) / 2, art.BY - art.L2_UP - 5),
                "l1": (art.BX + 4, art.BY - art.L1_UP - 5), "r1": (art.BX + art.BW - 4, art.BY - art.L1_UP - 5),
                "select": (art.SELECT[0], art.SELECT[1] + 8), "start": (art.START[0], art.START[1] + 8)}
        for name, (x, y) in tags.items():                             # names of the small buttons
            text(name.upper() if len(name) == 2 else name.capitalize(), *at(x, y), 9, fg, bold=False)
        return False

    def _at_pointer(self, ev):
        """The button under the pointer, or None."""
        if not hasattr(self, "areas"):
            return None
        x = (ev.x - self.origin) / K + CX0
        y = ev.y / K + CY0
        return next((n for n, (x0, y0, x1, y1) in self.areas.items() if x0 <= x <= x1 and y0 <= y <= y1), None)

    def _hover(self, w, ev):
        name = None if ev.type == Gdk.EventType.LEAVE_NOTIFY else self._at_pointer(ev)
        # only what can be changed lights up (a key set by the boot file can't, nor anything in rescue mode)
        lit = name if name and not self.is_locked("desktop", name) and self.cfg.app_settings else None
        if lit != self.hh.hover:
            self.hh.hover = lit
            w.get_window().set_cursor(Gdk.Cursor.new_from_name(w.get_display(), "pointer") if lit else None)
            self.area.queue_draw()
        self._show_mapping(name)
        return False

    def _click(self, _w, ev):
        name = self._at_pointer(ev)
        if name is None:
            return False
        self.sel = name
        self._show_mapping()
        self.open_action(name)
        return True

    def _show_mapping(self, button=None):
        """The line under the picture: the button under the pointer, else the last one picked."""
        b = button or self.sel
        name = A.button_name(b)
        act = A.describe(self.values.bindings.get(b, "none"), self.app_names)
        lock = "   (set by the boot partition file)" if self.is_locked("desktop", b) else ""
        self.map_label.set_markup(f"<b>{GLib.markup_escape_text(name)}</b>   {GLib.markup_escape_text(act)}"
                                  f"<small>{lock}</small>")
        self.change_btn.set_sensitive(not self.is_locked("desktop", self.sel))

    # ---- action list -----------------------------------------------------------------------------
    def _page(self, title_attr):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6, margin=8)
        head = Gtk.Box(spacing=8)
        back = Gtk.Button(label="‹ Back")
        back.connect("clicked", lambda *_: self.back())
        head.pack_start(back, False, False, 0)
        title = _label()
        setattr(self, title_attr, title)
        head.pack_start(title, True, True, 0)
        box.pack_start(head, False, False, 0)
        sw = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER)
        box.pack_start(sw, True, True, 0)
        return box, sw

    def _action_page(self):
        box, sw = self._page("action_title")
        lb = Gtk.ListBox()
        lb.set_activate_on_single_click(True)
        lb.connect("row-activated", self._action_chosen)
        sw.add(lb)
        self.action_list = lb
        return box

    def _fill_actions(self, button):
        """The list for this button: its own extras first (the D-pad's pointer, volume and
        brightness for Vol / F / Power), then what every button can do."""
        for row in self.action_list.get_children():
            self.action_list.remove(row)
        for value, text in A.extras(button) + A.SIMPLE + [("@key", "A key…"), ("@combo", "Key combination…"),
                                                          ("@app", "Open an app…"), ("@macro", "Run a macro…"),
                                                          ("macro_record", "Record macro (start / pause)")]:
            row = Gtk.ListBoxRow()
            row.value = value
            row.add(_label(text, margin=6))
            self.action_list.add(row)
        self.action_list.show_all()

    def open_action(self, button, origin="main"):
        if self.is_locked("desktop", button) or not self.cfg.app_settings:
            return
        self.hh.hover = None                   # back on the picture, nothing stays lit
        self.action_from = origin
        self._fill_actions(button)
        if origin != "main":
            self.pic_sel = self.sel                # the picture's button stays picked meanwhile
        self.sel = button
        cur = self.values.bindings.get(button, "none")
        self.action_title.set_markup(f"<b>{GLib.markup_escape_text(A.button_name(button))}</b>   now: "
                                     f"{GLib.markup_escape_text(A.describe(cur, self.app_names))}")
        self.stack.set_visible_child_name("action")

    def _action_chosen(self, _lb, row):
        v = row.value
        if v == "@key":
            self._open_keys(combo=False)
        elif v == "@combo":
            self._open_keys(combo=True)
        elif v == "@macro":
            self._open_macro_pick()
        elif v == "@app":
            self.apps_title.set_markup(f"<b>{A.button_name(self.sel)}</b> opens an app")
            self.stack.set_visible_child_name("apps")
        else:
            self._set_binding(v)

    def _set_binding(self, action):
        self.stack.set_visible_child_name(self.action_from)
        self.change("desktop", self.sel, action)
        if self.action_from != "main":
            self.sel = getattr(self, "pic_sel", "a")
        self._show_mapping()
        self.advanced_refresh()

    # ---- keys / combination ----------------------------------------------------------------------
    def _keys_page(self):
        box, sw = self._page("keys_title")
        inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.mods_box = Gtk.Box(spacing=6)
        self.mods = {}
        for k, name in A.MODIFIERS:
            cb = Gtk.CheckButton(label=name)
            self.mods[k] = cb
            self.mods_box.pack_start(cb, False, False, 0)
        inner.pack_start(self.mods_box, False, False, 0)
        flow = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE, max_children_per_line=8, homogeneous=True)
        for k, name in A.KEYS:
            b = Gtk.Button(label=name)
            b.connect("clicked", self._key_chosen, k)
            flow.add(b)
        inner.pack_start(flow, False, False, 0)
        sw.add(inner)
        return box

    def _open_keys(self, combo):
        self.combo_mode = combo
        for cb in self.mods.values():
            cb.set_active(False)
        self.mods_box.set_visible(combo)
        self.mods_box.set_no_show_all(not combo)
        what = "a key combination: tick Ctrl / Alt / Shift / Super, then pick the key" if combo else "a key"
        self.keys_title.set_markup(f"<b>{A.button_name(self.sel)}</b> types {what}")
        self.stack.set_visible_child_name("keys")
        if combo:
            self.mods_box.show_all()

    def _key_chosen(self, _b, key):
        if self.combo_mode:
            mods = [k for k, cb in self.mods.items() if cb.get_active() and k != key]
            if not mods:
                self.keys_title.set_markup(f"<b>{A.button_name(self.sel)}</b>: tick at least one of "
                                           "Ctrl / Alt / Shift / Super first")
                return
            self._set_binding("combo:" + "+".join(mods[:3] + [key]))
        else:
            self._set_binding("key:" + key)

    # ---- apps ------------------------------------------------------------------------------------
    def _apps_page(self):
        box, sw = self._page("apps_title")
        lb = Gtk.ListBox()
        lb.set_activate_on_single_click(True)
        for app_id, name in A.apps():
            row = Gtk.ListBoxRow()
            row.app_id = app_id
            row.add(_label(name, margin=6))
            lb.add(row)
        lb.connect("row-activated", lambda _lb, row: self._set_binding("launch:" + row.app_id))
        sw.add(lb)
        return box

    # ---- Pointer & more tab ----------------------------------------------------------------------
    def _pointer_tab(self):
        sw = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER)
        g = Gtk.Grid(column_spacing=12, row_spacing=8, margin=8)
        sw.add(g)
        self.ctl = {}
        rows = [
            ("settings", "pointer_max_speed", "Pointer speed", self._scale(50, 1500, 10, 0, "px/s")),
            ("settings", "pointer_curve", "Acceleration", self._choice([c for c, _ in ACCEL], [n for _, n in ACCEL])),
            ("settings", "scroll_speed", "Scroll speed", self._scale(1, 30, 0.1, 1)),
            ("settings", "natural_scroll", "Natural scrolling", self._switch()),
            ("settings", "pad_layout", "Gamepad buttons", self._choice(["position", "label"], ["By position", "By label"])),
            ("settings", "haptic_strength", "Vibration", self._scale(0, 100, 10, 0, "%", 100)),
        ]
        for i, (sec, key, text, (widget, get, put)) in enumerate(rows):
            g.attach(_label(text), 0, i, 1, 1)
            g.attach(getattr(widget, "rg_box", widget), 1, i, 1, 1)
            widget.set_hexpand(True)
            self._register(widget, sec, key, get, put)
            if key == "scroll_speed":                 # the test page: scroll a list while setting it
                try_btn = Gtk.Button(label="Try…")
                try_btn.connect("clicked", lambda *_: self.open_scroll_test("main"))
                g.attach(try_btn, 2, i, 1, 1)
        rc = Gtk.Button(label="Re-center sticks")
        rc.connect("clicked", lambda *_: subprocess.Popen(["rg35xxh-recenter-sticks"]))
        g.attach(rc, 0, len(rows), 1, 1)
        g.attach(_label("Hands off the sticks while it counts down.", dim=True), 1, len(rows), 1, 1)
        g.attach(_label("Vibration buzzes as you set it. Pointer speed and acceleration ask "
                        "\"Keep these controls?\" before they stay.", dim=True), 0, len(rows) + 1, 3, 1)
        return sw

    def _register(self, widget, sec, key, get, put):
        self.ctl.setdefault((sec, key), []).append((widget, get, put))
        self._connect(widget, sec, key, get)
        if isinstance(widget, Gtk.Scale):
            # the right stick scrolls: over a slider it would move the slider instead of the page
            widget.connect("scroll-event", lambda *_: True)

    # ---- scroll test page ------------------------------------------------------------------------
    def open_scroll_test(self, origin):
        self.scroll_from = origin
        self.stack.set_visible_child_name("scrolltest")

    def _scroll_test_page(self):
        """Scroll speed and natural scrolling, with something to try them on (scrolltest.py): an article
        that scrolls up / down on the left, a plan that scrolls every way on the right. The right
        stick scrolls whichever is under the pointer; a change applies while the slider is dragged."""
        box, sw = self._page("scroll_title")
        self.scroll_title.set_markup("<b>Try scrolling</b>: right stick over either side")
        g = Gtk.Grid(column_spacing=12, row_spacing=6)
        for i, (key, text, made) in enumerate((("scroll_speed", "Scroll speed", self._scale(1, 30, 0.1, 1)),
                                               ("natural_scroll", "Natural scrolling", self._switch()))):
            widget, get, put = made
            widget.set_hexpand(True)
            g.attach(_label(text), 0, i, 1, 1)
            g.attach(getattr(widget, "rg_box", widget), 1, i, 1, 1)
            self._register(widget, "settings", key, get, put)
        box.pack_start(g, False, False, 0)
        box.reorder_child(g, 1)                   # between the title row and the list
        # Two halves: an article that scrolls up / down only, and a plan that scrolls every way.
        box.remove(sw)
        halves = Gtk.Box(spacing=6, homogeneous=True)
        for title, content, hpol in (("Up and down", scrolltest.article(), Gtk.PolicyType.NEVER),
                                     ("Every direction", scrolltest.plan(), Gtk.PolicyType.AUTOMATIC)):
            col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            col.pack_start(_label(title, dim=True), False, False, 0)
            view = Gtk.ScrolledWindow(hscrollbar_policy=hpol, vexpand=True)
            view.set_shadow_type(Gtk.ShadowType.IN)
            view.add(content)
            col.pack_start(view, True, True, 0)
            halves.pack_start(col, True, True, 0)
        box.pack_start(halves, True, True, 0)
        return box

    def _scale(self, lo, hi, step, digits=0, unit="", factor=1):
        """Every slider in the app: a slider with a number box beside it (same value), so it can be
        dragged, stepped with the box's - / + or typed (X opens the on-screen keyboard). lo / hi /
        step are in shown units; factor converts to the setting's (100 with "%": 0.5 shows as 50 %).
        Registered by the slider; its .rg_box is what gets attached."""
        adj = Gtk.Adjustment(value=lo, lower=lo, upper=hi, step_increment=step, page_increment=step * 10)
        s = Gtk.Scale(orientation=Gtk.Orientation.HORIZONTAL, adjustment=adj, draw_value=False, hexpand=True)
        s.set_digits(digits)
        spin = Gtk.SpinButton(adjustment=adj, digits=digits, numeric=True, width_chars=5)
        spin.connect("scroll-event", lambda *_: True)     # the right stick must not change it
        box = Gtk.Box(spacing=6)
        box.pack_start(s, True, True, 0)
        box.pack_start(spin, False, False, 0)
        box.pack_start(Gtk.Label(label=unit, width_chars=3, xalign=0), False, False, 0)  # aligned boxes
        s.rg_box = box
        return (s, (lambda: round(round(s.get_value() / step) * step / factor, 4)),
                (lambda v: s.set_value(v * factor)))

    def _choice(self, values, names):
        box = Gtk.Box(spacing=0)
        box.get_style_context().add_class("linked")
        btns = []
        for v, n in zip(values, names):
            b = Gtk.ToggleButton(label=n)
            b.value = v
            btns.append(b)
            box.pack_start(b, False, False, 0)
        box.btns = btns

        def get():
            return next((b.value for b in btns if b.get_active()), None)

        def put(v):
            for b in btns:
                b.set_active(b.value == v)
        return box, get, put

    def _switch(self):
        s = Gtk.Switch(halign=Gtk.Align.START)
        return s, s.get_active, s.set_active

    def _connect(self, widget, sec, key, get):
        if isinstance(widget, Gtk.Scale) and key in ("haptic_strength", "scroll_speed"):
            # vibration and scroll speed: felt while dragging, applied at most every 0.45 s (a
            # vibration sample lasts ~0.36 s; the input daemon re-uploads at most every 0.3 s)
            widget.connect("value-changed", lambda *_: None if self._filling_settings else
                           self._throttle(key, 450, lambda: self._user(sec, key, get(), widget)))
        elif isinstance(widget, Gtk.Scale):
            # dragging: apply once it rests (a pointer-speed trial must not start mid-drag)
            # (setting the shown value fires value-changed too: ignored while filling)
            widget.connect("value-changed", lambda *_: None if self._filling_settings else
                           self._debounce(key, 600, lambda: self._user(sec, key, get(), widget)))
        elif isinstance(widget, Gtk.Switch):
            widget.connect("notify::active", lambda *_: self._user(sec, key, get(), widget))
        else:
            for b in widget.btns:
                b.connect("toggled", lambda btn: btn.get_active() and self._user(sec, key, btn.value))

    def _throttle(self, key, ms, fn):
        """Run fn now if the last run was at least ms ago, else once at that point (with the newest
        fn): a value that keeps changing is applied regularly, and its last value always."""
        self.pending[key] = fn
        if self.timers.get(key):
            return
        wait = self.last_run.get(key, 0) + ms / 1000 - GLib.get_monotonic_time() / 1e6

        def fire():
            self.timers[key] = None
            self.last_run[key] = GLib.get_monotonic_time() / 1e6
            self.pending.pop(key)()
            return False
        if wait <= 0:
            fire()
        else:
            self.timers[key] = GLib.timeout_add(int(wait * 1000), fire)

    def _debounce(self, key, ms, fn):
        if self.timers.get(key):
            GLib.source_remove(self.timers[key])

        def fire():
            self.timers[key] = None
            fn()
            return False
        self.timers[key] = GLib.timeout_add(ms, fire)

    def _user(self, sec, key, value, source=None):
        if self._filling_settings:
            return
        value = round(value, 2) if isinstance(value, float) else value
        # Power: a tap must end before the hold shuts down (else the menu could never open)
        if key == "power_tap_max_seconds":
            value = min(value, round(self.values.settings["power_hold_seconds"] - 0.5, 2))
        elif key == "power_hold_seconds":
            value = max(value, round(self.values.settings["power_tap_max_seconds"] + 0.5, 2))
        if isinstance(value, float) and abs(value - self.values.get(sec, key)) < 1e-6:
            return
        self.change(sec, key, value, preview=(key == "haptic_strength"))
        if not self.busy:
            # not back into the slider being dragged: it is ahead of the value just saved
            self._fill_settings(skip=source)

    def _fill_settings(self, skip=None):
        self._filling_settings = True
        for (sec, key), shown in self.ctl.items():
            v = self.values.get(sec, key)
            locked = self.is_locked(sec, key)
            for widget, get, put in shown:
                if widget is skip:
                    continue
                if key == "pointer_curve" and hasattr(widget, "btns") and v not in [c for c, _ in ACCEL]:
                    for b in widget.btns:
                        b.set_active(False)
                else:
                    put(v)
                shown_w = getattr(widget, "rg_box", widget)
                shown_w.set_sensitive(not locked)
                shown_w.set_tooltip_text("Set by the boot partition file (rg35xxh-input.conf)" if locked else None)
        self._filling_settings = False


def run():
    App().run()
