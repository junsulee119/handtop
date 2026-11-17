"""Config file loading.

Settings come in layers; per key, the last layer that sets it wins (docs/services/input-daemon.md,
"Settings layers"):
  1. built-in defaults (core.py)
  2. /etc/rg35xxh/input.conf                  system
  3. ~/.config/rg35xxh/controls/<profile>.conf the active profile (Controls app); <profile> is named
                                               in ~/.config/rg35xxh/controls/active, "default" if none
  4. $XDG_RUNTIME_DIR/rg35xxh-controls-trial.conf
                                               a change on trial ("Keep these controls?"): the whole
                                               candidate profile, so while it runs it REPLACES layer 3
                                               (a combination it leaves out is gone, not inherited);
                                               ignored once its [trial] expires time (trial_clock())
                                               has passed
  5. /boot/firmware/rg35xxh-input.conf         FAT boot partition, editable from Windows: wins, so it
                                               always rescues a broken profile. Images ship it with
                                               every setting commented out (boot_template()), so it
                                               locks nothing until a line is uncommented; its
                                               [rescue] use_app_settings = no drops layers 3 and 4
load() is the older single-file reader (first existing file wins), kept for the tests.
"""
import configparser
import logging
import math
import os
import re
import time

from .core import DEFAULT_BINDINGS, DEFAULT_SETTINGS

SYSTEM = "/etc/rg35xxh/input.conf"
BOOT = "/boot/firmware/rg35xxh-input.conf"
PATHS = (BOOT, SYSTEM)
TRIAL_NAME = "rg35xxh-controls-trial.conf"
DEFAULT_PROFILE = "default"
PROFILE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 _.-]{0,39}$")
BUTTON_NAMES = tuple(DEFAULT_BINDINGS)
HARDWARE_KEYS = ("invert_lx", "invert_ly", "invert_rx", "invert_ry")
_ACTION_RE = re.compile(r"^(none|click_(left|right|middle|back|forward)|key:KEY_[A-Z0-9_]+"
                        r"|combo:KEY_[A-Z0-9_]+(\+KEY_[A-Z0-9_]+){1,3}|launch:[A-Za-z0-9][A-Za-z0-9._-]{0,99}"
                        r"|copy|paste|osk_toggle|mode_gamepad|power_menu|pointer"
                        r"|volume_up|volume_down|brightness_up|brightness_down"
                        r"|macro:[A-Za-z0-9][A-Za-z0-9 _.-]{0,39}|macro_record)$")
DPAD_NAMES = ("up", "down", "left", "right")
# Combinations: the first button is held like a modifier (face, shoulder, stick press, Select,
# Start, F), the second is any button but Power and Volume (F + Volume stays brightness).
COMBO_FIRST = ("a", "b", "x", "y", "l1", "r1", "l2", "r2", "l3", "r3", "select", "start", "f")
COMBO_SECOND = COMBO_FIRST[:-1] + DPAD_NAMES
BOOL_SETTINGS = ("natural_scroll", "swap_sticks")
CHOICE_SETTINGS = {"pad_layout": ("position", "label")}

log = logging.getLogger("rg35xxh-inputd")

# Accepted range per setting (inclusive). A value outside it, or not a finite number, is
# ignored with a warning and the default stays: one typo on the FAT partition must not take
# the daemon, and with it every button, down (deadzone=1 divided by zero, pointer_max_speed=inf
# became NaN; codebase audit 2026-10-30, M04).
SETTING_RANGES = {
    "deadzone": (0.0, 0.9),
    "pointer_max_speed": (1.0, 5000.0),
    "pointer_curve": (0.5, 5.0),
    "dpad_speed_ratio": (0.0, 5.0),
    "scroll_speed": (0.0, 100.0),
    "scroll_log_k": (0.0, 100.0),
    "power_hold_seconds": (1.0, 10.0),
    "power_tap_max_seconds": (0.1, 5.0),
    "start_hold_seconds": (0.2, 10.0),
    "haptic_strength": (0.0, 1.0),
    "display_speed_scale": (0.0, 2.0),
    "osk_repeat_delay": (0.05, 5.0),
    "osk_repeat_interval": (0.02, 2.0),
    "osk_key_repeat_delay": (0.05, 5.0),
    "osk_key_repeat_interval": (0.02, 2.0),
    "vol_repeat_delay": (0.05, 5.0),
    "vol_repeat_interval": (0.02, 2.0),
}


TRIAL_MAX_SECONDS = 600     # a trial claiming to run longer than this is treated as ended


def trial_clock():
    """Seconds since boot, counting suspend (CLOCK_BOOTTIME): the trial's clock. Setting the wall
    clock (NTP after Wi-Fi comes up) can't stretch or cut a 15 s trial, and a trial running when
    the handheld goes to sleep has ended when it wakes. The trial file lives in $XDG_RUNTIME_DIR,
    which doesn't survive a reboot, so a time from another boot never meets this clock."""
    return time.clock_gettime(time.CLOCK_BOOTTIME)


def _known_key(name):
    """True if evdev knows the key code. Without python-evdev (the unit tests) only the
    pattern is checked."""
    try:
        from evdev import ecodes
    except ImportError:
        return True
    return isinstance(ecodes.ecodes.get(name), int)


def _unknown_keys(action):
    """The key names of a key: / combo: action that evdev doesn't know (empty for other actions)."""
    if action.startswith("key:"):
        names = [action[4:]]
    elif action.startswith("combo:"):
        names = action[6:].split("+")
    else:
        return []
    return [k for k in names if not _known_key(k)]


# Smallest set of controls that still lets you reach the Controls app and undo a change. The
# Controls app warns before a change that breaks one of them (then the usual 15 s "Keep these
# controls?" countdown follows).
MIN_POINTER_SPEED = 60.0       # px/s: slower than this, by stick or D-pad, counts as no pointer
MAX_USABLE_DEADZONE = 0.6      # beyond this the stick hardly moves the pointer


def minimal_problems(settings=None, bindings=None):
    """What a configuration takes away of the minimal controls: a list of short sentences, empty
    when the pointer still moves (stick, or the D-pad with all four directions on the pointer) and
    some button still gives a left click."""
    s = dict(DEFAULT_SETTINGS)
    s.update(settings or {})
    b = dict(DEFAULT_BINDINGS)
    b.update(bindings or {})
    out = []
    stick = s["deadzone"] <= MAX_USABLE_DEADZONE and s["pointer_max_speed"] >= MIN_POINTER_SPEED
    dpad = (s["dpad_speed_ratio"] * s["pointer_max_speed"] >= MIN_POINTER_SPEED
            and all(b[d] == "pointer" for d in DPAD_NAMES))
    if not (stick or dpad):
        out.append("The pointer would hardly move, with the stick or the D-pad.")
    if "click_left" not in b.values():
        out.append("No button would give a left click.")
    return out


# ------------------------------------------------------------------- paths
def controls_dir():
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.join(os.path.expanduser("~"), ".config")
    return os.path.join(base, "rg35xxh", "controls")


def active_file():
    return os.path.join(controls_dir(), "active")


def trial_path():
    return os.path.join(os.environ.get("XDG_RUNTIME_DIR", "/tmp"), TRIAL_NAME)


def active_profile():
    """Name of the active profile: the first line of controls/active, if it is a valid name.
    Anything else (unreadable, not UTF-8, too long) means "default": a broken pointer file must
    never stop the daemon, nor the boot file's rescue switch from being read."""
    try:
        with open(active_file(), "rb") as f:
            raw = f.read(256)
        name = raw.decode("utf-8-sig").splitlines()[0].strip() if raw.strip() else ""
    except OSError:
        return DEFAULT_PROFILE
    except (UnicodeDecodeError, IndexError):
        log.warning("%s: not a UTF-8 profile name (using %r)", active_file(), DEFAULT_PROFILE)
        return DEFAULT_PROFILE
    if not PROFILE_RE.match(name):
        log.warning("%s: not a profile name: %r (using %r)", active_file(), name, DEFAULT_PROFILE)
        return DEFAULT_PROFILE
    return name


def profile_path(name):
    return os.path.join(controls_dir(), name + ".conf")


def layer_paths():
    """(kind, path) from lowest to highest priority."""
    return [("system", SYSTEM), ("profile", profile_path(active_profile())),
            ("trial", trial_path()), ("boot", BOOT)]


def stamp():
    """Cheap change detector for the daemon's housekeeping: (path, inode, mtime_ns, size) of every
    layer file and the active-profile pointer (the inode catches an atomic replace within one
    timestamp tick); None for a missing file."""
    out = []
    for p in [active_file()] + [p for _, p in layer_paths()]:
        try:
            st = os.stat(p)
            out.append((p, st.st_ino, st.st_mtime_ns, st.st_size))
        except OSError:
            out.append((p, None, None, None))
    return tuple(out)


# ----------------------------------------------------------------- parsing
def _read(path):
    """ConfigParser for path, or None if the file is missing or unreadable."""
    # interpolation=None: a "%" in a value (haptic_strength = 50%) is an ordinary bad value, not
    # an InterpolationSyntaxError escaping from cp.items() later
    cp = configparser.ConfigParser(inline_comment_prefixes=("#", ";"), interpolation=None)
    try:
        with open(path, encoding="utf-8-sig") as f:   # tolerate a BOM from Windows editors
            cp.read_file(f)
    except FileNotFoundError:
        return None
    except (OSError, configparser.Error, UnicodeDecodeError) as e:
        log.warning("cannot read %s: %s", path, e)
        return None
    return cp


def parse(cp, label="config"):
    """The valid values of one file: (settings, bindings, hardware), each holding only the keys the
    file sets. Bad values are logged and left out, so a lower layer's value (or the default) stays."""
    settings, bindings, hardware = {}, {}, {}
    if cp.has_section("settings"):
        for k, v in cp.items("settings"):
            if k in BOOL_SETTINGS:
                try:
                    settings[k] = cp.getboolean("settings", k)
                except ValueError:
                    log.warning("%s: settings.%s: not yes/no: %r (ignored)", label, k, v)
            elif k in CHOICE_SETTINGS:
                v = v.strip().lower()
                if v in CHOICE_SETTINGS[k]:
                    settings[k] = v
                else:
                    log.warning("%s: settings.%s: %r is not one of %s (ignored)", label, k, v,
                                ", ".join(CHOICE_SETTINGS[k]))
            elif k in DEFAULT_SETTINGS:
                lo, hi = SETTING_RANGES.get(k, (-math.inf, math.inf))
                try:
                    x = float(v)
                except ValueError:
                    log.warning("%s: settings.%s: not a number: %r (ignored)", label, k, v)
                    continue
                if not math.isfinite(x) or not lo <= x <= hi:
                    log.warning("%s: settings.%s: %r outside %s..%s (ignored)", label, k, v, lo, hi)
                    continue
                settings[k] = x
            else:
                log.warning("%s: settings.%s: unknown setting", label, k)
    if cp.has_section("desktop"):
        for k, v in cp.items("desktop"):
            v = v.strip()
            if "+" in k:                                  # a combination: first+second
                first, _, second = k.partition("+")
                if first not in COMBO_FIRST or second not in COMBO_SECOND or first == second:
                    log.warning("%s: desktop.%s: not a combination of two buttons (ignored)", label, k)
                elif not _ACTION_RE.match(v) or v == "pointer":
                    log.warning("%s: desktop.%s: unknown action %r", label, k, v)
                elif _unknown_keys(v):
                    log.warning("%s: desktop.%s: unknown key in %r (ignored)", label, k, v)
                else:
                    bindings[k] = v
            elif k not in BUTTON_NAMES:
                log.warning("%s: desktop.%s: unknown button (valid: %s)", label, k, ", ".join(BUTTON_NAMES))
            elif not _ACTION_RE.match(v):
                log.warning("%s: desktop.%s: unknown action %r", label, k, v)
            elif _unknown_keys(v):
                log.warning("%s: desktop.%s: unknown key in %r (ignored)", label, k, v)
            elif v == "pointer" and k not in DPAD_NAMES:
                log.warning("%s: desktop.%s: pointer is for the D-pad directions only (ignored)", label, k)
            else:
                bindings[k] = v
    if cp.has_section("hardware"):
        for k in HARDWARE_KEYS:
            if cp.has_option("hardware", k):
                try:
                    hardware[k] = cp.getboolean("hardware", k)
                except ValueError:      # fallback= only covers a missing option, not a bad value
                    log.warning("%s: hardware.%s: not yes/no: %r (ignored)", label, k, cp.get("hardware", k))
    return settings, bindings, hardware


def trial_expires(cp):
    """trial_clock() time the trial ends, or None if the file has no valid [trial] expires."""
    try:
        x = float(cp.get("trial", "expires"))
    except (configparser.Error, ValueError):
        return None
    return x if math.isfinite(x) else None


def load(paths=PATHS):
    """Older single-file reader: the first existing file wins."""
    hardware = {k: False for k in HARDWARE_KEYS}
    for p in paths:
        cp = _read(p)
        if cp is not None:
            log.info("config: %s", p)
            s, b, h = parse(cp, p)
            hardware.update(h)
            return s, b, hardware, p
    return {}, {}, hardware, None


def app_settings_allowed(cp):
    """False when the boot file says [rescue] use_app_settings = no."""
    try:
        return cp.getboolean("rescue", "use_app_settings", fallback=True)
    except ValueError:
        log.warning("%s: rescue.use_app_settings: not yes/no: %r (ignored)", BOOT,
                    cp.get("rescue", "use_app_settings"))
        return True


def boot_template(system_text):
    """The boot partition's rg35xxh-input.conf for a new image, from /etc/rg35xxh/input.conf:
    the same settings, every one commented out (so nothing is locked in the Controls app), under
    a header that explains the rescue. Section names stay active, so uncommenting one line is
    enough. Line endings are the caller's business (the image writes CRLF)."""
    lines = system_text.splitlines()
    while lines and (lines[0].startswith("#") or not lines[0].strip()):
        lines.pop(0)                                   # the system file's own header
    body = [re.sub(r"^([a-z][a-z0-9_]*\s*=)", r"# \1", ln) for ln in lines]
    head = [
        "# Handtop controls: rescue file (boot partition, editable from Windows).",
        "# Change controls with Apps > Controls; this file normally stays all commented out.",
        "# A line here without # in front WINS over the Controls app (it shows it as locked).",
        "# Every line holds the default value. Changes apply within a second, or at the next boot.",
        "#",
        "# Controls broken? Remove the # in front of use_app_settings below: everything the",
        "# Controls app saved is ignored (not deleted) until you put the # back.",
        "",
        "[rescue]",
        "# use_app_settings = no",
        "",
    ]
    return "\n".join(head + body) + "\n"


class Layered:
    """Result of load_layers(): merged values plus where they came from."""
    def __init__(self):
        self.settings, self.bindings = {}, {}
        self.hardware = {k: False for k in HARDWARE_KEYS}
        self.files = []              # (kind, path) of the layers that were read
        self.locked = set()          # "settings.x" / "desktop.a" / "hardware.invert_lx" set by the boot file
        self.trial_expired = False   # a trial file was there but its time has passed (or it has none)
        self.trial_until = None      # trial_clock() time the trial in use ends
        self.app_settings = True     # False: the boot file's [rescue] switch is on


def load_layers(layers=None, now=None):
    now = trial_clock() if now is None else now
    out = Layered()
    layers = layer_paths() if layers is None else layers
    files = {path: _read(path) for _, path in layers}
    boot = next((files[p] for k, p in layers if k == "boot" and files[p] is not None), None)
    if boot is not None and not app_settings_allowed(boot):
        out.app_settings = False
        log.info("config: rescue.use_app_settings = no in the boot file: Controls app settings ignored")
    trial = next((files[p] for k, p in layers if k == "trial" and files[p] is not None), None)
    if trial is not None and out.app_settings:
        exp = trial_expires(trial)
        if exp is None or now >= exp or exp - now > TRIAL_MAX_SECONDS:
            out.trial_expired = True
        else:
            out.trial_until = exp
    for kind, path in layers:
        cp = files[path]
        if cp is None or (kind in ("profile", "trial") and not out.app_settings):
            continue
        if kind == "trial" and out.trial_until is None:
            continue
        if kind == "profile" and out.trial_until is not None:
            continue            # the trial holds the whole candidate profile and replaces this one

        s, b, h = parse(cp, path)
        out.settings.update(s)
        out.bindings.update(b)
        out.hardware.update(h)
        out.files.append((kind, path))
        if kind == "boot":
            out.locked = ({"settings." + k for k in s} | {"desktop." + k for k in b}
                          | {"hardware." + k for k in h})
    # "first+second = none" removes a combination a lower layer set (a profile can only list what
    # differs from the system layer)
    out.bindings = {k: v for k, v in out.bindings.items() if not ("+" in k and v == "none")}
    log.info("config: %s", ", ".join(f"{k} {p}" for k, p in out.files) or "built-in defaults")

    return out
