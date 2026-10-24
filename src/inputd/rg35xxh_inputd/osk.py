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

# (label, shifted label, key name, column span)
ROWS = [
    [("`", "~", "KEY_GRAVE", 1)] + [(c, s, "KEY_" + c, 1) for c, s in zip("1234567890", "!@#$%^&*()")]
    + [("⌫", "⌫", "KEY_BACKSPACE", 1)],
    [("Tab", "Tab", "KEY_TAB", 1)] + [(c, c.upper(), "KEY_" + c.upper(), 1) for c in "qwertyuiop"]
    + [("-", "_", "KEY_MINUS", 1)],
    [(c, c.upper(), "KEY_" + c.upper(), 1) for c in "asdfghjkl"]
    + [(";", ":", "KEY_SEMICOLON", 1), ("'", '"', "KEY_APOSTROPHE", 1), ("\\", "|", "KEY_BACKSLASH", 1)],
    [("⇧", "⇧", "SHIFT", 1)] + [(c, c.upper(), "KEY_" + c.upper(), 1) for c in "zxcvbnm"]
    + [(",", "<", "KEY_COMMA", 1), (".", ">", "KEY_DOT", 1), ("/", "?", "KEY_SLASH", 1), ("↑", "↑", "KEY_UP", 1)],
    [("Ctrl", "Ctrl", "CTRL", 1), ("Alt", "Alt", "ALT", 1), ("Space", "Space", "KEY_SPACE", 3),
     ("=", "+", "KEY_EQUAL", 1), ("[", "{", "KEY_LEFTBRACE", 1), ("]", "}", "KEY_RIGHTBRACE", 1),
     ("←", "←", "KEY_LEFT", 1), ("↓", "↓", "KEY_DOWN", 1), ("→", "→", "KEY_RIGHT", 1),
     ("Hide", "Hide", "HIDE", 1)],
]
MODIFIERS = {"SHIFT": "KEY_LEFTSHIFT", "CTRL": "KEY_LEFTCTRL", "ALT": "KEY_LEFTALT"}

# Colours per Handtop theme (rg35xxh-theme writes ~/.config/rg35xxh/theme); the keyboard re-reads
# the choice each time it is shown, so a theme switch needs no daemon restart.
PALETTES = {
    "dark":  dict(bg="#141820", key="#2b3240", border="#3a4456", fg="#e8eaee",
                  sel="#3d5a8a", sel_border="#8fb4ff", sel_fg="#e8eaee",
                  latch="#6a4d1f", latch_sel="#8a6a2f", latch_border="#ffd28f"),
    "light": dict(bg="#d5dbe5", key="#f8f9fb", border="#b9c1ce", fg="#2b303b",
                  sel="#c9dbff", sel_border="#3d68b0", sel_fg="#1a2a4a",
                  latch="#ffe2a8", latch_sel="#ffd28f", latch_border="#8a6a2f"),
}
CSS = """
#rg-osk {{ background: {bg}; padding: 3px; }}
#rg-osk button {{ min-height: 30px; padding: 0; margin: 1px; border-radius: 5px;
                 background: {key}; color: {fg}; border: 1px solid {border};
                 font: 13px "Noto Sans"; box-shadow: none; text-shadow: none; }}
#rg-osk button label {{ color: {fg}; text-shadow: none; }}
#rg-osk button.sel {{ background: {sel}; border-color: {sel_border}; }}
#rg-osk button.sel label {{ color: {sel_fg}; }}
#rg-osk button.latched {{ background: {latch}; }}
#rg-osk button.sel.latched {{ background: {latch_sel}; border-color: {latch_border}; }}
#rg-osk.panel {{ padding: 4px; }}
#rg-osk.panel button {{ font: 600 24px "Noto Sans"; border-radius: 8px; margin: 2px;
                       min-width: 0; padding: 0; }}
#rg-osk.panel button.word {{ font: 600 14px "Noto Sans"; }}
"""


def _theme():
    path = os.path.join(os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config"),
                        "rg35xxh", "theme")
    try:
        with open(path) as f:
            return "light" if f.read().strip() == "light" else "dark"
    except OSError:
        return "dark"


class OnScreenKeyboard:
    def __init__(self, emit):
        """emit(mods: list[str], key: str) types one key with the given modifier keys held."""
        self.emit = emit
        self.latched = set()
        self.row, self.col = 2, 4   # start near the middle ('g')
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
        GtkLayerShell.set_layer(self.win, GtkLayerShell.Layer.TOP)
        for edge in (GtkLayerShell.Edge.BOTTOM, GtkLayerShell.Edge.LEFT, GtkLayerShell.Edge.RIGHT):
            GtkLayerShell.set_anchor(self.win, edge, True)
        GtkLayerShell.auto_exclusive_zone_enable(self.win)   # windows shrink above it
        GtkLayerShell.set_keyboard_mode(self.win, GtkLayerShell.KeyboardMode.NONE)

        grid = Gtk.Grid(column_homogeneous=True, row_homogeneous=True)
        for r, row in enumerate(ROWS):
            col = 0
            line = []
            for spec in row:
                b = Gtk.Button(label=spec[0])
                b.set_can_focus(False)
                if len(spec[0]) > 1:
                    b.get_style_context().add_class("word")   # Tab, Ctrl, Space, Hide ...
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
            GtkLayerShell.set_layer(self.win, GtkLayerShell.Layer.OVERLAY if self.panel
                                    else GtkLayerShell.Layer.TOP)
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
        self._activate(self.buttons[self.row][self.col][1])

    def release_selected(self):
        pass  # keys are typed as complete taps on press

    # ---------------------------------------------------------------- typing
    def _on_click(self, _button, spec):
        self._activate(spec)

    def _activate(self, spec):
        key = spec[2]
        if key == "HIDE":
            self.hide()
            return
        if key in MODIFIERS:
            self.latched ^= {key}
        else:
            mods = [MODIFIERS[m] for m in sorted(self.latched)]
            self.emit(mods, key)
            self.latched.clear()
        self._relabel()
        self._highlight()

    def _relabel(self):
        shifted = "SHIFT" in self.latched
        for line in self.buttons:
            for b, spec, _ in line:
                b.set_label(spec[1] if shifted else spec[0])

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
