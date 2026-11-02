"""Config file loading. First existing file wins:
   /boot/firmware/rg35xxh-input.conf   (FAT boot partition, editable from Windows)
   /etc/rg35xxh/input.conf             (system default)
"""
import configparser
import logging
import math
import re

from .core import DEFAULT_BINDINGS, DEFAULT_SETTINGS

PATHS = ("/boot/firmware/rg35xxh-input.conf", "/etc/rg35xxh/input.conf")
BUTTON_NAMES = tuple(DEFAULT_BINDINGS)
_ACTION_RE = re.compile(r"^(none|click_(left|right|middle)|key:KEY_[A-Z0-9_]+|copy|paste|osk_toggle|mode_gamepad|power_menu)$")

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


def _known_key(name):
    """True if evdev knows the key code. Without python-evdev (the unit tests) only the
    pattern is checked."""
    try:
        from evdev import ecodes
    except ImportError:
        return True
    return isinstance(ecodes.ecodes.get(name), int)


def load(paths=PATHS):
    settings, bindings, hardware = {}, {}, {"invert_ly": False, "invert_ry": False, "invert_lx": False, "invert_rx": False}
    cp = configparser.ConfigParser(inline_comment_prefixes=("#", ";"))
    used = None
    for p in paths:
        try:
            with open(p, encoding="utf-8-sig") as f:   # tolerate a BOM from Windows editors
                cp.read_file(f)
            used = p
            break
        except FileNotFoundError:
            continue
        except (OSError, configparser.Error) as e:
            log.warning("cannot read %s: %s", p, e)
    if used:
        log.info("config: %s", used)
    if cp.has_section("settings"):
        for k, v in cp.items("settings"):
            if k in DEFAULT_SETTINGS:
                lo, hi = SETTING_RANGES.get(k, (-math.inf, math.inf))
                try:
                    x = float(v)
                except ValueError:
                    log.warning("settings.%s: not a number: %r (default %s kept)", k, v, DEFAULT_SETTINGS[k])
                    continue
                if not math.isfinite(x) or not lo <= x <= hi:
                    log.warning("settings.%s: %r outside %s..%s (default %s kept)", k, v, lo, hi, DEFAULT_SETTINGS[k])
                    continue
                settings[k] = x
            else:
                log.warning("settings.%s: unknown setting", k)
    if cp.has_section("desktop"):
        for k, v in cp.items("desktop"):
            v = v.strip()
            if k not in BUTTON_NAMES:
                log.warning("desktop.%s: unknown button (valid: %s)", k, ", ".join(BUTTON_NAMES))
            elif not _ACTION_RE.match(v):
                log.warning("desktop.%s: unknown action %r", k, v)
            elif v.startswith("key:") and not _known_key(v[4:]):
                log.warning("desktop.%s: unknown key %r (default kept)", k, v[4:])
            else:
                bindings[k] = v
    if cp.has_section("hardware"):
        for k in hardware:
            if cp.has_option("hardware", k):
                try:
                    hardware[k] = cp.getboolean("hardware", k)
                except ValueError:      # fallback= only covers a missing option, not a bad value
                    log.warning("hardware.%s: not yes/no: %r (default no kept)", k, cp.get("hardware", k))
    return settings, bindings, hardware, used
