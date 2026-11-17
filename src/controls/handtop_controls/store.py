"""Profiles and trials for the Controls app, on top of the input daemon's settings layers
(rg35xxh_inputd/config.py; docs/services/input-daemon.md, "Settings layers").

A profile is a partial input.conf in ~/.config/rg35xxh/controls/<name>.conf holding only what differs
from the system layer (/etc/rg35xxh/input.conf and the built-in defaults); the active one is named in
~/.config/rg35xxh/controls/active. The input daemon re-reads them within 0.1 s.

Changes to anything that can leave you unable to use the handheld (buttons, pointer movement, sticks,
axis inversion) go through a trial first: the new values in $XDG_RUNTIME_DIR/rg35xxh-controls-trial.conf
with an end time. keep() saves them into the profile; without it the daemon deletes the trial when the
time is up (so a crashed app or an unreachable Keep button still undoes it).
"""
import io
import os
import sys
import time

sys.path.append("/usr/local/lib/rg35xxh-inputd")       # appended: a copy earlier on the path wins (tests)
from rg35xxh_inputd import config  # noqa: E402
from rg35xxh_inputd import macros  # noqa: E402
from rg35xxh_inputd.core import DEFAULT_BINDINGS, DEFAULT_SETTINGS  # noqa: E402

TRIAL_SECONDS = 15
# Settings that move the pointer: a change goes through the trial, like every button and [hardware].
NAV_SETTINGS = ("pointer_max_speed", "pointer_curve", "dpad_speed_ratio", "deadzone", "swap_sticks")
DEFAULT_HARDWARE = {k: False for k in config.HARDWARE_KEYS}


class Values:
    """settings / bindings / hardware dicts, complete (every key)."""
    def __init__(self, settings=None, bindings=None, hardware=None):
        self.settings = dict(DEFAULT_SETTINGS)
        self.settings.update(settings or {})
        self.bindings = dict(DEFAULT_BINDINGS)
        self.bindings.update(bindings or {})
        self.hardware = dict(DEFAULT_HARDWARE)
        self.hardware.update(hardware or {})

    def copy(self):
        return Values(self.settings, self.bindings, self.hardware)

    def items(self):
        for sec, d in (("settings", self.settings), ("desktop", self.bindings), ("hardware", self.hardware)):
            for k, v in d.items():
                yield sec, k, v

    def get(self, sec, key):
        return {"settings": self.settings, "desktop": self.bindings, "hardware": self.hardware}[sec].get(key)

    def set(self, sec, key, value):
        {"settings": self.settings, "desktop": self.bindings, "hardware": self.hardware}[sec][key] = value


def needs_trial(sec, key):
    return sec in ("desktop", "hardware") or key in NAV_SETTINGS


# ------------------------------------------------------------------------- reading
def system_values():
    cfg = config.load_layers([("system", config.SYSTEM)])
    return Values(cfg.settings, cfg.bindings, cfg.hardware)


def effective():
    """(Values the daemon uses now, without a running trial; the Layered result with .locked and
    .app_settings)."""
    layers = [(k, p) for k, p in config.layer_paths() if k != "trial"]
    cfg = config.load_layers(layers)
    return Values(cfg.settings, cfg.bindings, cfg.hardware), cfg


def profiles():
    """Profile names, "default" first, then the others alphabetically."""
    names = set()
    try:
        for f in os.listdir(config.controls_dir()):
            if f.endswith(".conf") and config.PROFILE_RE.match(f[:-5]):
                names.add(f[:-5])
    except OSError:
        pass
    names.discard(config.DEFAULT_PROFILE)
    return [config.DEFAULT_PROFILE] + sorted(names, key=str.lower)


def active():
    return config.active_profile()


def read_profile(name):
    """The profile's own values (only what it sets): (settings, bindings, hardware)."""
    cp = config._read(config.profile_path(name))
    if cp is None:
        return {}, {}, {}
    return config.parse(cp, config.profile_path(name))


# ------------------------------------------------------------------------- writing
def _fmt(v):
    if isinstance(v, bool):
        return "yes" if v else "no"
    if isinstance(v, float):
        return f"{v:g}"
    return str(v)


def to_ini(values, base=None, extra=None):
    """INI text with every key whose value differs from base (both Values; None: every key).
    extra: leading sections."""
    out = io.StringIO()
    if extra:
        for sec, kv in extra.items():
            out.write(f"[{sec}]\n")
            for k, v in kv.items():
                out.write(f"{k} = {_fmt(v)}\n")
            out.write("\n")
    for sec in ("settings", "desktop", "hardware"):
        lines = [f"{k} = {_fmt(v)}" for s, k, v in values.items()
                 if s == sec and (base is None or v != base.get(s, k))]
        if lines:
            out.write(f"[{sec}]\n" + "\n".join(lines) + "\n\n")
    return out.getvalue()


def _write_atomic(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def write_profile(name, values):
    if not config.PROFILE_RE.match(name):
        raise ValueError(f"not a profile name: {name!r}")
    _write_atomic(config.profile_path(name), "# Handtop controls profile (Controls app)\n"
                  + to_ini(values, system_values()))


def set_active(name):
    if not config.PROFILE_RE.match(name):
        raise ValueError(f"not a profile name: {name!r}")
    _write_atomic(config.active_file(), name + "\n")


def new_profile(name, copy_from=None):
    """Create a profile (a copy of copy_from, or empty = the system values). False if it exists."""
    if not config.PROFILE_RE.match(name) or os.path.exists(config.profile_path(name)):
        return False
    s, b, h = read_profile(copy_from) if copy_from else ({}, {}, {})
    base = system_values()
    v = base.copy()
    v.settings.update(s)
    v.bindings.update(b)
    v.hardware.update(h)
    write_profile(name, v)
    return True


def rename_profile(old, new):
    if old == config.DEFAULT_PROFILE or not config.PROFILE_RE.match(new) \
            or os.path.exists(config.profile_path(new)):
        return False
    os.replace(config.profile_path(old), config.profile_path(new))
    if active() == old:
        set_active(new)
    return True


def delete_profile(name):
    if name == config.DEFAULT_PROFILE:
        return False
    if active() == name:
        set_active(config.DEFAULT_PROFILE)
    try:
        os.unlink(config.profile_path(name))
    except FileNotFoundError:
        pass
    return True


# ------------------------------------------------------------------------- trials
def problems(values):
    """config.minimal_problems() for complete Values."""
    return config.minimal_problems(values.settings, values.bindings)


def start_trial(values, seconds=TRIAL_SECONDS, now=None):
    """Put values (the whole new profile) on trial; returns the end time. The daemon applies it at
    once and drops it at the end time unless keep() came first."""
    until = (time.time() if now is None else now) + seconds
    # every key, not only what differs from the system: the profile layer lies underneath and must
    # not show through for a key set back to the system value
    _write_atomic(config.trial_path(), to_ini(values, None, {"trial": {"expires": f"{until:.0f}"}}))
    return until


def keep(values, name=None):
    """Save the values on trial into the profile, then end the trial (in that order: no moment
    with neither applied)."""
    write_profile(name or active(), values)
    cancel()


def cancel():
    try:
        os.unlink(config.trial_path())
    except FileNotFoundError:
        pass


def trial_running():
    return os.path.exists(config.trial_path())


def request_vibration_preview():
    """The input daemon plays the mode-change buzz at the current strength (after a change)."""
    path = os.path.join(os.environ.get("XDG_RUNTIME_DIR", "/tmp"), "rg35xxh-haptic-preview")
    with open(path, "w"):
        pass


# ------------------------------------------------------------------------- files
EXPORT_SUFFIX = ".conf"


def free_name(base):
    """base, or base 2, base 3 ... whichever is not a profile yet (and is a valid name)."""
    base = "".join(ch for ch in base if ch.isalnum() or ch in " _.-").lstrip(" _.-").strip()[:36] or "Profile"
    names = {n.lower() for n in profiles()}
    if base.lower() not in names:
        return base
    n = 2
    while f"{base} {n}".lower() in names:
        n += 1
    return f"{base} {n}"


def export_profile(name, path):
    """Write the profile (an input.conf fragment) to path; also usable as the boot partition's file."""
    s, b, h = read_profile(name)
    v = system_values()
    v.settings.update(s)
    v.bindings.update(b)
    v.hardware.update(h)
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"# Handtop controls profile \"{name}\" (exported by the Controls app). Import it in\n"
                "# Controls > Advanced > Profiles, or copy lines into the boot partition's rg35xxh-input.conf.\n"
                + to_ini(v, system_values()))


def import_profile(path, name):
    """A new profile from an exported file (or any input.conf). Bad lines are skipped, as the
    daemon does. Returns how many values it set."""
    cp = config._read(path)
    if cp is None:
        raise ValueError("not a controls file")
    s, b, h = config.parse(cp, path)
    v = system_values()
    v.settings.update(s)
    v.bindings.update(b)
    v.hardware.update(h)
    write_profile(name, v)
    return len(s) + len(b) + len(h)


# ------------------------------------------------------------------------- macros
def combos(values):
    """{"first+second": action} of a Values."""
    return {k: v for k, v in values.bindings.items() if "+" in k}


def record_request(cmd, name=None, pointer=False, timing=True):
    """Ask the input daemon to arm / stop / cancel a macro recording. timing: keep the time between
    steps (False: the steps run back to back)."""
    import json
    data = {"cmd": cmd}
    if name:
        data.update(name=name, pointer=bool(pointer), timing=bool(timing))
    p = os.path.join(os.environ.get("XDG_RUNTIME_DIR", "/tmp"), "rg35xxh-macro-rec.json")
    _write_atomic(p, json.dumps(data))


def record_status():
    import json
    p = os.path.join(os.environ.get("XDG_RUNTIME_DIR", "/tmp"), "rg35xxh-macro-rec.status")
    try:
        with open(p) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def free_macro_name(base):
    names = {n.lower() for n in macros.names()}
    n = 1
    while f"{base} {n}".lower() in names:
        n += 1
    return f"{base} {n}"
