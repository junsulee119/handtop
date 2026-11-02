"""Unit tests for failure paths in rg35xxh_inputd.daemon, with python-evdev and GLib replaced
by small fakes: no hardware, no display, nothing is grabbed or vibrated. Run with pytest
(cd src/inputd && python3 -m pytest -q tests). The cases come from the codebase audit of
2026-10-30 (M02, M05, M07)."""
import os
import sys
import types
import zlib

import pytest


def _import_daemon():
    class Codes(types.ModuleType):          # any evdev code name -> a stable int
        def __getattr__(self, name):
            if name.startswith("__"):
                raise AttributeError(name)
            return zlib.crc32(name.encode()) & 0xFFFF
    codes = Codes("evdev.ecodes")
    codes.ecodes = {}
    ff = types.ModuleType("evdev.ff")
    for n in ("Rumble", "Effect", "Trigger", "Replay", "EffectType"):
        setattr(ff, n, lambda *a, **k: types.SimpleNamespace(args=a, **k))
    evdev = types.ModuleType("evdev")
    evdev.ecodes, evdev.ff = codes, ff
    evdev.UInput = evdev.InputDevice = object
    evdev.list_devices = lambda: []

    class GLib:
        IO_IN, IO_ERR, IO_HUP = 1, 8, 16
        PRIORITY_DEFAULT, PRIORITY_HIGH = 0, -100
        idle = []

        @staticmethod
        def idle_add(fn, *a):
            GLib.idle.append(fn)
            return 1

        @staticmethod
        def timeout_add(*a):
            return 2

        @staticmethod
        def source_remove(_id):
            pass

        @staticmethod
        def io_add_watch(*a):
            return 3
    repo = types.ModuleType("gi.repository")
    repo.GLib = GLib
    gi = types.ModuleType("gi")
    gi.repository = repo
    fakes = {"evdev": evdev, "evdev.ecodes": codes, "evdev.ff": ff, "gi": gi, "gi.repository": repo}
    saved = {k: sys.modules.get(k) for k in fakes}
    sys.modules.update(fakes)
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
    try:
        from rg35xxh_inputd import daemon
    finally:   # the fakes are for daemon.py only (config.py looks evdev up again later)
        for k, v in saved.items():
            if v is None:
                sys.modules.pop(k, None)
            else:
                sys.modules[k] = v
    return daemon, GLib


daemon, GLib = _import_daemon()
E = daemon.E


class FakeGamepad:
    def __init__(self, name=daemon.GAMEPAD_NAME, path="/dev/input/event1", grab_error=None):
        self.name, self.path, self.grab_error = name, path, grab_error
        self.uploads, self.writes, self.erased, self.closed, self.grabs = [], [], [], False, 0

    def capabilities(self):
        return {E.EV_FF: [], E.EV_ABS: []}

    def upload_effect(self, eff):
        self.uploads.append(eff)
        return 40 + len(self.uploads)

    def write(self, *a):
        self.writes.append(a)

    def erase_effect(self, eid):
        self.erased.append(eid)

    def grab(self):
        self.grabs += 1
        if self.grab_error:
            raise self.grab_error

    def close(self):
        self.closed = True


def bare_daemon():
    d = daemon.Daemon.__new__(daemon.Daemon)
    d.gamepad = FakeGamepad()
    d.pad = types.SimpleNamespace(close=lambda: None)
    d.pad_watch = 7
    d.pad_ff = {}
    d.motor_timer = d.motor_refresh_timer = None
    d.motor_last = 0.0
    d.motor_pending_upload, d.motor_pending_play = {}, {}
    d.motor_ext_want = d.motor_ext_applied = 0
    d.motor_ext_ids = {}
    d.motor_game_endless, d.motor_game_active = set(), set()
    d.devices = []
    return d


# ---- M02: a game's vibration still queued when gamepad mode ends
def test_queued_game_vibration_does_not_play_after_gamepad_mode():
    d = bare_daemon()
    d.motor_pending_upload[0] = types.SimpleNamespace(id=-1)
    d.motor_pending_play[0] = 1
    d._destroy_pad()
    d._motor_flush()
    assert d.gamepad.uploads == [] and d.gamepad.writes == []
    assert d.pad_ff == {}


def test_queued_game_vibration_plays_while_in_gamepad_mode():
    d = bare_daemon()
    d.motor_pending_upload[0] = types.SimpleNamespace(id=-1)
    d.motor_pending_play[0] = 1
    d._motor_flush()
    assert len(d.gamepad.uploads) == 1
    assert d.gamepad.writes == [(E.EV_FF, d.pad_ff[0], 1)]


# ---- M05: an exception in an input callback ends the daemon instead of leaving it half dead
def test_input_loop_error_ends_the_daemon():
    d = bare_daemon()
    d.ticks = 0
    d.core = types.SimpleNamespace(tick=lambda now: 1 / 0)
    GLib.idle.clear()
    assert d._tick() is False
    assert GLib.idle == [d._quit]


def test_device_input_error_ends_the_daemon():
    d = bare_daemon()
    dev = FakeGamepad()
    dev.read = lambda: [types.SimpleNamespace(type=E.EV_KEY, code=next(iter(daemon.HW_BUTTONS)), value=1)]
    d.core = types.SimpleNamespace(button=lambda *a: (_ for _ in ()).throw(KeyError("boom")))
    GLib.idle.clear()
    assert d._on_device(3, GLib.IO_IN, dev) is False
    assert GLib.idle == [d._quit]


def test_device_read_oserror_keeps_running():
    d = bare_daemon()
    dev = FakeGamepad()

    def read():
        raise OSError(5, "EIO")
    dev.read = read
    GLib.idle.clear()
    assert d._on_device(3, GLib.IO_IN, dev) is True
    assert GLib.idle == []


# ---- M07: a device that cannot be grabbed is not used
def _open_with(monkeypatch, devs):
    by_path = {x.path: x for x in devs}
    monkeypatch.setattr(daemon.evdev, "list_devices", lambda: list(by_path))
    monkeypatch.setattr(daemon.evdev, "InputDevice", lambda p: by_path[p])
    monkeypatch.setattr(daemon.time, "sleep", lambda s: None)
    d = bare_daemon()
    d.gamepad = None
    d.setup_calls = 0
    d._setup_gamepad = lambda: setattr(d, "setup_calls", d.setup_calls + 1)
    d._watch = lambda dev: None
    return d


def test_gamepad_that_cannot_be_grabbed_ends_start_up(monkeypatch):
    pad = FakeGamepad(grab_error=OSError(16, "EBUSY"))
    vol = FakeGamepad("gpio-keys-volume", "/dev/input/event2")
    pwr = FakeGamepad("axp20x-pek", "/dev/input/event0")
    d = _open_with(monkeypatch, [pad, vol, pwr])
    with pytest.raises(RuntimeError):
        d._open_devices(wait=1.0)
    assert pad.grabs == daemon.GRAB_TRIES and pad.closed
    assert d.gamepad is None and d.setup_calls == 0
    assert all(x.closed for x in (vol, pwr) if x not in d.devices)


def test_other_device_that_cannot_be_grabbed_is_left_out(monkeypatch):
    pad = FakeGamepad()
    vol = FakeGamepad("gpio-keys-volume", "/dev/input/event2", grab_error=OSError(16, "EBUSY"))
    pwr = FakeGamepad("axp20x-pek", "/dev/input/event0")
    d = _open_with(monkeypatch, [pad, vol, pwr])
    d._open_devices(wait=1.0)
    assert vol.closed and vol not in d.devices
    assert d.gamepad is pad and d.setup_calls == 1 and pwr in d.devices


def test_busy_gamepad_released_in_time_is_used(monkeypatch):
    pad = FakeGamepad()
    calls = {"n": 0}

    def flaky():
        calls["n"] += 1
        if calls["n"] < 3:
            raise OSError(16, "EBUSY")
    pad.grab = flaky
    vol = FakeGamepad("gpio-keys-volume", "/dev/input/event2")
    pwr = FakeGamepad("axp20x-pek", "/dev/input/event0")
    d = _open_with(monkeypatch, [pad, vol, pwr])
    d._open_devices(wait=1.0)
    assert d.gamepad is pad and not pad.closed and calls["n"] == 3
