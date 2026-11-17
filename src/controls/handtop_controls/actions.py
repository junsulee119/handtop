"""What a button can do, in words (no GTK: unit-tested). Values are the input daemon's actions
(docs/services/input-daemon.md)."""
import configparser
import os

SIMPLE = [
    ("click_left", "Left click"), ("click_right", "Right click"), ("click_middle", "Middle click"),
    ("click_back", "Back (mouse)"), ("click_forward", "Forward (mouse)"),
    ("copy", "Copy"), ("paste", "Paste"), ("osk_toggle", "On-screen keyboard"),
    ("mode_gamepad", "Gamepad mode"), ("power_menu", "Power menu"), ("none", "Nothing"),
]
# Keys offered for "A key" and the last key of a combination (evdev names).
KEYS = [("KEY_ESC", "Esc"), ("KEY_ENTER", "Enter"), ("KEY_BACKSPACE", "Backspace"), ("KEY_TAB", "Tab"),
        ("KEY_SPACE", "Space"), ("KEY_DELETE", "Delete"), ("KEY_UP", "Up"), ("KEY_DOWN", "Down"),
        ("KEY_LEFT", "Left"), ("KEY_RIGHT", "Right"), ("KEY_PAGEUP", "Page Up"), ("KEY_PAGEDOWN", "Page Down"),
        ("KEY_HOME", "Home"), ("KEY_END", "End"), ("KEY_LEFTMETA", "Super")] \
    + [(f"KEY_F{i}", f"F{i}") for i in range(1, 13)] \
    + [(f"KEY_{c}", c) for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ"] + [(f"KEY_{d}", d) for d in "0123456789"]
MODIFIERS = [("KEY_LEFTCTRL", "Ctrl"), ("KEY_LEFTALT", "Alt"), ("KEY_LEFTSHIFT", "Shift"), ("KEY_LEFTMETA", "Super")]
_NAMES = dict(SIMPLE)
_KEYS = dict(KEYS + MODIFIERS)
APP_DIRS = [os.path.join(os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share"), "applications"),
            "/usr/local/share/applications", "/usr/share/applications"]
# Buttons in the order the Buttons tab cycles through, with their names on screen.
BUTTONS = [("a", "A"), ("b", "B"), ("x", "X"), ("y", "Y"), ("l1", "L1"), ("l2", "L2"), ("r1", "R1"),
           ("r2", "R2"), ("l3", "L3 (press left stick)"), ("r3", "R3 (press right stick)"),
           ("select", "Select"), ("start", "Start")]
# Advanced: what used to be fixed (desktop mode only), with the warning shown before a change.
MORE_BUTTONS = [("up", "D-pad up"), ("down", "D-pad down"), ("left", "D-pad left"), ("right", "D-pad right"),
                ("vol_up", "Volume +"), ("vol_down", "Volume -"), ("f", "F (tap)"), ("power", "Power (tap)")]
BUTTON_NAMES = dict(BUTTONS + MORE_BUTTONS)
LEVELS = [("volume_up", "Volume up"), ("volume_down", "Volume down"),
          ("brightness_up", "Brightness up"), ("brightness_down", "Brightness down")]
_NAMES.update(LEVELS)
_NAMES["pointer"] = "Move the pointer"
WARN = {
    "dpad": "The D-pad is the pointer's backup when a stick drifts. While the on-screen keyboard "
            "is open it still moves between keys, and in gamepad mode it stays the D-pad.",
    "vol": "Volume + / - change the sound. F + Volume stays brightness, and gamepad mode keeps "
           "the volume keys as they are.",
    "f": "F is also the brightness key with Volume. Only a tap of F alone is changed here.",
    "power": "A tap of Power opens the power menu (sleep, restart, shut down). The taskbar's power "
             "button still opens it. Holding Power to shut down can't be changed.",
}


def extras(button):
    """Actions offered only for some buttons, shown before the common list."""
    if button in ("up", "down", "left", "right"):
        return [("pointer", "Move the pointer")]
    if button in ("vol_up", "vol_down", "f", "power"):
        return LEVELS
    return []


def warning(button):
    if button in ("up", "down", "left", "right"):
        return WARN["dpad"]
    return WARN.get({"vol_up": "vol", "vol_down": "vol"}.get(button, button))


def key_name(k):
    return _KEYS.get(k, k[4:].replace("_", " ").title() if k.startswith("KEY_") else k)


def apps():
    """Visible apps: [(desktop id, name)], first .desktop file per id wins (as the daemon's launch)."""
    return [(i, n) for i, n, _ in _entries()]


def window_ids():
    """Visible apps for auto-switch links: [(app id their windows most likely report, name)]. That
    is StartupWMClass when the file sets one, else the desktop id (the daemon compares without
    case, so "thunar" matches Thunar's "Thunar" window)."""
    return [(w or i, n) for i, n, w in _entries()]


def _entries():
    seen = {}
    for d in APP_DIRS:
        try:
            files = sorted(os.listdir(d))
        except OSError:
            continue
        for f in files:
            if not f.endswith(".desktop") or f[:-8] in seen:
                continue
            cp = configparser.ConfigParser(interpolation=None, strict=False)
            try:
                cp.read(os.path.join(d, f), encoding="utf-8")
                e = cp["Desktop Entry"]
            except (configparser.Error, KeyError, UnicodeDecodeError):
                continue
            seen[f[:-8]] = None if e.get("NoDisplay", "").lower() == "true" or e.get("Type") != "Application" \
                else (e.get("Name", f[:-8]), e.get("StartupWMClass", "").strip() or None)
    return sorted(((i, v[0], v[1]) for i, v in seen.items() if v), key=lambda x: x[1].lower())


def button_name(b):
    """"l1+a" -> "L1 + A"; a single button -> its name."""
    if "+" in b:
        first, second = b.split("+", 1)
        return BUTTON_NAMES.get(first, first).split(" (")[0] + " + " + BUTTON_NAMES.get(second, second).split(" (")[0]
    return BUTTON_NAMES.get(b, b)


COMBO_FIRST = ["a", "b", "x", "y", "l1", "r1", "l2", "r2", "l3", "r3", "select", "start", "f"]
COMBO_SECOND = COMBO_FIRST[:-1] + ["up", "down", "left", "right"]
FIRST_NAMES = dict(BUTTONS, f="F", up="D-pad up", down="D-pad down", left="D-pad left", right="D-pad right")


def describe(action, app_names=None):
    if action.startswith("macro:"):
        return "Macro: " + action[6:]
    if action == "macro_record":
        return "Record macro (start / pause)"
    if action in _NAMES:
        return _NAMES[action]
    if action.startswith("key:"):
        return "Key: " + key_name(action[4:])
    if action.startswith("combo:"):
        return " + ".join(key_name(k) for k in action[6:].split("+"))
    if action.startswith("launch:"):
        app = action[7:]
        return "Open " + ((app_names or {}).get(app) or app)
    return action
