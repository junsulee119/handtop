"""Unit tests for failure paths in the External Controller services (overlay/usr/local/sbin:
rg35xxh-btpad, rg35xxh-switchbt, rg35xxh-usbpad). D-Bus, evdev and GLib are replaced by small
fakes: nothing touches Bluetooth, USB or the motor, and nothing needs root. Run from the repo:
python3 -m pytest -q tests. The cases come from the codebase audit of 2026-10-30 (M01, M03, M08)."""
import importlib.machinery
import importlib.util
import os
import signal
import sys
import types
import zlib

import pytest

TOP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SBIN = os.path.join(TOP, "overlay", "usr", "local", "sbin")


class GLib:
    IO_IN, IO_ERR, IO_HUP = 1, 8, 16
    PRIORITY_DEFAULT = 0
    timeouts = []          # (ms, fn, args)
    removed = []
    _next = [100]

    @classmethod
    def timeout_add(cls, ms, fn, *a):
        cls.timeouts.append((ms, fn, a))
        cls._next[0] += 1
        return cls._next[0]

    timeout_add_seconds = timeout_add

    @classmethod
    def io_add_watch(cls, *a):
        cls._next[0] += 1
        return cls._next[0]

    @classmethod
    def source_remove(cls, sid):
        cls.removed.append(sid)

    @classmethod
    def idle_add(cls, *a):
        return 1

    @classmethod
    def reset(cls):
        cls.timeouts.clear()
        cls.removed.clear()

    class MainLoop:
        def run(self):
            pass

        def quit(self):
            pass

    @staticmethod
    def unix_signal_add(*a):
        return 1


def _fakes():
    class Codes(types.ModuleType):
        def __getattr__(self, name):
            if name.startswith("__"):
                raise AttributeError(name)
            return zlib.crc32(name.encode()) & 0xFFFF
    codes = Codes("evdev.ecodes")
    evdev = types.ModuleType("evdev")
    evdev.ecodes = codes

    dbus = types.ModuleType("dbus")
    service = types.ModuleType("dbus.service")
    mainloop = types.ModuleType("dbus.mainloop")
    mainloop_glib = types.ModuleType("dbus.mainloop.glib")

    class Object:
        def __init__(self, *a, **k):
            pass

    def deco(*a, **k):
        return lambda fn: fn
    service.Object = Object
    service.method = service.signal = deco
    dbus.service, dbus.mainloop = service, mainloop
    mainloop.glib = mainloop_glib
    dbus.Array = lambda v, signature=None: list(v)
    dbus.exceptions = types.SimpleNamespace(DBusException=Exception)

    class DBusException(Exception):
        pass
    dbus.DBusException = DBusException
    repo = types.ModuleType("gi.repository")
    repo.GLib = GLib
    gi = types.ModuleType("gi")
    gi.repository = repo
    return {"evdev": evdev, "evdev.ecodes": codes, "dbus": dbus, "dbus.service": service,
            "dbus.mainloop": mainloop, "dbus.mainloop.glib": mainloop_glib,
            "gi": gi, "gi.repository": repo}


def load(name, argv=()):
    """Import one of the service scripts as a module, with the fakes in place."""
    fakes = _fakes()
    saved = {k: sys.modules.get(k) for k in fakes}
    saved_argv = sys.argv
    sys.modules.update(fakes)
    sys.argv = [name, *argv]
    try:
        path = os.path.join(SBIN, name)
        loader = importlib.machinery.SourceFileLoader(name.replace("-", "_") + str(len(argv)), path)
        spec = importlib.util.spec_from_loader(loader.name, loader)
        mod = importlib.util.module_from_spec(spec)
        loader.exec_module(mod)
    finally:
        sys.argv = saved_argv
        for k, v in saved.items():
            if v is None:
                sys.modules.pop(k, None)
            else:
                sys.modules[k] = v
    mod.log = lambda *a: None
    return mod


# ---- M01: a report the link could not take is sent again, not counted as sent
btpad = load("rg35xxh-btpad")


class BusyOnceChr:
    def __init__(self, busy=1):
        self.busy, self.sent = busy, []

    def notify(self, value):
        if self.busy:
            self.busy -= 1
            return False
        self.sent.append(bytes(value))
        return True


def bt_pad(chr_):
    pad = btpad.Pad.__new__(btpad.Pad)
    pad.chr, pad.status = chr_, None
    pad.buttons, pad.hat = set(), [0, 0]
    pad.axes = dict.fromkeys((btpad.E.ABS_X, btpad.E.ABS_Y, btpad.E.ABS_RX, btpad.E.ABS_RY,
                              btpad.E.ABS_Z, btpad.E.ABS_RZ), 0)
    pad.pending, pad.last = False, None
    return pad


def test_ble_report_refused_by_a_busy_link_is_sent_again():
    GLib.reset()
    chr_ = BusyOnceChr(busy=1)
    pad = bt_pad(chr_)
    pad.flush()                                    # busy: nothing sent, nothing remembered
    assert chr_.sent == [] and pad.last is None and pad.pending
    (ms, fn, _), = GLib.timeouts
    assert ms == btpad.RETRY_MS
    fn()                                           # the retry delivers the newest state
    assert len(chr_.sent) == 1 and pad.last == chr_.sent[0] and not pad.pending


def test_ble_notify_reports_a_busy_link():
    c = btpad.Characteristic.__new__(btpad.Characteristic)
    r, w = os.pipe()
    os.set_blocking(w, False)
    try:
        c.notify_fd = w
        while True:                                # fill the pipe: the next write is "busy"
            try:
                os.write(w, b"x" * 4096)
            except BlockingIOError:
                break
        assert c.notify(b"\x01\x02") is False
        os.read(r, 1 << 20)
        assert c.notify(b"\x01\x02") is True
    finally:
        os.close(r)
        os.close(w)


switchbt = load("rg35xxh-switchbt", ["--xbox"])


class FakeSock:
    def __init__(self, busy=0, fileno=10):
        self.busy, self.sent, self.closed, self._fileno = busy, [], False, fileno

    def send(self, data, flags=0):
        if self.busy:
            self.busy -= 1
            raise BlockingIOError(11, "EAGAIN")
        self.sent.append(data)
        return len(data)

    def setblocking(self, flag):
        pass

    def fileno(self):
        return self._fileno

    def close(self):
        self.closed = True


def bare_link():
    link = switchbt.Link.__new__(switchbt.Link)
    link.ctrl = link.itr = None
    link.peer = None
    link.watches, link.watch_by_psm = [], {}
    link.sent = 0
    link.stream = None
    link.xbox_last, link.xbox_sent_at, link.xbox_pending = None, 0.0, False
    link.pad = types.SimpleNamespace(xbox_report=lambda: b"\x00" * 16)
    link.connected = lambda: None
    return link


def test_classic_xbox_report_refused_by_a_busy_link_is_sent_again():
    GLib.reset()
    link = bare_link()
    link.itr = FakeSock(busy=1)
    link._xbox_send()
    assert link.itr.sent == [] and link.xbox_last is None and link.xbox_pending
    (ms, fn, _), = GLib.timeouts
    assert ms == switchbt.RETRY_MS
    fn()
    assert len(link.itr.sent) == 1 and link.xbox_last == b"\x00" * 16 and not link.xbox_pending


def test_classic_xbox_no_retry_without_a_link():
    GLib.reset()
    link = bare_link()
    link._xbox_send()
    assert GLib.timeouts == []


# ---- M03: a channel opened again replaces the old socket and its watch
def test_reopened_channel_replaces_old_socket_and_watch():
    GLib.reset()
    link = bare_link()
    first, second = FakeSock(fileno=11), FakeSock(fileno=12)
    link.attach(first, switchbt.PSM_CTRL, "AA:BB")
    w1 = link.watch_by_psm[switchbt.PSM_CTRL]
    link.attach(second, switchbt.PSM_CTRL, "AA:BB")
    assert first.closed and w1 in GLib.removed
    assert link.ctrl is second and link.watches == [link.watch_by_psm[switchbt.PSM_CTRL]]


# ---- M08: a stop request during the USB set-up still removes the gadget
usbpad = load("rg35xxh-usbpad")


def test_stop_during_usb_setup_removes_the_gadget(monkeypatch):
    calls = []

    def gadget_up():
        calls.append("up")
        os.kill(os.getpid(), signal.SIGTERM)       # systemd stops the mode right now

    monkeypatch.setattr(usbpad, "gadget_up", gadget_up)
    monkeypatch.setattr(usbpad, "gadget_down", lambda fds: calls.append("down"))
    monkeypatch.setattr(usbpad, "Status", lambda: types.SimpleNamespace(close=lambda: calls.append("status closed")))
    monkeypatch.setattr(usbpad, "Pad", lambda *a: types.SimpleNamespace(close=lambda: calls.append("pad closed")))
    old = {s: signal.getsignal(s) for s in (signal.SIGTERM, signal.SIGINT)}
    try:
        with pytest.raises(SystemExit):
            usbpad.main()
        assert calls == ["up", "pad closed", "status closed", "down"]
    finally:
        for s, h in old.items():
            signal.signal(s, h)


# ---- H02: pairing accepts only what a controller needs, and strangers don't stay paired
def test_ble_agent_refuses_every_service():
    agent = btpad.Agent.__new__(btpad.Agent)
    with pytest.raises(btpad.Rejected):
        agent.AuthorizeService("/org/bluez/hci0/dev_X", "00001124-0000-1000-8000-00805f9b34fb")


def test_classic_agent_allows_only_its_hid_profile():
    agent = switchbt.Agent.__new__(switchbt.Agent)
    agent.AuthorizeService("/org/bluez/hci0/dev_X", switchbt.HID_UUID)          # no exception
    for uuid in ("0000110d-0000-1000-8000-00805f9b34fb",                       # A2DP
                 "00001105-0000-1000-8000-00805f9b34fb"):                      # OBEX push
        with pytest.raises(switchbt.Rejected):
            agent.AuthorizeService("/org/bluez/hci0/dev_X", uuid)


@pytest.mark.parametrize("mod", [btpad, switchbt], ids=["btpad", "switchbt"])
def test_strangers_are_new_untrusted_pairings_only(mod):
    devs = {
        "/a/old_pc": {"Paired": True, "Trusted": True},       # paired before the mode
        "/a/old_untrusted": {"Paired": True},                 # paired before, never trusted: keep
        "/a/new_host": {"Paired": True, "Trusted": True},      # paired now and used as host: keep
        "/a/new_stranger": {"Paired": True},                  # paired now, never used: remove
        "/a/seen_only": {"Paired": False},                    # only discovered: nothing to do
    }
    before = {"/a/old_pc", "/a/old_untrusted"}
    assert mod.strangers(devs, before) == ["/a/new_stranger"]
