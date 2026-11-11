"""Checks for a theme's own fonts and CSS (schema.FONT_ROLES, schema.CSS_PARTS).

Fonts are read by every app once installed, so a theme's font file is checked before it is ever
installed: TrueType / OpenType signature (no collections), size, and (where fontconfig's fc-scan
is installed, as on the device) that fontconfig reads it as one font family, the name theme.json
gives (one face, or the named instances of one variable font). CSS is plain text added after Handtop's own rules: UTF-8, no @import, no url() (a theme
must not pull in files from elsewhere), no backslash escapes (which could spell either)."""
import os
import re
import shutil
import subprocess

FONT_MAGIC = (b"\x00\x01\x00\x00", b"OTTO", b"true")
_BAD_CSS = re.compile(r"@import|url\s*\(|\\", re.I)
_COMMENT = re.compile(r"/\*.*?\*/", re.S)


def font_problem(path):
    """None if path looks like a single TrueType / OpenType font, else a message."""
    try:
        with open(path, "rb") as f:
            head = f.read(4)
    except OSError as e:
        return f"cannot be read ({e.strerror})"
    if head not in FONT_MAGIC:
        return "not a TrueType / OpenType font (font collections are not allowed)"
    return None


def font_families(path, timeout=10):
    """Family names fontconfig reads from path: [] if it reads no face, None if fc-scan is not
    installed (then the family cannot be checked here)."""
    if not shutil.which("fc-scan"):
        return None
    try:
        r = subprocess.run(["fc-scan", "--format", "%{family}\\n", path], capture_output=True,
                           text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired):
        return []
    if r.returncode != 0:
        return []
    faces = [line for line in r.stdout.splitlines() if line.strip()]
    # one face, or the named instances of one variable font (all of the same family)
    if not faces or len(faces) > 64:
        return []
    fams = [[n.strip() for n in f.split(",") if n.strip()] for f in faces]
    if any(f != fams[0] for f in fams):
        return []
    return fams[0]


def css_problem(path):
    """None if path is acceptable theme CSS, else a message."""
    try:
        with open(path, "rb") as f:
            data = f.read()
        text = data.decode("utf-8")
    except OSError as e:
        return f"cannot be read ({e.strerror})"
    except UnicodeDecodeError:
        return "not UTF-8 text"
    if "\x00" in text:
        return "not text"
    # GTK reads a comment as white space ("url/**/(" is a url): check the text without them
    bare = _COMMENT.sub(" ", text)
    if "/*" in bare:
        return "a comment is not closed"
    m = _BAD_CSS.search(bare)
    if m:
        return f"{m.group(0)!r} is not allowed (no @import, url() or backslash escapes)"
    return None


def read_css(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def text_problem(path):
    try:
        with open(path, "rb") as f:
            f.read().decode("utf-8")
    except OSError as e:
        return f"cannot be read ({e.strerror})"
    except UnicodeDecodeError:
        return "not UTF-8 text"
    return None


def plain_file(path):
    return os.path.isfile(path) and not os.path.islink(path)
