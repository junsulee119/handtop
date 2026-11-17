"""The Controls app's Advanced page: everything else the input daemon can do, in sections picked
on the left.

  More buttons   the D-pad directions, Volume + / -, a tap of F and a tap of Power (desktop mode
                 only), each with a warning first; holding Power to shut down stays fixed
  Combinations   first + second button -> an action (combos_macros.py)
  Macros         lists of steps, built here or recorded (combos_macros.py)
  Pointer        D-pad pointer speed, the acceleration curve in detail, speed on a monitor, and a
                 test area with targets
  Sticks         both sticks live (dead zone drawn), dead zone, swap sticks, invert each axis,
                 Re-center sticks
  Scrolling      the scroll curve; the scroll test page
  Timing         hold Start to leave gamepad mode, Power hold / tap times, Volume repeat
  Profiles       use, new, duplicate, rename, delete, export, import
  Reset          this profile, or everything

Mixed into app.App (it uses App's change(), trial(), _register(), _scale() ...)."""
import os
import subprocess
import json

import gi
gi.require_version("Gdk", "3.0")
gi.require_version("Gtk", "3.0")
from gi.repository import Gdk, GLib, Gtk  # noqa: E402

from . import actions as A  # noqa: E402
from . import store  # noqa: E402
from .combos_macros import ComboMacroMixin  # noqa: E402

RUNTIME = os.environ.get("XDG_RUNTIME_DIR", "/tmp")
STICK_WANT = os.path.join(RUNTIME, "rg35xxh-controls-sticks.want")
STICK_FEED = os.path.join(RUNTIME, "rg35xxh-controls-sticks")


def _lab(text, dim=False, markup=False, **kw):
    lab = Gtk.Label(xalign=0, **kw)
    lab.set_line_wrap(True)
    if markup:
        lab.set_markup(text)
    else:
        lab.set_text(text)
    if dim:
        lab.get_style_context().add_class("rg-dim")
    return lab


class AdvancedMixin(ComboMacroMixin):
    # ---- page --------------------------------------------------------------------------------
    def _advanced_page(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6, margin=6)
        head = Gtk.Box(spacing=8)
        back = Gtk.Button(label="‹ Back")
        back.connect("clicked", lambda *_: self.back())
        head.pack_start(back, False, False, 0)
        head.pack_start(_lab("<b>Advanced</b>", markup=True), True, True, 0)
        box.pack_start(head, False, False, 0)
        body = Gtk.Box(spacing=6)
        self.adv = Gtk.Stack()
        self.adv.connect("notify::visible-child-name", lambda *_: self._sticks_watch())
        side = Gtk.StackSidebar(stack=self.adv)
        side.set_size_request(118, -1)
        body.pack_start(side, False, False, 0)
        body.pack_start(self.adv, True, True, 0)
        box.pack_start(body, True, True, 0)
        for name, title, make in (("buttons", "More buttons", self._sec_buttons),
                                  ("combos", "Combinations", self._sec_combos), ("macros", "Macros", self._sec_macros),
                                  ("pointer", "Pointer", self._sec_pointer),
                                  ("sticks", "Sticks", self._sec_sticks), ("scroll", "Scrolling", self._sec_scroll),
                                  ("timing", "Timing", self._sec_timing), ("profiles", "Profiles", self._sec_profiles),
                                  ("reset", "Reset", self._sec_reset)):
            sw = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER)
            inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8, margin=6)
            make(inner)
            sw.add(inner)
            self.adv.add_titled(sw, name, title)
        self.stack.connect("notify::visible-child-name", lambda *_: self._sticks_watch())
        return box

    def open_advanced(self):
        if not self.cfg.app_settings:
            return
        self.stack.set_visible_child_name("advanced")

    def advanced_refresh(self):
        if not hasattr(self, "more_rows"):
            return
        for button, (lab, btn) in self.more_rows.items():
            lock = self.is_locked("desktop", button)
            lab.set_text(A.describe(self.values.bindings[button], self.app_names)
                         + ("  (boot partition file)" if lock else ""))
            btn.set_sensitive(not lock)
        self._fill_profile_list()
        self.combos_refresh()
        self.macros_refresh()

    def _grid(self, inner):
        g = Gtk.Grid(column_spacing=10, row_spacing=8)
        inner.pack_start(g, False, False, 0)
        return g

    def _rows(self, inner, rows, note=None):
        """rows: (section, key, label, (widget, get, put)); registered like the Pointer & more tab."""
        g = self._grid(inner)
        for i, (sec, key, text, made) in enumerate(rows):
            widget, get, put = made
            widget.set_hexpand(True)
            g.attach(_lab(text), 0, i, 1, 1)
            g.attach(getattr(widget, "rg_box", widget), 1, i, 1, 1)
            self._register(widget, sec, key, get, put)
        if note:
            inner.pack_start(_lab(note, dim=True), False, False, 0)
        return g

    # ---- More buttons ------------------------------------------------------------------------
    def _sec_buttons(self, inner):
        inner.pack_start(_lab("These normally do one fixed job. Change them only if you have a reason: "
                              "each change asks first and then runs 15 s on trial. Desktop mode only; "
                              "holding Power to shut down can't be changed.", dim=True), False, False, 0)
        g = self._grid(inner)
        self.more_rows = {}
        for i, (button, name) in enumerate(A.MORE_BUTTONS):
            g.attach(_lab(name), 0, i, 1, 1)
            cur = _lab("", hexpand=True)
            g.attach(cur, 1, i, 1, 1)
            b = Gtk.Button(label="Change…")
            b.connect("clicked", lambda _b, bt=button: self._change_more(bt))
            g.attach(b, 2, i, 1, 1)
            self.more_rows[button] = (cur, b)

    def _change_more(self, button):
        d = Gtk.MessageDialog(transient_for=self.win, modal=True, message_type=Gtk.MessageType.WARNING,
                              buttons=Gtk.ButtonsType.NONE, text=f"Change {A.button_name(button)}?")
        d.format_secondary_text(A.warning(button) + "\n\nThe change runs 15 s on trial, then asks to keep it.")
        d.add_buttons("Cancel", Gtk.ResponseType.CANCEL, "Change", Gtk.ResponseType.OK)
        d.set_default_response(Gtk.ResponseType.CANCEL)
        r = d.run()
        d.destroy()
        if r == Gtk.ResponseType.OK:
            self.open_action(button, origin="advanced")

    def _lit(self):
        """The theme's highlight for controls (status.lit: the pressed-button colour on the handheld
        drawing), as a Gdk.RGBA-like object: visible on every theme, High contrast included."""
        c = self.hh.pal["LIT"]
        return Gdk.RGBA(c[0], c[1], c[2], c[3] if len(c) == 4 else 1.0)

    # ---- Pointer -----------------------------------------------------------------------------
    def _sec_pointer(self, inner):
        self._rows(inner, [
            ("settings", "dpad_speed_ratio", "D-pad speed", self._scale(5, 200, 5, 0, "%", 100)),
            ("settings", "pointer_curve", "Acceleration", self._scale(0.5, 5, 0.1, 1)),
            ("settings", "display_speed_scale", "On a monitor", self._scale(0, 200, 5, 0, "%", 100)),
        ], "D-pad speed is a share of the stick's top speed. Acceleration: 1 = even, higher = finer near "
           "the centre (Off / Normal / Precise are 1 / 2 / 3). On a monitor: 100 % moves as far across a big "
           "screen as across the handheld's, 0 % keeps the handheld's speed.")
        inner.pack_start(_lab("<b>Test area</b>: click the dots", markup=True), False, False, 0)
        self.targets = Gtk.DrawingArea()
        self.targets.set_size_request(-1, 150)
        self.targets.add_events(Gdk.EventMask.BUTTON_PRESS_MASK)
        self.hits = set()
        dots = [(0.08, 0.2), (0.3, 0.75), (0.5, 0.15), (0.7, 0.6), (0.92, 0.25), (0.15, 0.85), (0.85, 0.9),
                (0.5, 0.5), (0.62, 0.32), (0.38, 0.4)]

        def draw(w, cr):
            a = w.get_allocation()
            fg = w.get_style_context().get_color(Gtk.StateFlags.NORMAL)
            acc = self._lit()
            cr.set_source_rgba(fg.red, fg.green, fg.blue, 0.06)
            cr.rectangle(0, 0, a.width, a.height)
            cr.fill()
            for i, (fx, fy) in enumerate(dots):
                r = 6 if i % 3 else 4                          # some small, some smaller
                c = acc if i in self.hits else fg
                cr.set_source_rgba(c.red, c.green, c.blue, 0.9 if i in self.hits else 0.6)
                cr.arc(fx * a.width, fy * a.height, r, 0, 6.2832)
                cr.fill()
            cr.set_source_rgba(fg.red, fg.green, fg.blue, 0.7)
            cr.move_to(8, a.height - 8)
            cr.set_font_size(11)
            cr.show_text(f"{len(self.hits)} of {len(dots)}" + ("   all hit: click to start again" if
                                                                   len(self.hits) == len(dots) else ""))
            return False

        def click(w, ev):
            a = w.get_allocation()
            if len(self.hits) == len(dots):
                self.hits.clear()
            for i, (fx, fy) in enumerate(dots):
                if (ev.x - fx * a.width) ** 2 + (ev.y - fy * a.height) ** 2 <= 9 ** 2:
                    self.hits.add(i)
            w.queue_draw()
            return True
        self.targets.connect("draw", draw)
        self.targets.connect("button-press-event", click)
        inner.pack_start(self.targets, False, False, 0)

    # ---- Sticks ------------------------------------------------------------------------------
    def _sec_sticks(self, inner):
        self.stick_view = Gtk.DrawingArea()
        self.stick_view.set_size_request(-1, 170)
        self.stick_view.connect("draw", self._draw_sticks)
        self.stick_data = None
        inner.pack_start(self.stick_view, False, False, 0)
        dz = self._scale(0, 60, 1, 0, "%", 100)
        self.dz_scale, self.dz_get = dz[0], dz[1]
        dz[0].connect("value-changed", lambda *_: self.stick_view.queue_draw())   # the ring follows the slider
        self._rows(inner, [
            ("settings", "deadzone", "Dead zone", dz),
            ("settings", "swap_sticks", "Swap sticks", self._switch()),
        ])
        g = self._grid(inner)
        g.attach(_lab("Invert"), 0, 0, 1, 1)
        for i, (k, text) in enumerate((("invert_lx", "Left X"), ("invert_ly", "Left Y"),
                                        ("invert_rx", "Right X"), ("invert_ry", "Right Y"))):
            cb = Gtk.CheckButton(label=text)
            g.attach(cb, 1 + i, 0, 1, 1)
            self.ctl.setdefault(("hardware", k), []).append((cb, cb.get_active, cb.set_active))
            cb.connect("toggled", lambda b, key=k: None if self._filling_settings else
                       self._user("hardware", key, b.get_active(), b))
        rc = Gtk.Button(label="Re-center sticks", halign=Gtk.Align.START)
        rc.connect("clicked", lambda *_: subprocess.Popen(["rg35xxh-recenter-sticks"]))
        inner.pack_start(rc, False, False, 0)
        inner.pack_start(_lab("The circles show each stick as the pointer sees it. Inside the hatched "
                              "dead zone nothing moves (the dot turns grey); it follows the slider as you "
                              "drag. Changes here run 15 s on trial.", dim=True), False, False, 0)

    def _sticks_watch(self):
        """While the Sticks section is on screen, ask the input daemon for the stick feed (it stops
        by itself 2 s after the last request) and redraw from it."""
        on = (self.stack.get_visible_child_name() == "advanced"
              and self.adv.get_visible_child_name() == "sticks")
        if on and not getattr(self, "stick_timer", None):
            self._stick_tick_want()
            self.stick_timer = (GLib.timeout_add(1000, self._stick_tick_want),
                                GLib.timeout_add(50, self._stick_tick_read))
        elif not on and getattr(self, "stick_timer", None):
            for t in self.stick_timer:
                GLib.source_remove(t)
            self.stick_timer = None

    def _stick_tick_want(self):
        try:
            with open(STICK_WANT, "w"):
                pass
        except OSError:
            pass
        return True

    def _stick_tick_read(self):
        try:
            with open(STICK_FEED) as f:
                data = json.loads(f.readline() or "null")
        except (OSError, ValueError):
            data = None
        if data != self.stick_data:
            self.stick_data = data
            self.stick_view.queue_draw()
        return True

    def _draw_sticks(self, w, cr):
        a = w.get_allocation()
        fg = w.get_style_context().get_color(Gtk.StateFlags.NORMAL)
        acc = self._lit()
        d = self.stick_data
        R = min(a.height / 2 - 14, a.width / 4 - 14)
        dz = self.dz_get()                       # the slider's value, also while dragging it
        for i, (side, kx, ky) in enumerate((("Left", "lx", "ly"), ("Right", "rx", "ry"))):
            cx, cy = a.width * (0.25 + 0.5 * i), a.height / 2 - 4
            cr.new_path()                          # (text leaves a current point behind)
            cr.set_source_rgba(fg.red, fg.green, fg.blue, 0.5)
            cr.set_line_width(1.5)
            cr.arc(cx, cy, R, 0, 6.2832)
            cr.stroke()
            # dead zone: a hatched disc with a dashed edge; inside it the stick does nothing
            cr.save()
            cr.arc(cx, cy, R * dz, 0, 6.2832)
            cr.clip()
            cr.set_source_rgba(fg.red, fg.green, fg.blue, 0.12)
            cr.paint()
            cr.set_source_rgba(fg.red, fg.green, fg.blue, 0.35)
            cr.set_line_width(1)
            for k in range(-int(R), int(R) + 1, 6):
                cr.move_to(cx + k - R, cy + R)
                cr.line_to(cx + k + R, cy - R)
            cr.stroke()
            cr.restore()
            cr.set_source_rgba(acc.red, acc.green, acc.blue, 0.9)
            cr.set_line_width(2)
            cr.set_dash([4, 3])
            cr.arc(cx, cy, max(R * dz, 1), 0, 6.2832)
            cr.stroke()
            cr.set_dash([])
            cr.set_font_size(11)
            cr.set_source_rgba(fg.red, fg.green, fg.blue, 0.8)
            cr.move_to(cx - 14, a.height - 2)
            cr.show_text(side)
            if d:
                x, y = d.get(kx, 0.0), d.get(ky, 0.0)
                inside = (x * x + y * y) ** 0.5 <= dz
                c, al = (fg, 0.45) if inside else (acc, 1)     # dim while the stick is ignored
                cr.set_source_rgba(c.red, c.green, c.blue, al)
                cr.set_line_width(1.5)
                cr.move_to(cx, cy)
                cr.line_to(cx + x * R, cy + y * R)
                cr.stroke()
                cr.arc(cx + x * R, cy + y * R, 4, 0, 6.2832)
                cr.fill()
            cr.set_source_rgba(acc.red, acc.green, acc.blue, 1)    # the dead zone's size, next to it
            cr.move_to(cx + R * dz + 6, cy - R * dz - 2)
            cr.show_text(f"{dz:.0%}")
        if not d:
            cr.set_source_rgba(fg.red, fg.green, fg.blue, 0.8)
            cr.move_to(8, 14)
            cr.show_text("Waiting for the controls…")
        return False

    # ---- Scrolling ---------------------------------------------------------------------------
    def _sec_scroll(self, inner):
        self._rows(inner, [("settings", "scroll_log_k", "Scroll curve", self._scale(0, 30, 1, 0))],
                   "Higher: a small push already scrolls quickly. 0: even all the way.")
        t = Gtk.Button(label="Try scrolling…", halign=Gtk.Align.START)
        t.connect("clicked", lambda *_: self.open_scroll_test("advanced"))
        inner.pack_start(t, False, False, 0)

    # ---- Timing ------------------------------------------------------------------------------
    def _sec_timing(self, inner):
        self._rows(inner, [
            ("settings", "start_hold_seconds", "Leave gamepad mode", self._scale(0.2, 5, 0.1, 1, "s")),
            ("settings", "power_hold_seconds", "Power: hold to shut down", self._scale(1, 10, 0.5, 1, "s")),
            ("settings", "power_tap_max_seconds", "Power: longest tap", self._scale(0.2, 3, 0.1, 1, "s")),
            ("settings", "vol_repeat_delay", "Volume: repeat after", self._scale(0.1, 2, 0.05, 2, "s")),
            ("settings", "vol_repeat_interval", "Volume: repeat every", self._scale(0.03, 1, 0.01, 2, "s")),
        ], "Leave gamepad mode: how long to hold Start. Power: a press up to the longest tap opens the menu; "
           "between that and the hold time nothing happens; holding to the hold time shuts down.")

    # ---- Profiles ----------------------------------------------------------------------------
    def _sec_profiles(self, inner):
        self.profile_list = Gtk.ListBox()
        self.profile_list.set_selection_mode(Gtk.SelectionMode.SINGLE)
        frame = Gtk.Frame()
        frame.add(self.profile_list)
        inner.pack_start(frame, False, False, 0)
        row = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE, max_children_per_line=4, homogeneous=True)
        for text, fn in (("Use", self._p_use), ("New", self._p_new), ("Duplicate", self._p_dup),
                         ("Rename", self._p_rename), ("Delete", self._p_delete), ("Export…", self._p_export),
                         ("Import…", self._p_import)):
            b = Gtk.Button(label=text)
            b.connect("clicked", lambda _b, f=fn: f())
            row.add(b)
        inner.pack_start(row, False, False, 0)
        self.profile_note = _lab("", dim=True)
        inner.pack_start(self.profile_note, False, False, 0)

    def _fill_profile_list(self):
        if not hasattr(self, "profile_list"):
            return
        sel = self._p_selected() or store.active()
        for r in self.profile_list.get_children():
            self.profile_list.remove(r)
        for n in store.profiles():
            r = Gtk.ListBoxRow()
            r.name = n
            r.add(_lab(("Default" if n == "default" else n) + ("   (in use)" if n == store.active() else ""),
                       margin=6))
            self.profile_list.add(r)
            if n == sel:
                self.profile_list.select_row(r)
        self.profile_list.show_all()

    def _p_selected(self):
        r = self.profile_list.get_selected_row() if hasattr(self, "profile_list") else None
        return r.name if r else None

    def _ask_name(self, title, initial):
        d = Gtk.Dialog(title=title, transient_for=self.win, modal=True)
        d.add_buttons("Cancel", Gtk.ResponseType.CANCEL, "OK", Gtk.ResponseType.OK)
        e = Gtk.Entry(text=initial, activates_default=True)
        d.set_default_response(Gtk.ResponseType.OK)
        d.get_content_area().pack_start(_lab("Name (letters, digits, space . _ -). X opens the keyboard."),
                                        False, False, 6)
        d.get_content_area().pack_start(e, False, False, 6)
        d.show_all()
        r = d.run()
        name = e.get_text().strip()
        d.destroy()
        return name if r == Gtk.ResponseType.OK and name else None

    def _note(self, text):
        self.profile_note.set_text(text)

    def _p_use(self):
        name = self._p_selected()
        if name and name != store.active():
            self.profile_combo.set_active_id(name)        # same path as the picker: trial first

    def _p_new(self):
        name = self._ask_name("New profile", store.free_name("Profile"))
        if name:
            self._note(f"Created {name}." if store.new_profile(name) else f"Can't use the name {name!r}.")
            self.refresh()

    def _p_dup(self):
        src = self._p_selected() or store.active()
        name = self._ask_name("Duplicate profile", store.free_name(src))
        if name:
            self._note(f"Copied to {name}." if store.new_profile(name, copy_from=src) else f"Can't use the name {name!r}.")
            self.refresh()

    def _p_rename(self):
        old = self._p_selected()
        if not old or old == "default":
            self._note("Default can't be renamed.")
            return
        name = self._ask_name("Rename profile", old)
        if name and name != old:
            self._note(f"Renamed to {name}." if store.rename_profile(old, name) else f"Can't use the name {name!r}.")
            self.refresh()

    def _p_delete(self):
        name = self._p_selected()
        if not name or name == "default":
            self._note("Default can't be deleted.")
            return
        if name == store.active():
            self._note("Use another profile first.")      # deleting the one in use would switch controls untried
            return
        store.delete_profile(name)
        self._note(f"Deleted {name}.")
        self.refresh()

    def _chooser(self, title, action, name=None):
        d = Gtk.FileChooserDialog(title=title, transient_for=self.win, action=action)
        d.add_buttons("Cancel", Gtk.ResponseType.CANCEL,
                      "Save" if action == Gtk.FileChooserAction.SAVE else "Open", Gtk.ResponseType.OK)
        d.set_current_folder(os.path.expanduser("~"))
        if name:
            d.set_current_name(name)
            d.set_do_overwrite_confirmation(True)
        r = d.run()
        path = d.get_filename() if r == Gtk.ResponseType.OK else None
        d.destroy()
        return path

    def _p_export(self):
        name = self._p_selected() or store.active()
        path = self._chooser("Export profile", Gtk.FileChooserAction.SAVE, f"controls-{name}{store.EXPORT_SUFFIX}")
        if path:
            try:
                store.export_profile(name, path)
                self._note(f"Saved {os.path.basename(path)}.")
            except OSError as e:
                self._note(f"Could not save: {e.strerror}.")

    def _p_import(self):
        path = self._chooser("Import profile", Gtk.FileChooserAction.OPEN)
        if not path:
            return
        base = os.path.splitext(os.path.basename(path))[0]
        name = store.free_name(base[len("controls-"):] if base.startswith("controls-") else base)
        try:
            n = store.import_profile(path, name)
            self._note(f"Imported as {name} ({n} settings). Choose Use to try it.")
        except (OSError, ValueError) as e:
            self._note(f"Could not import: {e}.")
        self.refresh()

    # ---- Reset -------------------------------------------------------------------------------
    def _sec_reset(self, inner):
        inner.pack_start(_lab("Back to Handtop's defaults. Both run 15 s on trial first.", dim=True),
                         False, False, 0)
        b1 = Gtk.Button(label="Reset this profile", halign=Gtk.Align.START)
        b1.connect("clicked", lambda *_: self.trial(store.system_values()))
        inner.pack_start(b1, False, False, 0)
        b2 = Gtk.Button(label="Reset everything (delete the other profiles)", halign=Gtk.Align.START)
        b2.connect("clicked", lambda *_: self._reset_all())
        inner.pack_start(b2, False, False, 0)

    def _reset_all(self):
        d = Gtk.MessageDialog(transient_for=self.win, modal=True, message_type=Gtk.MessageType.WARNING,
                              buttons=Gtk.ButtonsType.NONE, text="Delete every other profile?")
        d.format_secondary_text("Default goes back to Handtop's settings (on trial first); "
                                "the other profiles are deleted once you keep it.")
        d.add_buttons("Cancel", Gtk.ResponseType.CANCEL, "Reset everything", Gtk.ResponseType.OK)
        d.set_default_response(Gtk.ResponseType.CANCEL)
        r = d.run()
        d.destroy()
        if r != Gtk.ResponseType.OK:
            return
        self.trial(store.system_values(), profile="default", save=True, on_keep=self._delete_others)

    def _delete_others(self):
        for n in store.profiles():
            if n != "default":
                store.delete_profile(n)
