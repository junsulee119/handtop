"""Read, check and resolve a theme folder (an unpacked .handtop-theme).

load() returns a Theme whose every colour, image slot and setting is filled in: the theme's own
values first, then the rules of the contract (schema.py):
  palette colour missing   -> the base Handtop theme's (handtop-dark / handtop-light)
  part colour missing      -> derived from the theme's own palette (schema.COLORS rules)
  image missing            -> generated from its parent slot if that is the theme's own (shake
                              frames, small app icons), otherwise the base Handtop theme's
  wallpaper image missing  -> none (an image is never inherited: Handtop's has its colour baked in)
Problems are collected, not raised: errors make a theme unusable (import refused, apply refused),
warnings are shown and ignored."""
import json
import os
import re

from . import colors as C
from . import extras as X
from . import pngcheck
from . import schema as S

BUILTIN_DIR = "/usr/share/rg35xxh/themes"
_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9 ._+-]{0,63}\Z")    # font / GTK / cursor theme names
_CTRL = re.compile(r"[\x00-\x1f\x7f]")
TOP_KEYS = ("schema", "id", "name", "base", "author", "description", "palette", "colors",
            "wallpaper", "gtk", "cursor", "fonts", "borders", "icons", "names")


class Problem:
    def __init__(self, level, where, message):
        self.level, self.where, self.message = level, where, message

    def __repr__(self):
        return f"{self.level}: {self.where}: {self.message}"

    __str__ = __repr__


class ThemeError(Exception):
    """A theme that cannot be used; .problems lists why."""
    def __init__(self, problems):
        self.problems = [p for p in problems if p.level == "error"]
        super().__init__("; ".join(f"{p.where}: {p.message}" for p in self.problems))


class Theme:
    """A resolved theme. images: slot -> ("file", path) | ("generate", parent path) | ("system",)."""
    def __init__(self, path):
        self.path = path
        self.id = self.name = self.base = None
        self.author = self.description = ""
        self.palette, self.colors, self.images, self.names = {}, {}, {}, {}
        self.wallpaper = {"color": None, "image": None, "mode": "center"}
        self.borders = 1
        self.gtk, self.cursor, self.fonts = {}, {}, {}
        self.cursor_images = {}     # shape -> path (the theme's own pointer, 48 px art)
        self.font_files = {}        # role -> path (the theme's own fonts)
        self.css = {}               # part -> CSS text added after Handtop's rules
        self.own = set()            # slots this theme supplies itself
        self.problems = []

    @property
    def errors(self):
        return [p for p in self.problems if p.level == "error"]

    def is_builtin(self):
        return self.id.startswith(S.RESERVED_PREFIX)


# ---- theme.json -----------------------------------------------------------------------------------
def read_json(path, problems):
    f = os.path.join(path, S.THEME_FILE)
    try:
        if os.path.getsize(f) > S.MAX_JSON_BYTES:
            problems.append(Problem("error", S.THEME_FILE, "too large"))
            return None
        with open(f, encoding="utf-8") as fh:
            data = json.load(fh)
    except FileNotFoundError:
        problems.append(Problem("error", S.THEME_FILE, "missing"))
        return None
    except (OSError, UnicodeDecodeError, ValueError) as e:
        problems.append(Problem("error", S.THEME_FILE, f"not valid JSON ({e})"))
        return None
    except RecursionError:
        problems.append(Problem("error", S.THEME_FILE, "nested too deeply"))
        return None
    if _depth(data) > S.MAX_JSON_DEPTH:
        problems.append(Problem("error", S.THEME_FILE, "nested too deeply"))
        return None
    if not isinstance(data, dict):
        problems.append(Problem("error", S.THEME_FILE, "must be a JSON object"))
        return None
    return data


def _depth(data):
    """How deeply lists and objects nest (without recursion)."""
    deepest, todo = 0, [(data, 1)]
    while todo:
        v, d = todo.pop()
        if isinstance(v, (dict, list)):
            deepest = max(deepest, d)
            todo.extend((x, d + 1) for x in (v.values() if isinstance(v, dict) else v))
    return deepest


def _text(v, maxlen):
    return isinstance(v, str) and 0 < len(v) <= maxlen and not _CTRL.search(v)


def validate(data):
    """Check theme.json's content against the contract. Returns a list of Problems."""
    P = []

    def err(where, msg):
        P.append(Problem("error", where, msg))

    def warn(where, msg):
        P.append(Problem("warning", where, msg))

    def section(key):
        v = data.get(key, {})
        if not isinstance(v, dict):
            err(key, "must be an object")
            return {}
        return v

    for k in data:
        if k not in TOP_KEYS:
            warn(k, "unknown field, ignored")
    schema = data.get("schema")
    if not isinstance(schema, int) or isinstance(schema, bool) or schema < 1:
        err("schema", "missing or not a positive whole number")
    elif schema > S.SCHEMA:
        err("schema", f"made for a newer Handtop (schema {schema}; this one reads {S.SCHEMA})")
    tid = data.get("id")
    if not isinstance(tid, str) or not re.match(S.ID_RE, tid):
        err("id", "1-40 characters: a-z, 0-9 and -, starting with a letter or digit")
    if not _text(data.get("name"), S.NAME_MAX):
        err("name", f"1-{S.NAME_MAX} characters, one line")
    if data.get("base") not in S.BASES:
        err("base", "must be \"dark\" or \"light\"")
    for k in ("author", "description"):
        if k in data and not _text(data[k], 200):
            warn(k, "1-200 characters, one line; ignored")

    for k, v in section("palette").items():
        if k not in S.PALETTE:
            warn(f"palette.{k}", "unknown colour, ignored")
        elif not C.valid(v):
            err(f"palette.{k}", f"{v!r} is not #rrggbb or #rrggbbaa")
    for k, v in section("colors").items():
        if k not in S.COLORS:
            warn(f"colors.{k}", "unknown colour, ignored")
        elif v is None and S.COLORS[k][2]:
            pass
        elif not C.valid(v):
            err(f"colors.{k}", f"{v!r} is not #rrggbb or #rrggbbaa"
                + (" or null" if S.COLORS[k][2] else ""))

    wp = section("wallpaper")
    for k in wp:
        if k not in ("color", "image", "mode"):
            warn(f"wallpaper.{k}", "unknown field, ignored")
    if "color" in wp and not C.valid(wp["color"]):
        err("wallpaper.color", "not #rrggbb")
    if "image" in wp and wp["image"] not in (None, S.WALLPAPER_FILE):
        err("wallpaper.image", f"must be \"{S.WALLPAPER_FILE}\" or null")
    if "mode" in wp and wp["mode"] not in S.WALLPAPER_MODES:
        err("wallpaper.mode", "one of " + ", ".join(S.WALLPAPER_MODES))


    gtk = section("gtk")
    if "color_scheme" in gtk and gtk["color_scheme"] not in S.GTK_SCHEMES:
        err("gtk.color_scheme", "one of " + ", ".join(S.GTK_SCHEMES))
    for k in ("theme", "icon_theme"):
        if k in gtk and not (isinstance(gtk[k], str) and _NAME.match(gtk[k])):
            err(f"gtk.{k}", "not a theme name")

    cur = section("cursor")
    if "theme" in cur and not (isinstance(cur["theme"], str) and _NAME.match(cur["theme"])):
        err("cursor.theme", "not a cursor theme name")
    for k in cur:
        if k not in ("theme", "size", "hotspots"):
            warn(f"cursor.{k}", "unknown field, ignored")
    hs = cur.get("hotspots", {})
    if not isinstance(hs, dict):
        err("cursor.hotspots", "must be an object")
    else:
        for k, v in hs.items():
            if k not in S.CURSOR_SHAPES:
                warn(f"cursor.hotspots.{k}", "unknown pointer shape, ignored")
            elif not (isinstance(v, list) and len(v) == 2
                      and all(isinstance(n, int) and not isinstance(n, bool) and 0 <= n < S.CURSOR_ART for n in v)):
                err(f"cursor.hotspots.{k}", f"[x, y], whole numbers 0-{S.CURSOR_ART - 1}")
    if "size" in cur:
        v = cur["size"]
        if not isinstance(v, int) or isinstance(v, bool) or not S.CURSOR_SIZES[0] <= v <= S.CURSOR_SIZES[1]:
            err("cursor.size", f"a whole number {S.CURSOR_SIZES[0]}-{S.CURSOR_SIZES[1]}")

    if "borders" in data:
        v = data["borders"]
        if not isinstance(v, int) or isinstance(v, bool) or not S.BORDERS[0] <= v <= S.BORDERS[1]:
            err("borders", f"a whole number {S.BORDERS[0]}-{S.BORDERS[1]}")

    fonts = section("fonts")
    for k in ("ui", "mono"):
        if k in fonts and not (isinstance(fonts[k], str) and _NAME.match(fonts[k])):
            err(f"fonts.{k}", "not a font name")
    if "scale" in fonts:
        v = fonts["scale"]
        if not isinstance(v, (int, float)) or isinstance(v, bool) or not S.FONT_SCALES[0] <= v <= S.FONT_SCALES[1]:
            err("fonts.scale", f"a number {S.FONT_SCALES[0]}-{S.FONT_SCALES[1]}")

    for k, v in section("icons").items():
        if k not in S.IMAGE_SLOTS:
            warn(f"icons.{k}", "unknown slot, ignored")
        elif v != "system":
            err(f"icons.{k}", "the only value allowed here is \"system\" (images are files, "
                f"this one is {S.slot_file(k)})")
        elif k not in S.SYSTEM_OK:
            err(f"icons.{k}", "this slot has no system icon")

    for k, v in section("names").items():
        if k not in S.NAMEABLE:
            warn(f"names.{k}", "only default apps can be renamed; ignored")
        elif v != "system" and not _text(v, S.APP_NAME_MAX):
            err(f"names.{k}", f"1-{S.APP_NAME_MAX} characters, one line")
    return P


# ---- images ---------------------------------------------------------------------------------------
def check_image(path, rel, want, max_bytes, decode=False):
    """Problems with one image file (exact size when want = (w, h))."""
    try:
        if os.path.islink(path) or not os.path.isfile(path):
            return [Problem("error", rel, "not a plain file")]
        if os.path.getsize(path) > max_bytes:
            return [Problem("error", rel, f"larger than {max_bytes // 1024} KB")]
        with open(path, "rb") as f:
            data = f.read()
        # icons: anything up to 1024 px is read so a wrong size gets a clear message
        limit = (1024, 1024) if want else S.MAX_WALLPAPER_SIZE
        w, h = pngcheck.check(data, limit)
        if want and (w, h) != tuple(want):
            return [Problem("error", rel, f"is {w}x{h}, must be {want[0]}x{want[1]}")]
        if decode:
            pngcheck.decode(path)
    except pngcheck.BadPNG as e:
        return [Problem("error", rel, str(e))]
    except OSError as e:
        return [Problem("error", rel, f"cannot be read ({e.strerror})")]
    return []


def stray_files(path):
    """Files in a theme folder that are not part of the contract (relative paths)."""
    allowed = set(S.allowed_files()) | {S.GUIDE_FILE}
    out = []
    for root, dirs, files in os.walk(path):
        for f in files:
            rel = os.path.relpath(os.path.join(root, f), path).replace(os.sep, "/")
            if rel not in allowed:
                out.append(rel)
    return sorted(out)


# ---- resolving ------------------------------------------------------------------------------------
def derive(rule, palette):
    def val(x):
        return x if x.startswith("#") else palette[x]
    if isinstance(rule, str):
        return val(rule)
    if rule[0] == "mix":
        return C.mix(val(rule[1]), val(rule[2]), rule[3])
    if rule[0] == "alpha":
        return C.with_alpha(val(rule[1]), rule[2])
    raise ValueError(rule)


def load(path, builtin_dir=BUILTIN_DIR, decode=False, _stack=()):
    """Load and resolve the theme folder at path. Never raises for a bad theme: see .problems."""
    t = Theme(path)
    P = t.problems
    data = read_json(path, P)
    if data is None:
        return t
    P += validate(data)
    if t.errors:                                  # list the image problems too, in one go
        for slot, (w, h, _kind) in S.IMAGE_SLOTS.items():
            f = os.path.join(path, S.slot_file(slot))
            if os.path.lexists(f):
                P.extend(check_image(f, S.slot_file(slot), (w, h), S.MAX_ICON_BYTES))
        return t
    t.id, t.name, t.base = data["id"], data["name"], data["base"]
    # a bad author / description was warned about as ignored: it is ignored (the app shows text only)
    t.author, t.description = (data[k] if _text(data.get(k), 200) else "" for k in ("author", "description"))
    base_id = S.RESERVED_PREFIX + t.base
    is_base = t.id == base_id
    base = None
    if not is_base:
        if base_id in _stack:
            P.append(Problem("error", "base", "loops"))
            return t
        base = load(os.path.join(builtin_dir, base_id), builtin_dir, False, _stack + (t.id,))
        if base.errors:
            P.append(Problem("error", "base", f"built-in theme {base_id} is broken: {base.errors[0]}"))
            return t

    own_pal = {k: v for k, v in data.get("palette", {}).items() if k in S.PALETTE}
    t.palette = dict(base.palette) if base else {}
    t.palette.update(own_pal)
    for k in S.PALETTE:
        if k not in t.palette:
            P.append(Problem("error", f"palette.{k}", "missing (a base theme must set every colour)"))
    if t.errors:
        return t
    own_col = {k: v for k, v in data.get("colors", {}).items() if k in S.COLORS}
    for k, (rule, _d, _n) in S.COLORS.items():
        t.colors[k] = own_col[k] if k in own_col else derive(rule, t.palette)

    wp = data.get("wallpaper", {})
    # wallpaper colour missing: the theme's own background if it sets one, else the base's
    default_wp = base.wallpaper["color"] if base and "bg" not in own_pal else t.palette["bg"]
    # swaybg takes #rrggbb only: a colour's alpha (its own or the palette's) is dropped
    t.wallpaper = {"color": wp.get("color", default_wp)[:7],
                   "mode": wp.get("mode", base.wallpaper["mode"] if base else "center"),
                   "image": None}
    if wp.get("image"):
        f = os.path.join(path, S.WALLPAPER_FILE)
        if not os.path.exists(f):
            P.append(Problem("error", "wallpaper.image", f"{S.WALLPAPER_FILE} is missing"))
        else:
            P.extend(check_image(f, S.WALLPAPER_FILE, None, S.MAX_WALLPAPER_BYTES, decode))
            t.wallpaper["image"] = f
    t.borders = data.get("borders", base.borders if base else 1)
    for attr, defaults in (("gtk", {"color_scheme": "prefer-dark" if t.base == "dark" else "default",
                                    "theme": "Adwaita", "icon_theme": "Adwaita"}),
                           ("cursor", {"theme": "Adwaita", "size": 24}),
                           ("fonts", {"ui": "Noto Sans", "mono": "Noto Sans Mono", "scale": 1.0})):
        val = dict(getattr(base, attr) if base else defaults)
        val.update({k: v for k, v in data.get(attr, {}).items() if k in defaults})
        setattr(t, attr, val)
    t.names = {k: v for k, v in data.get("names", {}).items() if k in S.NAMEABLE}
    _extras(t, data, decode)

    system = {k for k, v in data.get("icons", {}).items() if v == "system" and k in S.SYSTEM_OK}
    for slot, (w, h, kind) in S.IMAGE_SLOTS.items():
        rel = S.slot_file(slot)
        f = os.path.join(path, rel)
        if slot in system:
            t.images[slot] = ("system",)
            if os.path.exists(f):
                P.append(Problem("warning", rel, "ignored: the slot is set to \"system\""))
        elif os.path.lexists(f):
            P.extend(check_image(f, rel, (w, h), S.MAX_ICON_BYTES, decode))
            t.images[slot] = ("file", f)
            t.own.add(slot)
    for slot, (w, h, kind) in S.IMAGE_SLOTS.items():
        if slot in t.images:
            continue
        par = S.parent(slot)
        if par and t.images.get(par, (None,))[0] == "system":
            t.images[slot] = ("system",)
        elif par and par in t.own:
            t.images[slot] = ("generate", t.images[par][1])
        elif base is not None:
            t.images[slot] = base.images[slot]
        elif kind == "generated" and par in t.images:
            t.images[slot] = ("generate", t.images[par][1])
        else:
            P.append(Problem("error", S.slot_file(slot), "missing (a base theme must have every image)"))
    if os.path.exists(os.path.join(path, S.PREVIEW_FILE)):
        P.extend(check_image(os.path.join(path, S.PREVIEW_FILE), S.PREVIEW_FILE, S.PREVIEW_SIZE,
                             S.MAX_ICON_BYTES, decode))
    for rel in stray_files(path):
        P.append(Problem("warning", rel, "not part of a theme, ignored"))
    return t


def _extras(t, data, decode):
    """The theme's own pointer, fonts and CSS (never inherited from the base theme)."""
    P, path = t.problems, t.path
    for shape in S.CURSOR_SHAPES:
        rel = S.cursor_file(shape)
        f = os.path.join(path, rel)
        if os.path.lexists(f):
            P.extend(check_image(f, rel, (S.CURSOR_ART, S.CURSOR_ART), S.MAX_ICON_BYTES, decode))
            t.cursor_images[shape] = f
    if t.cursor_images:
        own = data.get("cursor", {}).get("hotspots", {})
        t.cursor["hotspots"] = {s: tuple(own.get(s, S.CURSOR_SHAPES[s][1])) for s in t.cursor_images}
        t.cursor["theme"] = S.CURSOR_SET_PREFIX + t.id
        if "theme" in data.get("cursor", {}):
            P.append(Problem("warning", "cursor.theme", "ignored: the theme has its own pointer images"))
    for role in S.FONT_ROLES:
        found = [rel for rel in S.font_files(role) if os.path.lexists(os.path.join(path, rel))]
        if len(found) > 1:
            P.append(Problem("error", found[1], f"only one {role} font (.ttf or .otf)"))
            continue
        if not found:
            continue
        rel, f = found[0], os.path.join(path, found[0])
        if not X.plain_file(f):
            P.append(Problem("error", rel, "not a plain file"))
            continue
        if os.path.getsize(f) > S.MAX_FONT_BYTES:
            P.append(Problem("error", rel, f"larger than {S.MAX_FONT_BYTES >> 20} MB"))
            continue
        msg = X.font_problem(f)
        if msg:
            P.append(Problem("error", rel, msg))
            continue
        name = data.get("fonts", {}).get(role)
        if not name:
            P.append(Problem("error", f"fonts.{role}", f"must name the family of {rel}"))
            continue
        if decode:
            fams = X.font_families(f)
            if fams == []:
                P.append(Problem("error", rel, "fontconfig cannot read it as one font"))
                continue
            if fams is not None and name not in fams:
                P.append(Problem("error", f"fonts.{role}",
                                 f"{name!r} is not the family of {rel} ({', '.join(fams)})"))
                continue
        t.font_files[role] = f
    lic = os.path.join(path, S.FONT_LICENSE_FILE)
    if os.path.lexists(lic):
        msg = None if X.plain_file(lic) else "not a plain file"
        msg = msg or X.text_problem(lic)
        if msg:
            P.append(Problem("error", S.FONT_LICENSE_FILE, msg))
    elif t.font_files:
        P.append(Problem("warning", S.FONT_LICENSE_FILE,
                         "missing: say which licence lets the fonts be shared"))
    for part in S.CSS_PARTS:
        rel = S.css_file(part)
        f = os.path.join(path, rel)
        if not os.path.lexists(f):
            continue
        msg = None if X.plain_file(f) else "not a plain file"
        if not msg and os.path.getsize(f) > S.MAX_CSS_BYTES:
            msg = f"larger than {S.MAX_CSS_BYTES >> 10} KB"
        msg = msg or X.css_problem(f)
        if msg:
            P.append(Problem("error", rel, msg))
        else:
            t.css[part] = X.read_css(f)


def check(path, builtin_dir=BUILTIN_DIR, decode=False):
    """load() that raises ThemeError when the theme cannot be used."""
    t = load(path, builtin_dir, decode)
    if t.errors:
        raise ThemeError(t.problems)
    return t
