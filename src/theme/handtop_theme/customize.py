"""What the Theme app's Duplicate screen does to a copy, and where theme files are found.

customize() edits a user theme's theme.json in place (the copy package.duplicate() made):
  accent / background   one of the presets below; changing either re-derives the theme from its
                        palette: the copied part colours ("colors") are dropped, so every part
                        follows the new colours (decision 2026-11-10), and a wallpaper image is
                        dropped with a new background (its colour is baked in)
  icons                 "dark" / "light": the base theme whose images the copy uses (its own
                        copied images are removed, "system" choices are kept)
  pointer               cursor size; text: font scale
Nothing here imports GTK, so it is tested like the rest of the package."""
import json
import os
import re
import shutil

from . import colors as C
from . import schema as S

# Background presets: the surfaces and text that go with each background colour.
BACKGROUNDS = {
    "#eceff4": dict(surface="#f8f9fb", surface_hi="#c9d6ee", border="#c9ced8", fg="#2b303b", fg_dim="#6b7385"),
    "#fafafa": dict(surface="#ffffff", surface_hi="#dcdcdc", border="#cdc7c2", fg="#2e3436", fg_dim="#77767b"),
    "#f6f0e6": dict(surface="#fffaf2", surface_hi="#e8dcc6", border="#d6c9b4", fg="#3a3228", fg_dim="#7a6e60"),
    "#e8f0ea": dict(surface="#f6faf7", surface_hi="#cfe0d4", border="#bfd0c4", fg="#26332b", fg_dim="#5f7266"),
    "#1a1e26": dict(surface="#2b3240", surface_hi="#2b3a55", border="#3a4456", fg="#e8eaee", fg_dim="#b8bcc4"),
    "#121212": dict(surface="#262626", surface_hi="#333333", border="#404040", fg="#ededed", fg_dim="#a8a8a8"),
    "#10243f": dict(surface="#1b3456", surface_hi="#25487a", border="#2e4c73", fg="#e6eef8", fg_dim="#a9bbd2"),
    "#221c2b": dict(surface="#332a40", surface_hi="#45385a", border="#4a3d5c", fg="#eee8f4", fg_dim="#b9aec6"),
}
ACCENTS = ("#3d68b0", "#2f6fd6", "#d70a53", "#c64600", "#e5a50a", "#26a269", "#2190a4", "#9141ac")
POINTERS = (24, 32, 48)
TEXT_SCALES = (1.0, 1.25)


def is_dark(c):
    r, g, b, _a = C.parse(c)
    return 0.299 * r + 0.587 * g + 0.114 * b < 128


def accent_fg(accent, bg):
    """The accent as text / outline on bg: lighter on dark backgrounds, darker on light ones."""
    return C.mix(accent, "#ffffff", 0.45) if is_dark(bg) else C.mix(accent, "#000000", 0.15)


def customize(path, accent=None, background=None, icons=None, pointer=None, text=None):
    """Apply the Duplicate screen's choices to the user theme folder at path (None = keep)."""
    f = os.path.join(path, S.THEME_FILE)
    with open(f, encoding="utf-8") as fh:
        data = json.load(fh)
    pal = data.setdefault("palette", {})
    if background is not None and background not in BACKGROUNDS:
        raise ValueError(f"not a background preset: {background}")
    if accent is not None and accent not in ACCENTS:
        raise ValueError(f"not an accent preset: {accent}")
    if icons is not None and icons not in S.BASES:
        raise ValueError(f"icons: {icons!r}")
    orig_base = data.get("base", "dark")
    new_bg = background is not None and background != pal.get("bg")
    if new_bg or (accent is not None and accent != pal.get("accent")):
        if new_bg:
            pal["bg"] = background
            pal.update(BACKGROUNDS[background])
            data["wallpaper"] = {"color": C.mix(background, BACKGROUNDS[background]["surface"], 0.35),
                                 "image": None,
                                 "mode": data.get("wallpaper", {}).get("mode", "center")}
            shutil.rmtree(os.path.join(path, "images"), ignore_errors=True)
            data.setdefault("gtk", {})["color_scheme"] = "prefer-dark" if is_dark(background) else "default"
        if accent is not None:
            pal["accent"] = accent
        if "accent" in pal and "bg" in pal:
            pal["accent_fg"] = accent_fg(pal["accent"], pal["bg"])
            pal["on_accent"] = "#ffffff"
        data.pop("colors", None)                       # every part follows the palette now
        try:
            os.remove(os.path.join(path, S.PREVIEW_FILE))
        except OSError:
            pass
    base = icons or (("dark" if is_dark(background) else "light") if new_bg else orig_base)
    if base != orig_base:                              # the other set of images: the base's
        data["base"] = base
        shutil.rmtree(os.path.join(path, "icons"), ignore_errors=True)
    if pointer is not None:
        if pointer not in POINTERS:
            raise ValueError(pointer)
        data.setdefault("cursor", {})["size"] = pointer
    if text is not None:
        if text not in TEXT_SCALES:
            raise ValueError(text)
        data.setdefault("fonts", {})["scale"] = text
    with open(f, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)
        fh.write("\n")


def id_from_name(name, taken):
    """A theme id for a name: a-z, 0-9 and -, unique among taken, never handtop-..."""
    base = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:34] or "theme"
    if base.startswith(S.RESERVED_PREFIX.rstrip("-")):
        base = "my-" + base
    base = base[:34].strip("-")
    tid, n = base, 2
    while tid in taken:
        tid, n = f"{base}-{n}", n + 1
    return tid


# ---- where theme files are -------------------------------------------------------------------------
def drives(media=None):
    """Mounted USB drives / SD cards: [(label, path)] (udisks mounts them at /media/<user>/<label>)."""
    media = media or os.path.join("/media", os.environ.get("USER") or os.path.basename(os.path.expanduser("~")))
    try:
        names = sorted(os.listdir(media))
    except OSError:
        return []
    return [(n, os.path.join(media, n)) for n in names if os.path.ismount(os.path.join(media, n))
            or os.path.isdir(os.path.join(media, n))]


def import_places(home=None, media=None):
    """[(label, folder)] searched for theme files: home, ~/Themes, ~/Downloads, each drive and its
    Themes folder."""
    home = home or os.path.expanduser("~")
    places = [("Home", home), ("Themes", os.path.join(home, "Themes")), ("Downloads", os.path.join(home, "Downloads"))]
    for label, p in drives(media):
        places += [(label, p), (label, os.path.join(p, "Themes"))]
    return places


def find_theme_files(places):
    """[(path, place label, size in bytes)] of *.handtop-theme files directly in each place."""
    out, seen = [], set()
    for label, folder in places:
        try:
            names = sorted(os.listdir(folder))
        except OSError:
            continue
        for n in names:
            p = os.path.join(folder, n)
            if n.endswith(".handtop-theme") and os.path.isfile(p) and os.path.realpath(p) not in seen:
                seen.add(os.path.realpath(p))
                out.append((p, label, os.path.getsize(p)))
    return out


def export_places(home=None, media=None):
    """[(label, folder)] a theme can be exported to: ~/Themes and each drive."""
    home = home or os.path.expanduser("~")
    return [("Themes folder (~/Themes)", os.path.join(home, "Themes"))] + \
           [(f"{label} (drive)", p) for label, p in drives(media)]


# ---- live preview of the Duplicate screen's choices ----------------------------------------------------
def preview_theme(src, bases, accent=None, background=None, icons=None, pointer=None, text=None):
    """A copy of the loaded Theme src as customize() would leave it, without writing anything:
    for the Duplicate screen's live preview. bases: {"dark": Theme, "light": Theme}."""
    import copy
    from .theme import derive
    t = copy.copy(src)
    t.palette, t.colors, t.images = dict(src.palette), dict(src.colors), dict(src.images)
    t.wallpaper, t.cursor, t.fonts = dict(src.wallpaper), dict(src.cursor), dict(src.fonts)
    new_bg = background is not None and background != src.palette.get("bg")
    if new_bg or (accent is not None and accent != src.palette.get("accent")):
        if new_bg:
            t.palette["bg"] = background
            t.palette.update(BACKGROUNDS[background])
            t.wallpaper = {"color": C.mix(background, BACKGROUNDS[background]["surface"], 0.35),
                           "image": None, "mode": src.wallpaper["mode"]}
        if accent is not None:
            t.palette["accent"] = accent
        t.palette["accent_fg"] = accent_fg(t.palette["accent"], t.palette["bg"])
        t.palette["on_accent"] = "#ffffff"
        t.colors = {k: derive(rule, t.palette) for k, (rule, _d, _n) in S.COLORS.items()}
    base = icons or (("dark" if is_dark(background) else "light") if new_bg else src.base)
    if base != src.base and base in bases:
        b = bases[base]
        t.base = base
        t.images = {k: (v if v == ("system",) else b.images[k]) for k, v in src.images.items()}
    if pointer is not None:
        t.cursor["size"] = pointer
    if text is not None:
        t.fonts["scale"] = text
    return t
