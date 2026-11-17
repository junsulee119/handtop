"""Folders and files for the media apps: what a folder shows, in which order, and the places a
browser can start from. No GTK here (unit-tested)."""
import hashlib
import os
import re

VIDEO = {"mp4", "m4v", "mkv", "webm", "mov", "avi", "mpg", "mpeg", "ts", "m2ts", "mts", "ogv",
         "wmv", "flv", "3gp"}
AUDIO = {"mp3", "flac", "ogg", "oga", "opus", "m4a", "aac", "wav", "wma", "ape", "wv", "mka",
         "aif", "aiff"}
COVERS = ("cover", "folder", "front", "album")          # cover.jpg, Folder.png, ...
COVER_EXT = (".jpg", ".jpeg", ".png")


def ext(name):
    return name.rsplit(".", 1)[-1].lower() if "." in name else ""


def natural_key(name):
    """'Track 2' before 'Track 10'; case-insensitive."""
    return [int(p) if p.isdigit() else p for p in re.split(r"(\d+)", name.casefold())]


def listing(path, kinds):
    """(folders, files) in path: names, sorted naturally, hidden entries left out. files are
    those whose extension is in kinds. A folder that can't be read gives two empty lists."""
    folders, files = [], []
    try:
        with os.scandir(path) as it:
            for e in it:
                if e.name.startswith("."):
                    continue
                try:
                    if e.is_dir():
                        folders.append(e.name)
                    elif e.is_file() and ext(e.name) in kinds:
                        files.append(e.name)
                except OSError:
                    continue
    except OSError:
        return [], []
    return sorted(folders, key=natural_key), sorted(files, key=natural_key)


def title_of(name):
    """A file's name as shown in a list: without its extension."""
    return name.rsplit(".", 1)[0] if "." in name else name


def cover_file(folder):
    """The folder's own cover picture (cover.jpg, folder.png, ...), or None."""
    try:
        names = {n.casefold(): n for n in os.listdir(folder)}
    except OSError:
        return None
    for base in COVERS:
        for e in COVER_EXT:
            n = names.get(base + e)
            if n:
                return os.path.join(folder, n)
    return None


def user():
    try:
        import pwd
        return pwd.getpwuid(os.getuid()).pw_name
    except (ImportError, KeyError):
        return os.environ.get("USER", "")


def drives():
    """Mounted removable drives (udisks2 mounts them under /media/<user>/), as (name, path)."""
    out = []
    u = user()
    for base in (f"/media/{u}", f"/run/media/{u}"):
        try:
            names = sorted(os.listdir(base), key=natural_key)
        except OSError:
            continue
        for n in names:
            p = os.path.join(base, n)
            if os.path.ismount(p):
                out.append((n, p))
    return out


def under(path, root):
    """True when path is root or inside it."""
    path, root = os.path.realpath(path), os.path.realpath(root)
    return path == root or path.startswith(root.rstrip("/") + "/")


def fmt_time(sec):
    """'3:07', '1:02:03'; '' for None or a negative value."""
    if sec is None or sec < 0:
        return ""
    sec = int(sec)
    h, m, s = sec // 3600, sec // 60 % 60, sec % 60
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def watch_later_dir():
    state = os.environ.get("XDG_STATE_HOME") or os.path.expanduser("~/.local/state")
    return os.path.join(state, "mpv", "watch_later")


def resume_pos(path, wdir=None):
    """Where mpv will resume this file (save-position-on-quit), in seconds, or None. mpv names
    the file after the MD5 of the path it was given, upper-case hex."""
    name = hashlib.md5(path.encode("utf-8", "surrogateescape")).hexdigest().upper()
    try:
        with open(os.path.join(wdir or watch_later_dir(), name), encoding="utf-8",
                  errors="replace") as f:
            for line in f.read(4096).splitlines():
                if line.startswith("start="):
                    v = float(line[6:])
                    return v if v >= 1 else None
    except (OSError, ValueError):
        pass
    return None
