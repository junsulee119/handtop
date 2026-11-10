"""Theme files: list, safe import of a .handtop-theme (zip), export, duplicate, delete.

Import never trusts the zip: only the paths of the contract are unpacked (schema.allowed_files),
no absolute paths, no "..", no links, no encrypted entries, size limits per file and in total
(checked on the bytes actually read, not on what the zip claims), then the whole theme is checked
(theme.load) in a temporary folder and only moved into place when it has no errors. On any error
the import is refused and nothing changes."""
import json
import os
import re
import shutil
import stat
import tempfile
import zipfile

from . import guide
from . import schema as S
from .theme import BUILTIN_DIR, Problem, ThemeError, load

USER_DIR = os.path.join(os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share"),
                        "rg35xxh", "themes")
EXT = ".handtop-theme"


class ThemeExists(Exception):
    """A user theme with this id exists; import again with replace=True."""
    def __init__(self, theme_id):
        self.id = theme_id
        super().__init__(f"a theme with the id {theme_id!r} is already installed")


def list_themes(builtin_dir=BUILTIN_DIR, user_dir=USER_DIR):
    """[(id, path, is_builtin)], built-ins first. User folders with a reserved id are skipped."""
    out = []
    for d, builtin in ((builtin_dir, True), (user_dir, False)):
        try:
            names = sorted(os.listdir(d))
        except OSError:
            continue
        for n in names:
            p = os.path.join(d, n)
            if (not re.match(S.ID_RE, n) or not os.path.isdir(p) or os.path.islink(p)
                    or n.startswith(S.RESERVED_PREFIX) != builtin):
                continue
            out.append((n, p, builtin))
    return out


def find(theme_id, builtin_dir=BUILTIN_DIR, user_dir=USER_DIR):
    for tid, p, _b in list_themes(builtin_dir, user_dir):
        if tid == theme_id:
            return p
    return None


# ---- import ---------------------------------------------------------------------------------------
def _entries(zf, problems):
    """[(ZipInfo, path inside the theme)] for the files to unpack; problems collected."""
    infos = zf.infolist()
    if len(infos) > S.MAX_FILES:
        problems.append(Problem("error", "file", f"more than {S.MAX_FILES} files"))
        return []
    names = []
    for i in infos:
        n = i.filename
        if "\\" in n or n.startswith("/") or ":" in n.split("/")[0] or "\x00" in n:
            problems.append(Problem("error", n, "bad path in the zip"))
            continue
        parts = n.rstrip("/").split("/")
        if any(p in ("", ".", "..") for p in parts):
            problems.append(Problem("error", n, "bad path in the zip"))
            continue
        mode = i.external_attr >> 16
        if stat.S_ISLNK(mode):
            problems.append(Problem("error", n, "links are not allowed"))
            continue
        if i.flag_bits & 0x1:
            problems.append(Problem("error", n, "encrypted"))
            continue
        if not i.is_dir():
            names.append((i, n))
    # a zip of a folder ("my-theme/theme.json"): strip that one top folder
    if names and S.THEME_FILE not in (n for _i, n in names):
        tops = {n.split("/")[0] for _i, n in names}
        if len(tops) == 1 and all("/" in n for _i, n in names):
            top = tops.pop() + "/"
            names = [(i, n[len(top):]) for i, n in names]
    allowed = S.allowed_files()
    out, seen = [], set()
    for i, n in names:
        if n == S.GUIDE_FILE:
            continue                                # written on export, never read back
        if n not in allowed:
            problems.append(Problem("warning", n, "not part of a theme, ignored"))
            continue
        if n in seen:
            problems.append(Problem("error", n, "appears twice in the zip"))
            continue
        seen.add(n)
        if i.file_size > allowed[n][0]:
            problems.append(Problem("error", n, f"larger than {allowed[n][0] // 1024} KB"))
            continue
        out.append((i, n))
    if sum(i.file_size for i, _n in out) > S.MAX_TOTAL_BYTES:
        problems.append(Problem("error", "file", f"larger than {S.MAX_TOTAL_BYTES >> 20} MB unpacked"))
    return out


def _unpack(zf, entries, dest, problems):
    allowed = S.allowed_files()
    total = 0
    for info, rel in entries:
        limit = allowed[rel][0]
        target = os.path.join(dest, *rel.split("/"))
        os.makedirs(os.path.dirname(target), exist_ok=True)
        fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o644)
        size = 0
        with os.fdopen(fd, "wb") as out, zf.open(info) as src:
            while True:
                chunk = src.read(65536)
                if not chunk:
                    break
                size += len(chunk)
                total += len(chunk)
                if size > limit or total > S.MAX_TOTAL_BYTES:
                    problems.append(Problem("error", rel, "larger than allowed"))
                    return
                out.write(chunk)
        if size != info.file_size:
            problems.append(Problem("error", rel, "size does not match the zip's directory"))
            return


def import_theme(zip_path, user_dir=USER_DIR, builtin_dir=BUILTIN_DIR, replace=False, decode=True):
    """Install a .handtop-theme into user_dir/<id>/. Returns the loaded Theme (its .problems hold
    the warnings). Raises ThemeError (refused, nothing changed) or ThemeExists."""
    problems = []
    try:
        if os.path.getsize(zip_path) > S.MAX_ZIP_BYTES:
            raise ThemeError([Problem("error", "file", f"larger than {S.MAX_ZIP_BYTES >> 20} MB")])
        zf = zipfile.ZipFile(zip_path)
    except (OSError, zipfile.BadZipFile) as e:
        raise ThemeError([Problem("error", "file", f"not a theme file ({e})")]) from None
    os.makedirs(user_dir, exist_ok=True)
    tmp = tempfile.mkdtemp(prefix=".import-", dir=user_dir)
    try:
        with zf:
            entries = _entries(zf, problems)
            if not any(p.level == "error" for p in problems):
                try:
                    _unpack(zf, entries, tmp, problems)
                except (zipfile.BadZipFile, zipfile.LargeZipFile, OSError, EOFError, RuntimeError) as e:
                    problems.append(Problem("error", "file", f"damaged ({e})"))
        if any(p.level == "error" for p in problems):
            raise ThemeError(problems)
        t = load(tmp, builtin_dir, decode)
        if t.errors:
            raise ThemeError(t.problems)
        if t.id.startswith(S.RESERVED_PREFIX):
            raise ThemeError([Problem("error", "id", f"\"{S.RESERVED_PREFIX}…\" is kept for the built-in themes")])
        final = os.path.join(user_dir, t.id)
        if os.path.lexists(final) and not replace:
            raise ThemeExists(t.id)
        old = None
        if os.path.lexists(final):
            old = tempfile.mkdtemp(prefix=".old-", dir=user_dir)
            os.rename(final, os.path.join(old, "t"))
        os.rename(tmp, final)
        tmp = None
        if old:
            shutil.rmtree(old, ignore_errors=True)
        t2 = load(final, builtin_dir, False)
        t2.problems = problems + [p for p in t2.problems if p.level != "error"]
        return t2
    finally:
        if tmp:
            shutil.rmtree(tmp, ignore_errors=True)


# ---- export / duplicate / delete --------------------------------------------------------------------
def _theme_files(path):
    allowed = S.allowed_files()
    out = []
    for rel in allowed:
        f = os.path.join(path, *rel.split("/"))
        if os.path.isfile(f) and not os.path.islink(f):
            out.append(rel)
    return sorted(out, key=lambda r: (r != S.THEME_FILE, r))


def export_theme(path, dest, builtin_dir=BUILTIN_DIR):
    """Write the theme folder at path as a .handtop-theme zip (with GUIDE.md). Returns dest."""
    t = load(path, builtin_dir)
    if t.errors:
        raise ThemeError(t.problems)
    d = os.path.dirname(os.path.abspath(dest))
    os.makedirs(d, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".export-", dir=d)
    os.close(fd)
    try:
        with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zf:
            for rel in _theme_files(path):
                zf.write(os.path.join(path, *rel.split("/")), rel)
            zf.writestr(S.GUIDE_FILE, guide.generate())
        os.chmod(tmp, 0o644)                     # mkstemp makes it private; it is meant to be shared
        os.replace(tmp, dest)
    except BaseException:
        os.unlink(tmp)
        raise
    return dest


def duplicate(path, new_id, new_name, user_dir=USER_DIR, builtin_dir=BUILTIN_DIR):
    """Copy a theme (built-in or not) to user_dir/new_id with a new id and name."""
    if not re.match(S.ID_RE, new_id) or new_id.startswith(S.RESERVED_PREFIX):
        raise ValueError(f"not a usable theme id: {new_id!r}")
    dest = os.path.join(user_dir, new_id)
    if os.path.lexists(dest):
        raise ThemeExists(new_id)
    os.makedirs(user_dir, exist_ok=True)
    tmp = tempfile.mkdtemp(prefix=".dup-", dir=user_dir)
    try:
        for rel in _theme_files(path):
            out = os.path.join(tmp, *rel.split("/"))
            os.makedirs(os.path.dirname(out), exist_ok=True)
            shutil.copyfile(os.path.join(path, *rel.split("/")), out)
        f = os.path.join(tmp, S.THEME_FILE)
        with open(f, encoding="utf-8") as fh:
            data = json.load(fh)
        orig = data.get("name", "")
        data["id"], data["name"] = new_id, new_name
        data.pop("author", None)
        data["description"] = f"Based on {orig}."[:200] if orig else ""
        if not data["description"]:
            data.pop("description")
        with open(f, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, ensure_ascii=False)
            fh.write("\n")
        t = load(tmp, builtin_dir)
        if t.errors:
            raise ThemeError(t.problems)
        os.rename(tmp, dest)
        tmp = None
        with open(os.path.join(dest, S.GUIDE_FILE), "w", encoding="utf-8") as fh:
            fh.write(guide.generate())               # for whoever edits the copy
        return load(dest, builtin_dir)
    finally:
        if tmp:
            shutil.rmtree(tmp, ignore_errors=True)


def delete(theme_id, user_dir=USER_DIR):
    """Remove a user theme (never a built-in)."""
    if not re.match(S.ID_RE, theme_id) or theme_id.startswith(S.RESERVED_PREFIX):
        raise ValueError(f"not a user theme: {theme_id!r}")
    p = os.path.join(user_dir, theme_id)
    if os.path.islink(p):
        os.unlink(p)
    elif os.path.isdir(p):
        shutil.rmtree(p)
