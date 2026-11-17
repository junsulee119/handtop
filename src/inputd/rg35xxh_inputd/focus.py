"""Which window has the focus: a tiny Wayland client for wlr-foreign-toplevel-management.

labwc tells clients of this protocol (waybar's taskbar, wlrctl) about every window: its app_id,
title and state (activated = focused). The input daemon uses it to switch Controls profiles per
app. Only the few messages needed are spoken here, straight on the socket (no library): the
daemon adds fileno() to its select loop and calls read() when it is readable, so nothing runs
while no window changes.

Wire format (wayland.freedesktop.org, "Wire Format"): native-endian 32-bit words; each message
is [object id][size << 16 | opcode][arguments], strings and arrays as [length][bytes, padded to 4].
"""
import logging
import os
import socket
import struct

log = logging.getLogger("rg35xxh-inputd.focus")

MANAGER = "zwlr_foreign_toplevel_manager_v1"
MANAGER_VERSION = 3          # labwc 0.8 offers 3; nothing here needs more than 1
MINIMIZED, ACTIVATED = 1, 2  # zwlr_foreign_toplevel_handle_v1.state values

DISPLAY_ID, REGISTRY_ID, MANAGER_ID = 1, 2, 3

# opcodes
DISPLAY_GET_REGISTRY, REGISTRY_BIND = 1, 0
EV_DISPLAY_ERROR, EV_DISPLAY_DELETE_ID = 0, 1
EV_REGISTRY_GLOBAL = 0
EV_MANAGER_TOPLEVEL, EV_MANAGER_FINISHED = 0, 1
EV_TITLE, EV_APP_ID, EV_STATE, EV_DONE, EV_CLOSED = 0, 1, 4, 5, 6
REQ_HANDLE_DESTROY = 7

MAX_BUFFER = 1 << 20         # a client this far behind is broken: drop the connection


class ProtocolError(Exception):
    pass


def _string(data, off):
    """(value, next offset) of a string argument; None for a null string."""
    (n,) = struct.unpack_from("=I", data, off)
    off += 4
    if n == 0:
        return None, off
    if off + n > len(data):
        raise ProtocolError("string runs past the message")
    raw = data[off:off + n - 1]                    # length counts the trailing NUL
    return raw.decode("utf-8", "replace"), off + ((n + 3) & ~3)


def _array(data, off):
    (n,) = struct.unpack_from("=I", data, off)
    off += 4
    if off + n > len(data):
        raise ProtocolError("array runs past the message")
    return data[off:off + n], off + ((n + 3) & ~3)


def _message(obj, opcode, payload=b""):
    return struct.pack("=II", obj, ((8 + len(payload)) << 16) | opcode) + payload


def _pack_string(s):
    b = s.encode() + b"\0"
    return struct.pack("=I", len(b)) + b + b"\0" * (-len(b) % 4)


class Window:
    __slots__ = ("app_id", "title", "active", "minimized", "pending_app_id", "pending_title", "pending_state")

    def __init__(self):
        self.app_id = self.title = None
        self.active = self.minimized = False
        self.pending_app_id = self.pending_title = self.pending_state = None


class FocusWatcher:
    """Connects, binds the toplevel manager and keeps the window list. focused() = app_id of the
    window in front (see there)."""

    def __init__(self, path=None, sock=None):
        """path: the compositor's socket ($XDG_RUNTIME_DIR/$WAYLAND_DISPLAY by default); sock: an
        already connected socket instead (tests: one end of a socketpair)."""
        if sock is None:
            if path is None:
                display = os.environ.get("WAYLAND_DISPLAY", "wayland-0")
                path = display if display.startswith("/") else \
                    os.path.join(os.environ.get("XDG_RUNTIME_DIR", "/run/user/%d" % os.getuid()), display)
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM | socket.SOCK_CLOEXEC)
            try:
                sock.connect(path)
            except OSError:
                sock.close()
                raise
        self.sock = sock
        self.sock.setblocking(False)
        self.buf = b""
        self.windows = {}
        self.last_active = None      # handle id of the window that had the focus last
        self.bound = False
        self._send(_message(DISPLAY_ID, DISPLAY_GET_REGISTRY, struct.pack("=I", REGISTRY_ID)))

    def fileno(self):
        return self.sock.fileno()

    def close(self):
        try:
            self.sock.close()
        except OSError:
            pass

    def focused(self):
        """app_id of the focused window. While no window has the focus because an overlay took the
        keyboard (app drawer, power menu, on-screen keyboard, the External Controller status
        screen), the window that had it last still counts: it is still the app in front. None
        once that window is closed or minimized (the bare desktop)."""
        for w in self.windows.values():
            if w.active:
                return w.app_id
        w = self.windows.get(self.last_active)
        return w.app_id if w is not None and not w.minimized else None

    def open_windows(self):
        """[(app_id, title)] of the windows open now, for the Controls app's picker."""
        return [(w.app_id, w.title) for w in self.windows.values() if w.app_id]

    def _send(self, data):
        # Requests are tiny and rare (one bind, a destroy per closed window); the socket buffer
        # always has room, so a short write means the compositor is gone.
        if self.sock.send(data) != len(data):
            raise ProtocolError("short write")

    def read(self):
        """Read what is waiting and handle it. True if the window list changed. Raises OSError /
        ProtocolError when the connection is lost or broken (the caller reconnects later)."""
        while True:
            try:
                chunk = self.sock.recv(65536)
            except BlockingIOError:
                break
            if not chunk:
                raise ProtocolError("compositor closed the connection")
            self.buf += chunk
            if len(self.buf) > MAX_BUFFER:
                raise ProtocolError("message too large")
        changed = False
        buf, off = self.buf, 0
        while len(buf) - off >= 8:
            obj, word = struct.unpack_from("=II", buf, off)
            size, opcode = word >> 16, word & 0xFFFF
            if size < 8 or size % 4:
                raise ProtocolError("bad message size %d" % size)
            if len(buf) - off < size:
                break
            changed |= self._event(obj, opcode, buf[off + 8:off + size])
            off += size
        self.buf = buf[off:]
        return changed

    def _event(self, obj, opcode, data):
        if obj == DISPLAY_ID:
            if opcode == EV_DISPLAY_ERROR:
                _, code = struct.unpack_from("=II", data, 0)
                msg, _ = _string(data, 8)
                raise ProtocolError("compositor error %d: %s" % (code, msg))
            return False                       # delete_id: nothing to free here
        if obj == REGISTRY_ID:
            if opcode == EV_REGISTRY_GLOBAL and not self.bound:
                (name,) = struct.unpack_from("=I", data, 0)
                iface, off = _string(data, 4)
                (version,) = struct.unpack_from("=I", data, off)
                if iface == MANAGER:
                    v = min(version, MANAGER_VERSION)
                    self._send(_message(REGISTRY_ID, REGISTRY_BIND, struct.pack("=I", name)
                                        + _pack_string(MANAGER) + struct.pack("=II", v, MANAGER_ID)))
                    self.bound = True
            return False
        if obj == MANAGER_ID:
            if opcode == EV_MANAGER_TOPLEVEL:
                (new_id,) = struct.unpack_from("=I", data, 0)
                self.windows[new_id] = Window()
                return False
            if opcode == EV_MANAGER_FINISHED:
                raise ProtocolError("toplevel manager finished")
            return False
        w = self.windows.get(obj)
        if w is None:
            return False                       # an object we never asked about (or already gone)
        if opcode == EV_TITLE:
            w.pending_title, _ = _string(data, 0)
        elif opcode == EV_APP_ID:
            w.pending_app_id, _ = _string(data, 0)
        elif opcode == EV_STATE:
            arr, _ = _array(data, 0)
            states = struct.unpack("=%dI" % (len(arr) // 4), arr[:len(arr) // 4 * 4])
            w.pending_state = states
        elif opcode == EV_DONE:
            before = (w.app_id, w.active, w.minimized)
            if w.pending_title is not None:
                w.title = w.pending_title
            if w.pending_app_id is not None:
                w.app_id = w.pending_app_id
            if w.pending_state is not None:
                w.active = ACTIVATED in w.pending_state
                w.minimized = MINIMIZED in w.pending_state
            w.pending_title = w.pending_app_id = w.pending_state = None
            if w.active:
                self.last_active = obj
            return (w.app_id, w.active, w.minimized) != before   # a new title alone changes nothing
        elif opcode == EV_CLOSED:
            del self.windows[obj]
            if self.last_active == obj:
                self.last_active = None
            self._send(_message(obj, REQ_HANDLE_DESTROY))
            return True
        return False


if __name__ == "__main__":                     # manual check: print focus changes
    import select
    fw = FocusWatcher()
    last = object()
    while True:
        select.select([fw], [], [])
        fw.read()
        now = fw.focused()
        if now != last:
            print("focused:", now, "| open:", fw.open_windows(), flush=True)
            last = now
