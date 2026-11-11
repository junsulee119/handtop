"""Folder swaps that never lose the folder in place, and the lock every theme change takes.

swap_in(new, final) moves the old folder aside, then the new one in; if the second step fails, the
old one goes back. If the process dies in between, recover(final) (run before the next change)
finds the folder aside and puts it back. Run under lock(): two theme changes at once (the Theme
app and an ssh command, log-in and a click) would otherwise mix two themes."""
import contextlib
import fcntl
import os
import shutil
import tempfile
import threading

LOCK = os.path.join(os.environ.get("XDG_STATE_HOME") or os.path.expanduser("~/.local/state"),
                    "rg35xxh", "theme.lock")
_held = threading.local()


@contextlib.contextmanager
def lock(path=None):
    """Exclusive, across processes and threads; nested use in one thread is fine."""
    if getattr(_held, "n", 0):
        _held.n += 1
        try:
            yield
        finally:
            _held.n -= 1
        return
    path = path or LOCK
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        _held.n = 1
        try:
            yield
        finally:
            _held.n = 0
    finally:
        os.close(fd)                     # releases the lock


def _aside(final):
    parent, name = os.path.split(final)
    return parent, name, f".old-{name}-"


def recover(final):
    """Undo a swap that died half-way: final missing and a copy aside -> put it back. Copies aside
    while final exists are leftovers of a finished swap and are removed."""
    parent, name, prefix = _aside(final)
    try:
        names = os.listdir(parent)
    except OSError:
        return
    for n in sorted(names):
        d = os.path.join(parent, n)
        if not n.startswith(prefix) or os.path.islink(d) or not os.path.isdir(d):
            continue
        kept = os.path.join(d, name)
        if not os.path.lexists(kept):
            continue                     # another folder's (".old-my-" also starts ".old-my-blue-")
        if not os.path.lexists(final):
            try:
                os.rename(kept, final)
            except OSError:
                continue
        shutil.rmtree(d, ignore_errors=True)


def swap_in(new, final):
    """Replace folder final with folder new (same parent). On failure final is as before."""
    parent, name, prefix = _aside(final)
    old = None
    if os.path.lexists(final):
        old = tempfile.mkdtemp(prefix=prefix, dir=parent)
        os.rename(final, os.path.join(old, name))
    try:
        os.rename(new, final)
    except BaseException:
        if old:
            try:
                os.rename(os.path.join(old, name), final)
            except OSError:
                pass                     # recover() puts it back next time
            else:
                shutil.rmtree(old, ignore_errors=True)
        raise
    if old:
        shutil.rmtree(old, ignore_errors=True)
