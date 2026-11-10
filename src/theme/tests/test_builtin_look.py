"""Step 2's promise, checked in step 1: the built-in Handtop themes render to the same look as
today's hand-written configs and palettes (overlay/, osk.py, rg35xxh-display,
rg35xxh-controller-screen, rg35xxh-osd.c). Compared rule by rule, not byte by byte; every
intended difference is listed with its reason."""
import ast
import os
import re

import pytest

from handtop_theme import colors as C
from handtop_theme import render, theme

from conftest import REPO

O = os.path.join(REPO, "overlay")
ICONS = "/usr/local/share/rg35xxh/icons"


def css_rules(text):
    """{(selector, property): value}, comments dropped, whitespace normalised, '-light' and the
    icon folder dropped from url()s (theme icons have one name; the folder is the render's)."""
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    text = re.sub(r"@import[^;]*;", "", text)
    out = {}
    for sel, body in re.findall(r"([^{}]+)\{([^{}]*)\}", text):
        sel = " ".join(sel.split())
        if sel.startswith("@"):
            continue
        for decl in body.split(";"):
            if ":" not in decl:
                continue
            k, v = decl.split(":", 1)
            v = " ".join(v.split())
            v = re.sub(r'url\("[^"]*/([^/"]+?)(-light)?\.png"\)', r'url("\1.png")', v)
            out[(sel, k.strip())] = v
    return out


def read(*p):
    with open(os.path.join(*p)) as f:
        return f.read()


@pytest.fixture(scope="module")
def rendered(builtins, tmp_path_factory):
    from conftest import StubOps
    out = {}
    for tid in ("handtop-dark", "handtop-light"):
        t = theme.load(os.path.join(builtins, tid), builtins)
        d = render.render(t, str(tmp_path_factory.mktemp(tid) / "theme"), StubOps())
        out[tid] = (t, d)
    return out


def compare(expected, got, extra_ok=(), differ_ok=()):
    for key, v in expected.items():
        if key in differ_ok:
            continue
        assert key in got, f"missing {key}"
        assert got[key] == v, f"{key}: {got[key]!r} != {v!r}"
    for key in got:
        if key not in expected:
            assert key in extra_ok, f"new rule {key} = {got[key]!r}"


# ---- Waybar -------------------------------------------------------------------------------------
WAYBAR_EXTRA = {("#custom-apps", "color")}   # dark: was inherited (#e8eaee), now explicit


def test_waybar_dark(rendered):
    t, d = rendered["handtop-dark"]
    compare(css_rules(read(O, "etc/xdg/waybar/style.css")), css_rules(read(d, "waybar.css")), WAYBAR_EXTRA)
    assert rendered["handtop-dark"][0].colors["taskbar.apps_fg"] == "#e8eaee"


def test_waybar_light(rendered):
    _t, d = rendered["handtop-light"]
    exp = css_rules(read(O, "etc/xdg/waybar/style.css"))
    exp.update(css_rules(read(O, "etc/xdg/waybar/style-light.css")))
    # light only swapped the power icon's image; the theme names one file for both
    exp.pop(("#custom-power", "background-image"))
    compare(exp, css_rules(read(d, "waybar.css")), WAYBAR_EXTRA)


# ---- wlogout ------------------------------------------------------------------------------------
HOVER = {(f"#{a}:hover", "background-image") for a in ("sleep", "reboot", "logout", "shutdown", "saver")}


def test_wlogout_dark(rendered):
    _t, d = rendered["handtop-dark"]
    exp = css_rules(read(O, "etc/wlogout/style.css"))
    got = css_rules(read(d, "wlogout.css"))
    # dark highlight icons: power-<a>-focus.png in both
    compare(exp, got)


def test_wlogout_light(rendered):
    _t, d = rendered["handtop-light"]
    # light had no hover images (icons keep their colour): the theme's -focus slots are the same
    # files, so the new hover rules show the same picture
    compare(css_rules(read(O, "etc/wlogout/style-light.css")), css_rules(read(d, "wlogout.css")), HOVER)


# ---- nwg-drawer -----------------------------------------------------------------------------------
LABELS = {("label, button, button label, entry", k) for k in ("color", "text-shadow", "-gtk-icon-shadow")}


@pytest.mark.parametrize("tid,src,extra", [
    ("handtop-dark", "handtop-dark.css", LABELS | {("entry", "color")}),   # dark: explicit, same colour
    ("handtop-light", "handtop-light.css", set()),
])
def test_drawer(rendered, tid, src, extra):
    _t, d = rendered[tid]
    compare(css_rules(read(O, "etc/xdg/nwg-drawer", src)), css_rules(read(d, "nwg-drawer.css")), extra)


# ---- key = value configs --------------------------------------------------------------------------
def kv(text, sep="="):
    out = {}
    section = ""
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("["):
            section = line
            continue
        k, v = line.split(sep, 1)
        out[(section, k.strip())] = v.strip()
    return out


@pytest.mark.parametrize("tid,src", [("handtop-dark", "config"), ("handtop-light", "config-light")])
def test_mako(rendered, tid, src):
    assert kv(read(rendered[tid][1], "mako.conf")) == kv(read(O, "etc/xdg/mako", src))


@pytest.mark.parametrize("tid,src", [("handtop-dark", "Handtop"), ("handtop-light", "Handtop-Light")])
def test_labwc(rendered, tid, src):
    assert (kv(read(rendered[tid][1], "labwc/themerc"), ":")
            == kv(read(O, "usr/share/themes", src, "labwc/themerc"), ":"))


@pytest.mark.parametrize("tid", ["handtop-dark", "handtop-light"])   # one dark terminal for both
def test_foot(rendered, tid):
    assert kv(read(rendered[tid][1], "foot.ini")) == kv(read(O, "etc/xdg/foot/foot.ini"))


# ---- palettes in code (moved into the theme in step 6) -------------------------------------------------
def _module_values(path, names):
    """Evaluate simple module-level assignments of a Python file without importing it."""
    src = read(path)
    ns = {}
    for node in ast.parse(src).body:
        if isinstance(node, ast.Assign):
            tg = [t.id for t in node.targets if isinstance(t, ast.Name)]
            tg += [e.id for t in node.targets if isinstance(t, ast.Tuple) for e in t.elts]
            if set(tg) & set(names) and not (isinstance(node.value, ast.Call) and
                                             getattr(node.value.func, "id", "") == "_theme"):
                try:
                    exec(compile(ast.Module([node], []), path, "exec"), {"dict": dict}, ns)
                except NameError:
                    pass
        elif isinstance(node, ast.FunctionDef) and node.name in names:
            exec(compile(ast.Module([node], []), path, "exec"), {"dict": dict}, ns)
    return ns


def close(hexcol, rgb):
    """Theme hex vs a float tuple from the code: within 1/255 per channel (rounding)."""
    got = C.parse(hexcol)
    want = [round(x * 255) for x in rgb] + ([] if len(rgb) == 4 else [255])
    return all(abs(a - b) <= 1 for a, b in zip(got, want))


@pytest.mark.parametrize("tid,key", [("handtop-dark", "dark"), ("handtop-light", "light")])
def test_osk(rendered, tid, key):
    pal = _module_values(os.path.join(REPO, "src/inputd/rg35xxh_inputd/osk.py"), ["PALETTES"])["PALETTES"][key]
    t = rendered[tid][0]
    assert {k: t.colors[f"osk.{k}"] for k in pal} == pal
    assert len(pal) == sum(1 for k in t.colors if k.startswith("osk."))


@pytest.mark.parametrize("tid,light", [("handtop-dark", False), ("handtop-light", True)])
def test_display(rendered, tid, light):
    pal = _module_values(os.path.join(O, "usr/local/bin/rg35xxh-display"), ["palette"])["palette"](light)
    t = rendered[tid][0]
    assert len(pal) == sum(1 for k in t.colors if k.startswith("display."))
    for k, v in pal.items():
        assert close(t.colors[f"display.{k}"], v), k


@pytest.mark.parametrize("tid,key", [("handtop-dark", "dark"), ("handtop-light", "light")])
def test_status_screen(rendered, tid, key):
    names = ["BG", "BODY", "BODY_EDGE", "BODY_SHADE", "PART", "PART_EDGE", "LABEL_COL", "LIT", "LIT_EDGE",
             "PALETTES", "TEXT", "DIM", "OK", "WARN"]
    v = _module_values(os.path.join(O, "usr/local/bin/rg35xxh-controller-screen"), names)
    pal, t = v["PALETTES"][key], rendered[tid][0]
    assert t.status_style == ("solid" if key == "dark" else "hologram")
    for k, col in pal.items():
        if k == "FACE":
            for b in "XYAB":
                assert close(t.colors[f"status.face_{b.lower()}"], col[b]), b
        elif col is None:
            assert t.colors[f"status.{k.lower()}"] is None
        else:
            assert close(t.colors[f"status.{k.lower()}"], col), k
    bg = (0.875, 0.894, 0.925) if key == "light" else v["BG"]       # light: the light wallpaper's
    assert close(t.colors["status.bg"], bg)
    for k in ("TEXT", "DIM", "OK", "WARN"):
        assert close(t.colors[f"status.{k.lower()}"], v[k]), k


@pytest.mark.parametrize("tid", ["handtop-dark", "handtop-light"])   # same bar in both
def test_osd(rendered, tid):
    src = read(REPO, "src/osd/rg35xxh-osd.c")
    t = rendered[tid][0]

    def argb(x):
        x = int(x, 16)
        return "#%06x" % (x & 0xFFFFFF) + ("" if x >> 24 == 0xFF else "%02x" % (x >> 24))
    assert t.colors["osd.bg"] == argb(re.search(r"#define BG 0x([0-9A-Fa-f]{8})u", src).group(1))
    assert t.colors["osd.text"] == argb(re.search(r"#define TEXT 0x([0-9A-Fa-f]{8})u", src).group(1))
    for kind, border, level in re.findall(r'\{"(\w+)",\s*0x([0-9A-Fa-f]{8})u,\s*0x([0-9A-Fa-f]{8})u\}', src):
        assert t.colors[f"osd.{kind}_border"] == argb(border)
        assert t.colors[f"osd.{kind}_level"] == argb(level)


def test_wallpapers(rendered):
    for tid, col in (("handtop-dark", "#1e2430"), ("handtop-light", "#dfe4ec")):
        t, d = rendered[tid]
        assert t.wallpaper["color"] == col and os.path.exists(os.path.join(d, "wallpaper.png"))
        assert f"'{col}'" in read(O, "usr/local/bin/rg35xxh-themed")
