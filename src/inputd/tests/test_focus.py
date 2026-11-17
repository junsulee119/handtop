"""Tests for rg35xxh_inputd.focus (the focused-window watcher behind auto-switch per app). The
compositor is played by the other end of a socketpair: the tests write Wayland events into it
and read back what the watcher sends. Run with pytest (cd src/inputd && python3 -m pytest -q tests)."""
import os
import socket
import struct
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from rg35xxh_inputd import focus  # noqa: E402

H1, H2 = 0xFF000000, 0xFF000001          # handle ids the compositor picks


def _str(s):
    b = s.encode() + b"\0"
    return struct.pack("=I", len(b)) + b + b"\0" * (-len(b) % 4)


def _ev(obj, opcode, payload=b""):
    return struct.pack("=II", obj, ((8 + len(payload)) << 16) | opcode) + payload


def _states(*values):
    arr = struct.pack("=%dI" % len(values), *values)
    return struct.pack("=I", len(arr)) + arr


def _window(handle, app_id, title, *states):
    return (_ev(focus.MANAGER_ID, focus.EV_MANAGER_TOPLEVEL, struct.pack("=I", handle))
            + _ev(handle, focus.EV_TITLE, _str(title)) + _ev(handle, focus.EV_APP_ID, _str(app_id))
            + _ev(handle, focus.EV_STATE, _states(*states)) + _ev(handle, focus.EV_DONE))


def _requests(server):
    """[(object, opcode, payload)] the watcher has sent."""
    server.setblocking(False)
    data = b""
    try:
        while True:
            chunk = server.recv(65536)
            if not chunk:
                break
            data += chunk
    except BlockingIOError:
        pass
    out, off = [], 0
    while off < len(data):
        obj, word = struct.unpack_from("=II", data, off)
        size = word >> 16
        out.append((obj, word & 0xFFFF, data[off + 8:off + size]))
        off += size
    return out


@pytest.fixture
def pair():
    server, client = socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM)
    fw = focus.FocusWatcher(sock=client)
    yield fw, server
    fw.close()
    server.close()


def _bound(fw, server):
    server.sendall(_ev(focus.REGISTRY_ID, focus.EV_REGISTRY_GLOBAL, struct.pack("=I", 7) + _str("wl_seat")
                       + struct.pack("=I", 9))
                   + _ev(focus.REGISTRY_ID, focus.EV_REGISTRY_GLOBAL, struct.pack("=I", 12)
                         + _str(focus.MANAGER) + struct.pack("=I", 3)))
    fw.read()
    return _requests(server)


def test_asks_for_the_registry_then_binds_only_the_toplevel_manager(pair):
    fw, server = pair
    reqs = _bound(fw, server)
    assert reqs[0] == (focus.DISPLAY_ID, focus.DISPLAY_GET_REGISTRY, struct.pack("=I", focus.REGISTRY_ID))
    assert len(reqs) == 2
    obj, op, payload = reqs[1]
    assert (obj, op) == (focus.REGISTRY_ID, focus.REGISTRY_BIND)
    assert payload == struct.pack("=I", 12) + _str(focus.MANAGER) + struct.pack("=II", 3, focus.MANAGER_ID)
    assert fw.bound


def test_focus_follows_the_activated_window(pair):
    fw, server = pair
    _bound(fw, server)
    server.sendall(_window(H1, "Thunar", "Home - Thunar", focus.ACTIVATED))
    assert fw.read() is True
    assert fw.focused() == "Thunar"
    server.sendall(_ev(H1, focus.EV_STATE, _states()) + _ev(H1, focus.EV_DONE)
                   + _window(H2, "foot", "foot", focus.ACTIVATED, 0))
    assert fw.read() is True
    assert fw.focused() == "foot"
    assert sorted(fw.open_windows()) == [("Thunar", "Home - Thunar"), ("foot", "foot")]


def test_a_new_title_alone_is_no_change(pair):
    fw, server = pair
    _bound(fw, server)
    server.sendall(_window(H1, "foot", "foot", focus.ACTIVATED))
    fw.read()
    server.sendall(_ev(H1, focus.EV_TITLE, _str("vim notes.txt")) + _ev(H1, focus.EV_DONE))
    assert fw.read() is False
    assert fw.open_windows() == [("foot", "vim notes.txt")]


def test_an_overlay_taking_the_keyboard_keeps_the_app_in_front(pair):
    fw, server = pair
    _bound(fw, server)
    server.sendall(_window(H1, "mpv", "film.mkv", focus.ACTIVATED))
    fw.read()
    server.sendall(_ev(H1, focus.EV_STATE, _states()) + _ev(H1, focus.EV_DONE))   # app drawer opens
    fw.read()
    assert fw.focused() == "mpv"
    server.sendall(_ev(H1, focus.EV_STATE, _states(focus.MINIMIZED)) + _ev(H1, focus.EV_DONE))
    fw.read()
    assert fw.focused() is None


def test_closing_the_focused_window_leaves_no_app_and_frees_the_handle(pair):
    fw, server = pair
    _bound(fw, server)
    server.sendall(_window(H1, "Thunar", "t", 0) + _window(H2, "foot", "f", focus.ACTIVATED))
    fw.read()
    server.sendall(_ev(H2, focus.EV_CLOSED))
    assert fw.read() is True
    assert fw.focused() is None                  # Thunar is open but nobody gave it the focus
    assert fw.open_windows() == [("Thunar", "t")]
    assert _requests(server) == [(H2, focus.REQ_HANDLE_DESTROY, b"")]


def test_messages_split_across_reads(pair):
    fw, server = pair
    _bound(fw, server)
    data = _window(H1, "org.example.Game", "Game", focus.ACTIVATED)
    for i in range(0, len(data), 5):
        server.sendall(data[i:i + 5])
        fw.read()
    assert fw.focused() == "org.example.Game"


def test_unknown_objects_and_events_are_ignored(pair):
    fw, server = pair
    _bound(fw, server)
    server.sendall(_ev(0xFF0000AA, focus.EV_TITLE, _str("x")) + _ev(focus.DISPLAY_ID, focus.EV_DISPLAY_DELETE_ID,
                                                                   struct.pack("=I", 5)))
    assert fw.read() is False


def test_compositor_error_and_hang_up_raise(pair):
    fw, server = pair
    server.sendall(_ev(focus.DISPLAY_ID, focus.EV_DISPLAY_ERROR, struct.pack("=II", 3, 1) + _str("bad")))
    with pytest.raises(focus.ProtocolError, match="bad"):
        fw.read()
    server.close()
    fw.buf = b""
    with pytest.raises((focus.ProtocolError, OSError)):
        fw.read()


def test_bad_sizes_raise(pair):
    fw, server = pair
    server.sendall(struct.pack("=II", 1, (6 << 16) | 0))
    with pytest.raises(focus.ProtocolError):
        fw.read()


def test_string_running_past_its_message_raises(pair):
    fw, server = pair
    _bound(fw, server)
    server.sendall(_ev(focus.MANAGER_ID, focus.EV_MANAGER_TOPLEVEL, struct.pack("=I", H1))
                   + _ev(H1, focus.EV_APP_ID, struct.pack("=I", 100) + b"abcd"))
    with pytest.raises(focus.ProtocolError):
        fw.read()
