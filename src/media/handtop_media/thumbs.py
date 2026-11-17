"""Video thumbnails in the shared freedesktop cache (~/.cache/thumbnails/normal), so the File
Manager and the Videos app use the same ones. Made one at a time in a worker thread with the
ffmpeg CLI (a frame 10 s in, or the first frame of a shorter file), at low priority."""
import hashlib
import os
import subprocess
import tempfile
import threading
import queue
from urllib.parse import quote

import gi
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import GdkPixbuf, GLib  # noqa: E402

SIZE = 128                    # "normal" thumbnails: at most 128x128
TIMEOUT = 20                  # s per file; a stuck decode must not hold the queue


def cache_dir():
    base = os.environ.get("XDG_CACHE_HOME") or os.path.expanduser("~/.cache")
    return os.path.join(base, "thumbnails", "normal")


def uri(path):
    return "file://" + quote(os.path.abspath(path), safe="/")


def thumb_path(path):
    return os.path.join(cache_dir(), hashlib.md5(uri(path).encode()).hexdigest() + ".png")


def cached(path):
    """The thumbnail if it exists and belongs to this version of the file (Thumb::MTime), else
    None."""
    t = thumb_path(path)
    try:
        mtime = int(os.stat(path).st_mtime)
        pb = GdkPixbuf.Pixbuf.new_from_file(t)
    except (OSError, GLib.Error):
        return None
    if pb.get_option("tEXt::Thumb::MTime") not in (None, str(mtime)):
        return None
    return pb


def _make(path):
    t = thumb_path(path)
    os.makedirs(os.path.dirname(t), mode=0o700, exist_ok=True)
    try:
        mtime = int(os.stat(path).st_mtime)
    except OSError:
        return None
    fd, tmp = tempfile.mkstemp(suffix=".png", dir=os.path.dirname(t))
    os.close(fd)
    try:
        scale = f"scale={SIZE}:{SIZE}:force_original_aspect_ratio=decrease"
        for start in ("10", "0"):
            cmd = ["nice", "-n", "10", "ffmpeg", "-nostdin", "-v", "error", "-y", "-ss", start,
                   "-i", path, "-an", "-sn", "-frames:v", "1", "-vf", scale, tmp]
            try:
                subprocess.run(cmd, timeout=TIMEOUT, stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL, check=False)
            except (OSError, subprocess.TimeoutExpired):
                continue
            if os.path.getsize(tmp) > 0:
                break
        else:
            return None
        pb = GdkPixbuf.Pixbuf.new_from_file(tmp)
        pb.savev(tmp, "png", ["tEXt::Thumb::URI", "tEXt::Thumb::MTime"], [uri(path), str(mtime)])
        os.replace(tmp, t)
        return pb
    except (OSError, GLib.Error):
        return None
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


class Maker:
    """Queue paths; done(path, pixbuf) is called on the main loop for each one made."""

    def __init__(self, done):
        self.done = done
        self.q = queue.Queue()
        threading.Thread(target=self._run, daemon=True).start()

    def add(self, path):
        self.q.put(path)

    def clear(self):
        try:
            while True:
                self.q.get_nowait()
        except queue.Empty:
            pass

    def _run(self):
        while True:
            path = self.q.get()
            pb = _make(path)
            if pb is not None:
                GLib.idle_add(self.done, path, pb)
