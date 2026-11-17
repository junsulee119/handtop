"""Advanced > Combinations and Advanced > Macros (mixed into app.App with AdvancedMixin).

Combinations: "first + second" bindings, hold-modifier style (the input daemon's core.py): hold the
first button, press the second, and the combination's action runs instead of the second's; the
first button's own action then runs only when it is tapped alone, on release.

Macros: files in ~/.config/rg35xxh/controls/macros (the daemon's macros.py), shared by every profile.
Built step by step here, or recorded: arm a recording here (with or without pointer movement), tap
the button set to "Record macro" in any app to start / pause, come back and Stop to save it."""
import os

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk  # noqa: E402

from . import actions as A  # noqa: E402
from . import store  # noqa: E402

M = store.macros
STEP_TYPES = [("key", "Press a key", "Enter"), ("combo", "Key combination", "Ctrl+C"),
              ("text", "Type text", "hello"), ("wait", "Wait (seconds)", "0.5"),
              ("click", "Click", "left"), ("press", "Hold a mouse button", "left"),
              ("release", "Let go of a mouse button", "left"), ("down", "Hold a key", "Shift"),
              ("up", "Let go of a key", "Shift"), ("move", "Move the pointer by x y", "40 -10"),
              ("scroll", "Scroll by down/up across (120 = one notch)", "-120 0"),
              ("launch", "Open an app (its id)", "chromium"), ("do", "Action", "copy")]
_FRIENDLY = {n.lower(): k for k, n in A.KEYS + A.MODIFIERS}
_FRIENDLY.update(ctrl="KEY_LEFTCTRL", control="KEY_LEFTCTRL", win="KEY_LEFTMETA", esc="KEY_ESC")


def key_code(word):
    """"Enter" / "ctrl" / "KEY_ENTER" / "f5" -> evdev name."""
    w = word.strip()
    if w.upper().startswith("KEY_"):
        return w.upper()
    return _FRIENDLY.get(w.lower(), "KEY_" + w.upper().replace(" ", ""))


def step_line(kind, value):
    """The file line for a step typed in the editor (friendly key names allowed)."""
    v = value.strip()
    if kind in ("key", "down", "up"):
        v = key_code(v)
    elif kind == "combo":
        v = "+".join(key_code(k) for k in v.replace(" + ", "+").split("+"))
    return f"{kind} {v}" if kind == "text" else f"{kind} {v}".strip()


def describe_step(st):
    w = st[0]
    if w in ("key", "down", "up"):
        return {"key": "Key", "down": "Hold key", "up": "Let go of key"}[w] + " " + A.key_name(st[1])
    if w == "combo":
        return "Keys " + " + ".join(A.key_name(k) for k in st[1].split("+"))
    if w == "text":
        return f"Type “{st[1]}”"
    if w == "wait":
        return f"Wait {st[1]:g} s"
    if w in ("click", "press", "release"):
        return {"click": "Click", "press": "Hold", "release": "Let go of"}[w] + f" {st[1]} button"
    if w == "move":
        return f"Move pointer {st[1]:+d}, {st[2]:+d}"
    if w == "scroll":
        return f"Scroll {st[1]:+d}, {st[2]:+d}"
    if w == "launch":
        return f"Open {st[1]}"
    return f"{A.describe(st[1])}"


def _lab(text, dim=False, markup=False, **kw):
    lab = Gtk.Label(xalign=0, **kw)
    lab.set_line_wrap(True)
    (lab.set_markup if markup else lab.set_text)(text)
    if dim:
        lab.get_style_context().add_class("rg-dim")
    return lab


class ComboMacroMixin:
    # ---- Combinations ------------------------------------------------------------------------
    def _sec_combos(self, inner):
        inner.pack_start(_lab("Hold the first button and press the second: the combination's action runs "
                              "instead of the second button's. The first button's own action then runs only "
                              "when it is tapped alone, on release: holding it (say, dragging with A) no "
                              "longer works. Desktop mode only; off while the on-screen keyboard is open.",
                              dim=True), False, False, 0)
        self.combo_box = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
        frame = Gtk.Frame()
        frame.add(self.combo_box)
        inner.pack_start(frame, False, False, 0)
        add = Gtk.Box(spacing=6)
        self.combo_first = Gtk.ComboBoxText()
        self.combo_second = Gtk.ComboBoxText()
        for b in A.COMBO_FIRST:
            self.combo_first.append(b, A.FIRST_NAMES[b])
        for b in A.COMBO_SECOND:
            self.combo_second.append(b, A.FIRST_NAMES[b])
        self.combo_first.set_active_id("select")
        self.combo_second.set_active_id("a")
        add.pack_start(self.combo_first, False, False, 0)
        add.pack_start(Gtk.Label(label="+"), False, False, 0)
        add.pack_start(self.combo_second, False, False, 0)
        b = Gtk.Button(label="Add…")
        b.connect("clicked", lambda *_: self._combo_add())
        add.pack_start(b, False, False, 0)
        inner.pack_start(add, False, False, 0)

    def combos_refresh(self):
        if not hasattr(self, "combo_box"):
            return
        for r in self.combo_box.get_children():
            self.combo_box.remove(r)
        combos = store.combos(self.values)
        if not combos:
            self.combo_box.add(_lab("No combinations yet.", dim=True, margin=6))
        for key, act in sorted(combos.items()):
            row = Gtk.Box(spacing=6, margin=4)
            row.pack_start(_lab(f"<b>{GLib.markup_escape_text(A.button_name(key))}</b>   "
                                f"{GLib.markup_escape_text(A.describe(act, self.app_names))}", markup=True),
                           True, True, 0)
            ch = Gtk.Button(label="Change…")
            ch.connect("clicked", lambda _b, k=key: self.open_action(k, origin="advanced"))
            de = Gtk.Button(label="Delete")
            de.connect("clicked", lambda _b, k=key: self._combo_delete(k))
            locked = self.is_locked("desktop", key)
            ch.set_sensitive(not locked)
            de.set_sensitive(not locked)
            row.pack_start(ch, False, False, 0)
            row.pack_start(de, False, False, 0)
            self.combo_box.add(row)
        self.combo_box.show_all()

    def _combo_add(self):
        first, second = self.combo_first.get_active_id(), self.combo_second.get_active_id()
        if not first or not second or first == second:
            return
        own = self.values.bindings.get(first, "none")
        holds = own.startswith(("click_", "key:", "combo:"))
        first_time = not any(k.startswith(first + "+") for k in store.combos(self.values))
        if holds and first_time:                    # warn once: this button can no longer be held
            d = Gtk.MessageDialog(transient_for=self.win, modal=True, message_type=Gtk.MessageType.WARNING,
                                  buttons=Gtk.ButtonsType.NONE,
                                  text=f"{A.FIRST_NAMES[first]} becomes a combination's first button")
            d.format_secondary_text(f"{A.FIRST_NAMES[first]} ({A.describe(own, self.app_names)}) will act "
                                    "only when tapped alone, on release: it can no longer be held down.")
            d.add_buttons("Cancel", Gtk.ResponseType.CANCEL, "Continue", Gtk.ResponseType.OK)
            d.set_default_response(Gtk.ResponseType.CANCEL)
            r = d.run()
            d.destroy()
            if r != Gtk.ResponseType.OK:
                return
        self.open_action(f"{first}+{second}", origin="advanced")

    def _combo_delete(self, key):
        new = self.values.copy()
        new.bindings.pop(key, None)
        self.trial(new)

    # ---- Macros: list, record ----------------------------------------------------------------
    def _sec_macros(self, inner):
        inner.pack_start(_lab("A macro runs a list of steps when its button is pressed (choose \"Run a macro\" "
                              "for a button or a combination); pressing it again stops it. Macros belong "
                              "to every profile.", dim=True), False, False, 0)
        self.macro_list = Gtk.ListBox()
        frame = Gtk.Frame()
        frame.add(self.macro_list)
        inner.pack_start(frame, False, False, 0)
        row = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE, max_children_per_line=4, homogeneous=True)
        for text, fn in (("New", self._m_new), ("Edit", self._m_edit), ("Rename", self._m_rename),
                         ("Delete", self._m_delete)):
            b = Gtk.Button(label=text)
            b.connect("clicked", lambda _b, f=fn: f())
            row.add(b)
        inner.pack_start(row, False, False, 0)
        self.m_note = _lab("", dim=True)                 # right under the buttons it answers
        inner.pack_start(self.m_note, False, False, 0)
        inner.pack_start(_lab("<b>Record</b>", markup=True), False, False, 0)
        self.rec_key = _lab("", dim=True)
        inner.pack_start(self.rec_key, False, False, 0)
        rb = Gtk.Box(spacing=6)
        self.rec_btn = Gtk.Button(label="Record…")
        self.rec_btn.connect("clicked", lambda *_: self._m_record())
        self.rec_stop = Gtk.Button(label="Stop and save")
        self.rec_stop.connect("clicked", lambda *_: store.record_request("stop"))
        self.rec_cancel = Gtk.Button(label="Cancel")
        self.rec_cancel.connect("clicked", lambda *_: store.record_request("cancel"))
        for w in (self.rec_btn, self.rec_stop, self.rec_cancel):
            rb.pack_start(w, False, False, 0)
        inner.pack_start(rb, False, False, 0)
        self.rec_state_lab = _lab("")
        inner.pack_start(self.rec_state_lab, False, False, 0)
        GLib.timeout_add(500, self._rec_poll)


    def macros_refresh(self):
        if not hasattr(self, "macro_list"):
            return
        self.m_note.set_text("")                         # an earlier answer no longer applies

        sel = self._m_selected()
        for r in self.macro_list.get_children():
            self.macro_list.remove(r)
        names = M.names()
        if not names:
            self.macro_list.add(_lab("No macros yet.", dim=True, margin=6))
        for n in names:
            r = Gtk.ListBoxRow()
            r.name = n
            used = [A.button_name(b) for b, a in self.values.bindings.items() if a == "macro:" + n]
            r.add(_lab(n + (f"   ({', '.join(used)})" if used else ""), margin=6))
            self.macro_list.add(r)
            if n == sel:
                self.macro_list.select_row(r)
        self.macro_list.show_all()
        keys = [A.button_name(b) for b, a in self.values.bindings.items() if a == "macro_record"]
        self.rec_key.set_text(("Record button: " + ", ".join(keys) + ". ") if keys else
                              "No button is set to \"Record macro\" yet: give one that action (a combination "
                              "such as Select + Start works well), then record. ")

    def _m_selected(self):
        r = self.macro_list.get_selected_row() if hasattr(self, "macro_list") else None
        return getattr(r, "name", None) if r else None

    def _m_new(self):
        name = self._ask_name("New macro", store.free_macro_name("Macro"))
        if name and M.NAME_RE.match(name) and name not in M.names():
            M.save(name, [])
            self.macros_refresh()
            self._m_open_editor(name)
        elif name:
            self.m_note.set_text(f"Can't use the name {name!r}.")

    def _m_edit(self):
        name = self._m_selected()
        if name:
            self._m_open_editor(name)

    def _m_rename(self):
        old = self._m_selected()
        if not old:
            return
        name = self._ask_name("Rename macro", old)
        if not name or name == old:
            return
        if not M.NAME_RE.match(name) or name in M.names():
            self.m_note.set_text(f"Can't use the name {name!r}.")
            return
        boot = [A.button_name(b) for p, b in store.macro_users(old) if p == "boot file"]
        if boot:                # the app never edits the boot partition's file
            self.m_note.set_text(f"The boot partition's rg35xxh-input.conf runs {old} ({', '.join(boot)}): "
                                 "change it there first.")
            return
        try:
            os.replace(M.path(old), M.path(name))
            store.rename_macro_refs(old, name)            # every profile's buttons follow the new name
        except OSError as e:
            self.refresh()
            self.m_note.set_text(f"Could not rename: {e}.")
            return
        self.refresh()

    def _m_delete(self):
        name = self._m_selected()
        if not name:
            return
        used = [f"{A.button_name(b)} ({'Default' if p == 'default' else p})"
                for p, b in store.macro_users(name)]
        if used:
            self.m_note.set_text(f"{name} is used by {', '.join(used)}: give those another action first.")
            return
        try:
            os.unlink(M.path(name))
        except OSError:
            pass
        self.macros_refresh()

    def _m_record(self):
        d = Gtk.Dialog(title="Record a macro", transient_for=self.win, modal=True)
        d.add_buttons("Cancel", Gtk.ResponseType.CANCEL, "Get ready", Gtk.ResponseType.OK)
        d.set_default_response(Gtk.ResponseType.OK)
        area = d.get_content_area()
        e = Gtk.Entry(text=store.free_macro_name("Recording"), activates_default=True)
        cb = Gtk.CheckButton(label="Include pointer movement")
        tm = Gtk.CheckButton(label="Keep the timing between steps", active=True)
        area.pack_start(_lab("Name"), False, False, 4)
        area.pack_start(e, False, False, 4)
        area.pack_start(cb, False, False, 4)
        area.pack_start(tm, False, False, 4)
        area.pack_start(_lab("Pointer movement is saved as \"move by x, y\": playback repeats it from wherever "
                             "the pointer is, so it matches only if it starts at the same spot. Without it, "
                             "clicks land wherever the pointer is when the macro runs. Without the timing, "
                             "the steps play back to back as fast as possible.", dim=True), False, False, 4)
        area.pack_start(_lab("Then go to any app and tap the record button to start; tap it again to pause. "
                             "Come back here and choose Stop and save.", dim=True), False, False, 4)
        d.show_all()
        r = d.run()
        name, pointer, timing = e.get_text().strip(), cb.get_active(), tm.get_active()
        d.destroy()
        if r != Gtk.ResponseType.OK:
            return
        if not M.NAME_RE.match(name) or name in M.names():
            self.m_note.set_text(f"Can't use the name {name!r}.")
            return
        store.record_request("arm", name, pointer, timing)

    def _rec_poll(self):
        st = store.record_status()
        state = st.get("state")
        live = state in ("armed", "recording", "paused", "full")
        text = {"armed": "Ready: tap the record button in any app to start.",
                "recording": f"Recording… {st.get('steps', 0)} steps. Tap the record button to pause.",
                "paused": f"Paused, {st.get('steps', 0)} steps. Tap the record button to go on, or stop here.",
                "full": "Paused: the longest macro was reached. Stop and save.",
                "saved": f"Saved {st.get('name')} ({st.get('steps', 0)} steps).",
                "empty": "Nothing was recorded.", "cancelled": "Recording cancelled."}.get(state, "")
        if text != self.rec_state_lab.get_text():
            self.rec_state_lab.set_text(text)
            if state == "saved":
                self.macros_refresh()
        self.rec_btn.set_sensitive(not live)
        self.rec_stop.set_visible(live)
        self.rec_cancel.set_visible(live)
        return True

    # ---- Macro editor (its own page) ---------------------------------------------------------
    def _macro_page(self):
        box, sw = self._page("macro_title")
        self.step_list = Gtk.ListBox()
        sw.add(self.step_list)
        row = Gtk.Box(spacing=4)
        for text, fn in (("Add…", self._s_add), ("Edit…", self._s_edit), ("Up", lambda: self._s_move(-1)),
                         ("Down", lambda: self._s_move(1)), ("Delete", self._s_delete), ("Save", self._s_save)):
            b = Gtk.Button(label=text)
            b.connect("clicked", lambda _b, f=fn: f())
            row.pack_start(b, True, True, 0)
        box.pack_start(row, False, False, 0)
        self.s_note = _lab("", dim=True)
        box.pack_start(self.s_note, False, False, 0)
        return box

    def _m_open_editor(self, name):
        self.m_name = name
        try:
            self.m_steps, problems = M.load(name)
        except OSError:
            self.m_steps, problems = [], []
        self.s_note.set_text("; ".join(problems[:2]))
        self.macro_title.set_markup(f"<b>Macro</b> {GLib.markup_escape_text(name)}")
        self._s_fill()
        self.stack.set_visible_child_name("macro")

    def _s_fill(self, select=None):
        for r in self.step_list.get_children():
            self.step_list.remove(r)
        for i, st in enumerate(self.m_steps):
            r = Gtk.ListBoxRow()
            r.i = i
            r.add(_lab(f"{i + 1}.  {describe_step(st)}", margin=4))
            self.step_list.add(r)
            if i == select:
                self.step_list.select_row(r)
        if not self.m_steps:
            self.step_list.add(_lab("No steps yet: Add…", dim=True, margin=6))
        self.step_list.show_all()

    def _s_sel(self):
        r = self.step_list.get_selected_row()
        return getattr(r, "i", None) if r else None

    def _s_dialog(self, step=None):
        """Ask for one step; returns the parsed step or None."""
        d = Gtk.Dialog(title="Step", transient_for=self.win, modal=True)
        d.add_buttons("Cancel", Gtk.ResponseType.CANCEL, "OK", Gtk.ResponseType.OK)
        d.set_default_response(Gtk.ResponseType.OK)
        kind = Gtk.ComboBoxText()
        for k, text, _ex in STEP_TYPES:
            kind.append(k, text)
        val = Gtk.Entry(activates_default=True)
        hint = _lab("", dim=True)

        def changed(*_):
            ex = dict((k, e) for k, _t, e in STEP_TYPES).get(kind.get_active_id(), "")
            hint.set_text(f"For example: {ex}" + ("   (do: " + ", ".join(M.DO) + ")" if kind.get_active_id() == "do"
                                                  else ""))
        kind.connect("changed", changed)
        if step:
            kind.set_active_id(step[0])
            line = M.format_steps([step]).splitlines()[1]
            v = line.partition(" ")[2]
            val.set_text(" + ".join(A.key_name(k) for k in v.split("+")) if step[0] == "combo" else
                         A.key_name(v) if step[0] in ("key", "down", "up") else v)
        else:
            kind.set_active_id("key")
        changed()
        area = d.get_content_area()
        for w in (kind, val, hint):
            area.pack_start(w, False, False, 4)
        d.show_all()
        while True:
            r = d.run()
            if r != Gtk.ResponseType.OK:
                d.destroy()
                return None
            steps, problems = M.parse(step_line(kind.get_active_id(), val.get_text()))
            if steps:
                d.destroy()
                return steps[0]
            hint.set_text("Not understood. " + (problems[0].split(": ", 1)[-1] if problems else ""))

    def _s_add(self):
        st = self._s_dialog()
        if st:
            i = self._s_sel()
            at = len(self.m_steps) if i is None else i + 1
            self.m_steps.insert(at, st)
            self._s_fill(at)

    def _s_edit(self):
        i = self._s_sel()
        if i is not None:
            st = self._s_dialog(self.m_steps[i])
            if st:
                self.m_steps[i] = st
                self._s_fill(i)

    def _s_move(self, d):
        i = self._s_sel()
        if i is not None and 0 <= i + d < len(self.m_steps):
            self.m_steps[i], self.m_steps[i + d] = self.m_steps[i + d], self.m_steps[i]
            self._s_fill(i + d)

    def _s_delete(self):
        i = self._s_sel()
        if i is not None:
            del self.m_steps[i]
            self._s_fill(min(i, len(self.m_steps) - 1))

    def _s_save(self):
        try:
            M.save(self.m_name, self.m_steps)
        except (OSError, ValueError) as e:
            self.s_note.set_text(f"Not saved: {e}.")
            return
        self.s_note.set_text(f"Saved ({len(self.m_steps)} steps).")

        self.macros_refresh()

    # ---- "Run a macro" for a button ----------------------------------------------------------
    def _macro_pick_page(self):
        box, sw = self._page("pick_title")
        self.pick_list = Gtk.ListBox()
        self.pick_list.set_activate_on_single_click(True)
        self.pick_list.connect("row-activated", lambda _l, r: self._set_binding("macro:" + r.name))
        sw.add(self.pick_list)
        return box

    def _open_macro_pick(self):
        for r in self.pick_list.get_children():
            self.pick_list.remove(r)
        for n in M.names():
            r = Gtk.ListBoxRow()
            r.name = n
            r.add(_lab(n, margin=6))
            self.pick_list.add(r)
        if not M.names():
            self.pick_list.add(_lab("No macros yet: make one in Advanced > Macros.", dim=True, margin=6))
        self.pick_list.show_all()
        self.pick_title.set_markup(f"<b>{GLib.markup_escape_text(A.button_name(self.sel))}</b> runs a macro")
        self.stack.set_visible_child_name("macropick")
