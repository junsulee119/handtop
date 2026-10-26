"""On-screen keyboard: GTK3 layer-shell panel at the bottom of the screen.

Navigated with the D-pad (highlight) and A (type), or clicked with the pointer.
Keys are typed through the daemon's virtual keyboard (US layout keycodes).
Shift / Ctrl / Alt are one-shot: they apply to the next key, then release.

Placement: always on the handheld screen. With an HDMI monitor in "monitor only" mode the
handheld screen is off; showing the keyboard turns it on (rg35xxh-display osk on) and the
keyboard fills it as a full-screen keyboard panel; hiding it turns the screen off again.
"""
import os
import subprocess

import gi

gi.require_version("Gdk", "3.0")
gi.require_version("Gtk", "3.0")
gi.require_version("GtkLayerShell", "0.1")
from gi.repository import Gdk, GLib, Gtk, GtkLayerShell  # noqa: E402

INTERNAL_MAX_MM = 100      # the handheld panel is 70x53 mm; any monitor is larger

# (label, shifted label, key name, width in quarter keys). Every row is 15 keys = 60 quarters wide.
# Staggered like a real keyboard (each row starts a little further right), Enter and ⌫ where a real
# keyboard has them; Ctrl sits where Caps Lock is (HHKB style); ↑ is right above ↓, Esc beside it.
#   `  1 2 3 4 5 6 7 8 9 0 - =  ⌫
#   Tab q w e r t y u i o p [ ]  \
#   Ctrl a s d f g h j k l ; '  Enter
#   ⇧       z x c v b n m , . / ↑ Esc
#   Alt Hide   Space         ← ↓ →
ROWS = [
    [("`", "~", "KEY_GRAVE", 4)] + [(c, s, "KEY_" + c, 4) for c, s in zip("1234567890", "!@#$%^&*()")]
    + [("-", "_", "KEY_MINUS", 4), ("=", "+", "KEY_EQUAL", 4), ("⌫", "⌫", "KEY_BACKSPACE", 8)],
    [("Tab", "Tab", "KEY_TAB", 6)] + [(c, c.upper(), "KEY_" + c.upper(), 4) for c in "qwertyuiop"]
    + [("[", "{", "KEY_LEFTBRACE", 4), ("]", "}", "KEY_RIGHTBRACE", 4), ("\\", "|", "KEY_BACKSLASH", 6)],
    [("Ctrl", "Ctrl", "CTRL", 7)] + [(c, c.upper(), "KEY_" + c.upper(), 4) for c in "asdfghjkl"]
    + [(";", ":", "KEY_SEMICOLON", 4), ("'", '"', "KEY_APOSTROPHE", 4), ("Enter", "Enter", "KEY_ENTER", 9)],
    [("⇧", "⇧", "SHIFT", 12)] + [(c, c.upper(), "KEY_" + c.upper(), 4) for c in "zxcvbnm"]
    + [(",", "<", "KEY_COMMA", 4), (".", ">", "KEY_DOT", 4), ("/", "?", "KEY_SLASH", 4),
       ("↑", "↑", "KEY_UP", 4), ("Esc", "Esc", "KEY_ESC", 4)],
    [("Alt", "Alt", "ALT", 6), ("Hide", "Hide", "HIDE", 6), ("Space", "Space", "KEY_SPACE", 36),
     ("←", "←", "KEY_LEFT", 4), ("↓", "↓", "KEY_DOWN", 4), ("→", "→", "KEY_RIGHT", 4)],
]
assert all(sum(k[3] for k in row) == 60 for row in ROWS)
MODIFIERS = {"SHIFT": "KEY_LEFTSHIFT", "CTRL": "KEY_LEFTCTRL", "ALT": "KEY_LEFTALT"}

# Colours per Handtop theme (rg35xxh-theme writes ~/.config/rg35xxh/theme); the keyboard re-reads
# the choice each time it is shown, so a theme switch needs no daemon restart.
PALETTES = {
    "dark":  dict(bg="#141820", key="#2e3544", border="#3e4859", fg="#eef0f4",
                  spec="#1f2a3d", spec_border="#2f4266", spec_fg="#a9c4f2",
                  sel="#3d5a8a", sel_border="#8fb4ff", sel_fg="#ffffff",
                  latch="#6a4d1f", latch_sel="#8a6a2f", latch_border="#ffd28f",
                  badge="#8fb4ff", hit="#0c1018", hit_border="#5b7bb0", hit_fg="#8fb4ff"),
    "light": dict(bg="#d5dbe5", key="#ffffff", border="#b9c1ce", fg="#22262e",
                  spec="#dbe4f3", spec_border="#a3b4d2", spec_fg="#2c4a7c",
                  sel="#c9dbff", sel_border="#3d68b0", sel_fg="#1a2a4a",
                  latch="#ffe2a8", latch_sel="#ffd28f", latch_border="#8a6a2f",
                  badge="#3d68b0", hit="#9fadc4", hit_border="#3d68b0", hit_fg="#14233f"),
}
# Character keys (letters, digits, symbols, Space) are brighter; special keys (Tab, Shift, Ctrl,
# Alt, Backspace, arrows, Hide) are darker and bluer. A small corner badge names the shoulder
# button that does the same thing (from the bindings; L2 = Shift while the keyboard is open).
# A typed key goes dark ("hit": pressed in, instant, then fades back over 0.35 s) so every press is
# visible and distinct from the bright highlight;
# Shift / Ctrl / Alt instead stay amber while latched.
CSS = """
#rg-osk {{ background: {bg}; padding: 3px; }}
#rg-osk button {{ min-height: 30px; padding: 0; margin: 1px; border-radius: 5px;
                 background: {key}; border: 1px solid {border}; box-shadow: none; text-shadow: none; }}
#rg-osk button label {{ color: {fg}; text-shadow: none; font: 17px "Noto Sans"; }}
#rg-osk button.word label {{ font: 600 12px "Noto Sans"; }}
#rg-osk button.special {{ background: {spec}; border-color: {spec_border}; }}
#rg-osk button.special label {{ color: {spec_fg}; }}
#rg-osk button label.badge {{ color: {badge}; font: 600 8px "Noto Sans"; margin: 0 2px; }}
#rg-osk button.sel {{ background: {sel}; border-color: {sel_border}; }}
#rg-osk button.sel label {{ color: {sel_fg}; }}
#rg-osk button.latched {{ background: {latch}; }}
#rg-osk button.sel.latched {{ background: {latch_sel}; border-color: {latch_border}; }}
#rg-osk button.hit {{ background: {hit}; border-color: {hit_border}; }}
#rg-osk button.hit label {{ color: {hit_fg}; }}
#rg-osk button.fading {{ transition: background-color 350ms ease-out, border-color 350ms ease-out; }}
#rg-osk.panel {{ padding: 4px; }}
#rg-osk.panel button {{ border-radius: 8px; margin: 2px; min-width: 0; padding: 0; }}
#rg-osk.panel button label {{ font: 600 30px "Noto Sans"; }}
#rg-osk.panel button.word label {{ font: 600 12px "Noto Sans"; }}
#rg-osk.panel button.wide label {{ font: 600 22px "Noto Sans"; }}
#rg-osk.panel button label.badge {{ font: 600 12px "Noto Sans"; margin: 1px 4px; }}
"""
SPECIAL = {"KEY_ESC", "KEY_ENTER", "KEY_TAB", "KEY_BACKSPACE", "KEY_UP", "KEY_DOWN", "KEY_LEFT", "KEY_RIGHT",
           "SHIFT", "CTRL", "ALT", "HIDE"}
SHOULDERS = ("l1", "l2", "r1", "r2")


def _theme():
    path = os.path.join(os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config"),
                        "rg35xxh", "theme")
    try:
        with open(path) as f:
            return "light" if f.read().strip() == "light" else "dark"
    except OSError:
        return "dark"


class OnScreenKeyboard:
    def __init__(self, emit, bindings=None):
        """emit(mods: list[str], key: str) types one key with the given modifier keys held.
        bindings: the daemon's desktop bindings, for the shoulder-button badges."""
        self.emit = emit
        self.repeat_mods = []       # modifiers of the last typed key, kept for its repeats
        self._held = None           # key button pressed in while A is held
        self.latched = set()
        self.row, self.col = 2, 5   # start near the middle ('g')
        self.buttons = []           # [row][i] -> (Gtk.Button, spec, column)
        self.shown = False          # tracked here: the window may appear a moment later
        self.panel = False          # full-screen keyboard panel on the handheld (monitor-only mode)
        self._wait = None

        self.css = Gtk.CssProvider()
        self.theme = None
        self._apply_theme()
        Gtk.StyleContext.add_provider_for_screen(Gdk.Screen.get_default(), self.css,
                                                 Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        self.win = Gtk.Window()
        self.win.set_name("rg-osk")
        GtkLayerShell.init_for_window(self.win)
        GtkLayerShell.set_namespace(self.win, "rg35xxh-osk")
        # Overlay layer (as the panel mode): the app launcher (nwg-drawer -ovl) is an overlay
        # surface too, and on the top layer the keyboard stayed hidden under it.
        GtkLayerShell.set_layer(self.win, GtkLayerShell.Layer.OVERLAY)
        for edge in (GtkLayerShell.Edge.BOTTOM, GtkLayerShell.Edge.LEFT, GtkLayerShell.Edge.RIGHT):
            GtkLayerShell.set_anchor(self.win, edge, True)
        GtkLayerShell.auto_exclusive_zone_enable(self.win)   # windows shrink above it
        GtkLayerShell.set_keyboard_mode(self.win, GtkLayerShell.KeyboardMode.NONE)

        badges = {}                     # key name -> "L1" ... (what that shoulder button types)
        for btn in SHOULDERS:
            act = (bindings or {}).get(btn, "")
            if act.startswith("key:"):
                badges.setdefault(act[4:], btn.upper())
        badges["SHIFT"] = "L2"          # fixed while the keyboard is open (core.py)
        grid = Gtk.Grid(column_homogeneous=True, row_homogeneous=True)
        for r, row in enumerate(ROWS):
            col = 0
            line = []
            for spec in row:
                b = Gtk.Button()
                b.set_can_focus(False)
                over = Gtk.Overlay()
                label = Gtk.Label(label=spec[0])
                over.add(label)
                if spec[2] in badges:
                    badge = Gtk.Label(label=badges[spec[2]], halign=Gtk.Align.END,
                                      valign=Gtk.Align.START)
                    badge.get_style_context().add_class("badge")
                    over.add_overlay(badge)
                b.add(over)
                b.label = label
                ctx = b.get_style_context()
                if len(spec[0]) > 1:
                    ctx.add_class("word")       # Tab, Ctrl, Space, Hide ...
                if spec[2] in SPECIAL:
                    ctx.add_class("special")
                if spec[2] == "KEY_BACKSPACE":
                    ctx.add_class("wide")       # ⌫ is a wide glyph: smaller on the panel to fit 640 px
                b.connect("clicked", self._on_click, spec)
                grid.attach(b, col, r, spec[3], 1)
                line.append((b, spec, col))
                col += spec[3]
            self.buttons.append(line)
        self.win.add(grid)
        grid.show_all()
        self._highlight()

    def _apply_theme(self):
        theme = _theme()
        if theme != self.theme:
            self.theme = theme
            self.css.load_from_data(CSS.format(**PALETTES[theme]).encode())

    # ------------------------------------------------------------- visibility
    @property
    def visible(self):
        return self.shown

    def toggle(self):
        if self.shown:
            self.hide()
        else:
            self.show()

    def show(self):
        self.shown = True
        self._apply_theme()
        self.panel = _display_status() == "monitor docked"
        if self.panel:
            subprocess.run(["rg35xxh-display", "osk", "on"], check=False, timeout=5)
        tries = [0]

        def place():
            mon = _internal_monitor()
            if mon is None and self.panel and tries[0] < 30:   # panel output still coming up
                tries[0] += 1
                return True
            self._wait = None
            if not self.shown:
                return False
            self.win.hide()   # layer-shell properties apply on (re)map
            ctx = self.win.get_style_context()
            (ctx.add_class if self.panel else ctx.remove_class)("panel")
            GtkLayerShell.set_monitor(self.win, mon)
            GtkLayerShell.set_layer(self.win, GtkLayerShell.Layer.OVERLAY)
            GtkLayerShell.set_anchor(self.win, GtkLayerShell.Edge.TOP, self.panel)
            if self.panel:
                GtkLayerShell.set_exclusive_zone(self.win, -1)   # cover the whole panel
            else:
                GtkLayerShell.auto_exclusive_zone_enable(self.win)
            self.win.show()
            return False

        if self._wait:
            GLib.source_remove(self._wait)
        self._wait = GLib.timeout_add(50, place)

    def hide(self):
        self.shown = False
        self._held = None
        for line in self.buttons:               # no key left pressed in for the next show
            for b, _, _ in line:
                if getattr(b, "fade_timer", None):
                    GLib.source_remove(b.fade_timer)
                    b.fade_timer = None
                b.get_style_context().remove_class("hit")
                b.get_style_context().remove_class("fading")
        self.win.hide()
        if self.panel:
            self.panel = False
            subprocess.Popen(["rg35xxh-display", "osk", "off"], stdin=subprocess.DEVNULL,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # ------------------------------------------------------------- navigation
    def move(self, dx, dy):
        if dy:
            # keep the horizontal position: pick the key whose centre is closest
            _, spec, col = self.buttons[self.row][self.col]
            centre = col + spec[3] / 2.0
            self.row = (self.row + dy) % len(self.buttons)
            self.col = min(range(len(self.buttons[self.row])),
                           key=lambda i: abs(self.buttons[self.row][i][2]
                                             + self.buttons[self.row][i][1][3] / 2.0 - centre))
        if dx:
            self.col = (self.col + dx) % len(self.buttons[self.row])
        self._highlight()

    def press_selected(self):
        b, spec, _ = self.buttons[self.row][self.col]
        self._held = b if spec[2] != "HIDE" and spec[2] not in MODIFIERS else None
        self._activate(spec, b, hold=True)

    def release_selected(self):
        # keys are typed as complete taps on press; this only lets the key come back up
        if self._held is not None:
            self._release(self._held, 0)
            self._held = None

    def repeat_selected(self):
        """A held: type the highlighted key again (not Shift / Ctrl / Alt / Hide)."""
        key = self.buttons[self.row][self.col][1][2]
        if key != "HIDE" and key not in MODIFIERS:
            self.emit(self.repeat_mods, key)   # the key stays pressed in while A is held

    def toggle_shift(self):
        """L2 while the keyboard is open: same as pressing the Shift key."""
        self.latched ^= {"SHIFT"}
        self._relabel()
        self._highlight()

    # ---------------------------------------------------------------- typing
    def _on_click(self, button, spec):
        self._activate(spec, button)

    def key_state(self, key, down):
        """A shoulder button typed `key` (e.g. KEY_ESC): the key stays pressed in while the button
        is held and fades back on release, like a real key."""
        for line in self.buttons:
            for b, spec, _ in line:
                if spec[2] == key:
                    if down:
                        self._press_in(b)
                    else:
                        self._release(b, 0)
                    return

    def _press_in(self, button):
        ctx = button.get_style_context()
        if getattr(button, "fade_timer", None):
            GLib.source_remove(button.fade_timer)
            button.fade_timer = None
        ctx.remove_class("fading")
        ctx.add_class("hit")

    def _flash(self, button):
        """Press trace: the key goes dark at once, then fades back (CSS transition)."""
        self._press_in(button)
        self._release(button, 90)

    def _release(self, button, delay):
        ctx = button.get_style_context()

        def fade():
            ctx.add_class("fading")          # transition applies while going back to normal
            ctx.remove_class("hit")

            def done():
                ctx.remove_class("fading")   # no transition for the moving highlight
                button.fade_timer = None
                return False
            button.fade_timer = GLib.timeout_add(400, done)
            return False
        if delay:
            button.fade_timer = GLib.timeout_add(delay, fade)
        else:
            fade()

    def _activate(self, spec, button=None, hold=False):
        key = spec[2]
        if key == "HIDE":
            self.hide()
            return
        if key in MODIFIERS:
            self.latched ^= {key}
        else:
            mods = [MODIFIERS[m] for m in sorted(self.latched)]
            self.repeat_mods = mods
            self.emit(mods, key)
            if button is not None:
                (self._press_in if hold else self._flash)(button)
            self.latched.clear()
        self._relabel()
        self._highlight()

    def _relabel(self):
        shifted = "SHIFT" in self.latched
        for line in self.buttons:
            for b, spec, _ in line:
                b.label.set_label(spec[1] if shifted else spec[0])

    def _highlight(self):
        for r, line in enumerate(self.buttons):
            for i, (b, spec, _) in enumerate(line):
                ctx = b.get_style_context()
                (ctx.add_class if (r, i) == (self.row, self.col) else ctx.remove_class)("sel")
                (ctx.add_class if spec[2] in self.latched else ctx.remove_class)("latched")


def _internal_monitor():
    disp = Gdk.Display.get_default()
    for i in range(disp.get_n_monitors()):
        m = disp.get_monitor(i)
        if 0 < m.get_width_mm() < INTERNAL_MAX_MM:
            return m
    return None


def _display_status():
    try:
        return subprocess.run(["rg35xxh-display", "status"], capture_output=True, text=True,
                              timeout=5).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""
