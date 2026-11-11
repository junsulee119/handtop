"""Unit tests for failure paths in rg35xxh_inputd.daemon, with python-evdev and GLib replaced
by small fakes: no hardware, no display, nothing is grabbed or vibrated. Run with pytest
(cd src/inputd && python3 -m pytest -q tests). The cases come from the codebase audit of
2026-10-30 (M02, M05, M06, M07)."""
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
    d.dropped = set()
    d.absinfo = {}
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


# ---- M06: events dropped by the kernel are recovered from the device's state
class Core:
    def __init__(self, held=()):
        self.held = dict.fromkeys(held, 0.0)
        self.calls = []

    def button(self, name, pressed, t):
        self.calls.append((name, pressed))
        if pressed:
            self.held[name] = t
        else:
            self.held.pop(name, None)
        return []

    def axis(self, name, value, t):
        self.calls.append((name, round(value, 2)))
        return []


def _ev(t, code, value=0):
    return types.SimpleNamespace(type=t, code=code, value=value)


def _dropped_gamepad(events, active=(), axes=None):
    dev = FakeGamepad()
    dev.read = lambda: list(events)
    dev.active_keys = lambda: list(active)
    keys = list(daemon.HW_BUTTONS)
    dev.capabilities = lambda: {E.EV_KEY: keys, E.EV_ABS: []}
    dev.absinfo = lambda code: types.SimpleNamespace(value=(axes or {}).get(code, 0))
    return dev


A = next(c for c, n in daemon.HW_BUTTONS.items() if n == "a")
B = next(c for c, n in daemon.HW_BUTTONS.items() if n == "b")


def test_release_lost_in_a_queue_overflow_is_recovered():
    d = bare_daemon()
    d.core = Core(held=["a"])
    d._run = lambda actions: None
    # A was released while the queue overflowed: the kernel sends SYN_DROPPED, maybe stale
    # events, then SYN_REPORT; the device now reports A up.
    dev = _dropped_gamepad([_ev(E.EV_SYN, E.SYN_DROPPED), _ev(E.EV_KEY, B, 1),
                            _ev(E.EV_SYN, E.SYN_REPORT)], active=[])
    d.gamepad = dev
    assert d._on_device(3, GLib.IO_IN, dev) is True
    assert ("a", False) in d.core.calls and "a" not in d.core.held
    assert ("b", True) not in d.core.calls            # the stale event inside the gap is skipped
    assert d.dropped == set()


def test_resync_presses_held_buttons_and_reads_the_sticks():
    d = bare_daemon()
    d.core = Core()
    d._run = lambda actions: None
    d.absinfo = {E.ABS_X: types.SimpleNamespace(min=-100, max=100)}
    d.axis_offset, d.hw = {}, {}
    dev = _dropped_gamepad([_ev(E.EV_SYN, E.SYN_DROPPED), _ev(E.EV_SYN, E.SYN_REPORT)],
                           active=[B], axes={E.ABS_X: 50})
    d.gamepad = dev
    d._on_device(3, GLib.IO_IN, dev)
    assert d.core.calls == [("b", True), ("lx", 0.5)]


def test_events_after_the_gap_are_handled_normally():
    d = bare_daemon()
    d.core = Core()
    d._run = lambda actions: None
    dev = _dropped_gamepad([_ev(E.EV_SYN, E.SYN_DROPPED), _ev(E.EV_SYN, E.SYN_REPORT),
                            _ev(E.EV_KEY, A, 1), _ev(E.EV_SYN, E.SYN_REPORT)])
    d.gamepad = None                                   # not the gamepad: no stick read
    d._on_device(3, GLib.IO_IN, dev)
    assert d.core.calls == [("a", True)]


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


# ---- 2026-11-06: an empty pointer layout (wlr-randr glitch) must not drop the speed to x1

def _layout_daemon(monkeypatch, tmp_path):
    path = tmp_path / "rg35xxh-pointer-layout"
    monkeypatch.setattr(daemon, "runtime_flag", lambda name: str(path))
    d = daemon.Daemon.__new__(daemon.Daemon)
    d.layout = daemon.PointerLayout()
    d.layout_mtime = None
    d.core = types.SimpleNamespace(s={"display_speed_scale": True}, pointer_scale=1.0)
    return d, path


def _write(path, text, mtime):
    path.write_text(text)
    os.utime(path, (mtime, mtime))


def test_empty_layout_keeps_the_monitor_speed(monkeypatch, tmp_path):
    d, path = _layout_daemon(monkeypatch, tmp_path)
    _write(path, '[{"name": "HDMI-A-1", "x": 0, "y": 0, "w": 1920, "h": 1080, "scale": 2.754}]', 1000)
    d._layout_reload()
    big = d.core.pointer_scale
    assert big > 2
    _write(path, "[]", 1001)
    d._layout_reload()
    assert d.core.pointer_scale == big


def test_missing_layout_file_means_handheld_speed(monkeypatch, tmp_path):
    d, path = _layout_daemon(monkeypatch, tmp_path)
    _write(path, '[{"name": "HDMI-A-1", "x": 0, "y": 0, "w": 1920, "h": 1080, "scale": 2.754}]', 1000)
    d._layout_reload()
    path.unlink()
    d._layout_reload()
    assert d.core.pointer_scale == 1.0


def test_spawn_leaves_no_zombie():
    """A program started with spawn() is waited for once it exits (2026-11-11: a finished
    wlogout stayed a zombie and the taskbar's power button stopped opening the menu)."""
    import time
    p = daemon.spawn("true")
    assert p is not None
    for _ in range(100):
        if p.returncode is not None:
            break
        time.sleep(0.02)
    assert p.returncode == 0
    with pytest.raises(ChildProcessError):
        os.waitpid(p.pid, os.WNOHANG)                # already reaped: nothing left to wait for


def test_spawn_missing_program():
    assert daemon.spawn("/nonexistent/rg35xxh-nothing") is None
