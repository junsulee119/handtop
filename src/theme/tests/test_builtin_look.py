"""The built-in Handtop themes render to the same look as Handtop v0.3.9: its hand-written
configs and the palettes it had in code, frozen in tests/reference/ (see its README). Compared
rule by rule, not byte by byte; every intended difference is listed with its reason."""
import json
import os
import re

import pytest

from handtop_theme import colors as C
from handtop_theme import render, theme

HERE = os.path.dirname(os.path.abspath(__file__))
REF = os.path.join(HERE, "reference")


def read(*p):
    with open(os.path.join(*p)) as f:
        return f.read()


def css_rules(text):
    """{(selector, property): value}, comments and @import dropped, whitespace normalised,
    '-light' and the folder dropped from url()s (a theme's icons have one name; the folder is the
    render's)."""
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    text = re.sub(r"@import[^;]*;", "", text)
    out = {}
    for sel, body in re.findall(r"([^{}]+)\{([^{}]*)\}", text):
        sel = " ".join(sel.split())
        for decl in body.split(";"):
            if ":" not in decl:
                continue
            k, v = decl.split(":", 1)
            v = " ".join(v.split())
            v = re.sub(r'url\("[^"]*/([^/"]+?)(-light)?\.png"\)', r'url("\1.png")', v)
            out[(sel, k.strip())] = v
    return out


@pytest.fixture(scope="module")
def rendered(builtins, tmp_path_factory):
    from conftest import StubOps
    out = {}
    for tid in ("handtop-dark", "handtop-light"):
        t = theme.load(os.path.join(builtins, tid), builtins)
        d = render.render(t, str(tmp_path_factory.mktemp(tid) / "theme"), StubOps())
        out[tid] = (t, d)
    return out


@pytest.fixture(scope="module")
def palettes():
    with open(os.path.join(REF, "palettes-v0.3.9.json")) as f:
        return json.load(f)


def compare(expected, got, extra_ok=()):
    for key, v in expected.items():
        assert key in got, f"missing {key}"
        assert got[key] == v, f"{key}: {got[key]!r} != {v!r}"
    for key in got:
        if key not in expected:
            assert key in extra_ok, f"new rule {key} = {got[key]!r}"


# ---- Waybar -------------------------------------------------------------------------------------
WAYBAR_EXTRA = {("#custom-apps", "color")}   # dark: was inherited (#e8eaee), now explicit


def test_waybar_dark(rendered):
    t, d = rendered["handtop-dark"]
    compare(css_rules(read(REF, "waybar-style.css")), css_rules(read(d, "waybar.css")), WAYBAR_EXTRA)
    assert t.colors["taskbar.apps_fg"] == "#e8eaee"


def test_waybar_light(rendered):
    _t, d = rendered["handtop-light"]
    exp = css_rules(read(REF, "waybar-style.css"))
    exp.update(css_rules(read(REF, "waybar-style-light.css")))
    # light only swapped the power icon's image; the theme names one file for both
    exp.pop(("#custom-power", "background-image"))
    compare(exp, css_rules(read(d, "waybar.css")), WAYBAR_EXTRA)


# ---- wlogout ------------------------------------------------------------------------------------
HOVER = {(f"#{a}:hover", "background-image") for a in ("sleep", "reboot", "logout", "shutdown", "saver")}


def test_wlogout_dark(rendered):
    compare(css_rules(read(REF, "wlogout-style.css")), css_rules(read(rendered["handtop-dark"][1], "wlogout.css")))


def test_wlogout_light(rendered):
    # light had no hover images (icons keep their colour): the theme's -focus slots are the same
    # files, so the new hover rules show the same picture
    compare(css_rules(read(REF, "wlogout-style-light.css")),
            css_rules(read(rendered["handtop-light"][1], "wlogout.css")), HOVER)


# ---- nwg-drawer -----------------------------------------------------------------------------------
# dark: label / entry colours explicit, the same as GTK gave them (#eeeeee); the GTK theme's text
# and icon shadows stay (a device comparison showed removing them changes the dark drawer)
LABELS = {("label, button, button label, entry", "color"), ("entry", "color")}


@pytest.mark.parametrize("tid,src,extra", [
    ("handtop-dark", "nwg-drawer-handtop-dark.css", LABELS),
    ("handtop-light", "nwg-drawer-handtop-light.css", set()),
])
def test_drawer(rendered, tid, src, extra):
    compare(css_rules(read(REF, src)), css_rules(read(rendered[tid][1], "nwg-drawer.css")), extra)


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


@pytest.mark.parametrize("tid,src", [("handtop-dark", "mako-config"), ("handtop-light", "mako-config-light")])
def test_mako(rendered, tid, src):
    assert kv(read(rendered[tid][1], "mako.conf")) == kv(read(REF, src))


# v0.4.0: Handtop dark's title-bar buttons are light (labwc drew them black on the dark bar;
# Jason, 2026-11-10); v0.3.9's dark themerc left them unset
DARK_BUTTONS = {("", "window.active.button.unpressed.image.color"): "#e8eaee",
                ("", "window.inactive.button.unpressed.image.color"): "#b8bcc4"}


@pytest.mark.parametrize("tid,src,changed", [("handtop-dark", "labwc-themerc", DARK_BUTTONS),
                                             ("handtop-light", "labwc-themerc-light", {})])
def test_labwc(rendered, tid, src, changed):
    exp = kv(read(REF, src), ":")
    exp.update(changed)
    assert kv(read(rendered[tid][1], "labwc/themerc"), ":") == exp


@pytest.mark.parametrize("tid", ["handtop-dark", "handtop-light"])   # one dark terminal for both
def test_foot(rendered, tid):
    assert kv(read(rendered[tid][1], "foot.ini")) == kv(read(REF, "foot.ini"))


# ---- palettes that were in code -------------------------------------------------------------------
def close(hexcol, rgb):
    """Theme hex vs a float tuple from the code: within 1/255 per channel (rounding)."""
    got = C.parse(hexcol)
    want = [round(x * 255) for x in rgb] + ([] if len(rgb) == 4 else [255])
    return all(abs(a - b) <= 1 for a, b in zip(got, want))


@pytest.mark.parametrize("tid,key", [("handtop-dark", "dark"), ("handtop-light", "light")])
def test_osk(rendered, palettes, tid, key):
    pal, t = palettes["osk"][key], rendered[tid][0]
    assert {k: t.colors[f"osk.{k}"] for k in pal} == pal
    assert len(pal) == sum(1 for k in t.colors if k.startswith("osk."))


@pytest.mark.parametrize("tid,key", [("handtop-dark", "dark"), ("handtop-light", "light")])
def test_display(rendered, palettes, tid, key):
    pal, t = palettes["display"][key], rendered[tid][0]
    assert len(pal) == sum(1 for k in t.colors if k.startswith("display."))
    for k, v in pal.items():
        assert close(t.colors[f"display.{k}"], v), k


@pytest.mark.parametrize("tid,key", [("handtop-dark", "dark"), ("handtop-light", "light")])
def test_status_screen(rendered, palettes, tid, key):
    pal, t = palettes["status"][key], rendered[tid][0]
    assert len(pal) - 1 + 4 == sum(1 for k in t.colors if k.startswith("status."))   # FACE = 4 keys
    for k, col in pal.items():
        if k == "FACE":
            for b in "XYAB":
                assert close(t.colors[f"status.face_{b.lower()}"], col[b]), b
        elif col is None:
            assert t.colors[f"status.{k.lower()}"] is None
        else:
            assert close(t.colors[f"status.{k.lower()}"], col), k


@pytest.mark.parametrize("tid", ["handtop-dark", "handtop-light"])   # same bar in both
def test_osd(rendered, palettes, tid):
    ref, t = palettes["osd"], rendered[tid][0]

    def argb(x):
        x = int(x, 16)
        return "#%06x" % (x & 0xFFFFFF) + ("" if x >> 24 == 0xFF else "%02x" % (x >> 24))
    assert t.colors["osd.bg"] == argb(ref["BG"]) and t.colors["osd.text"] == argb(ref["TEXT"])
    for kind, border, level in ref["KINDS"]:
        assert t.colors[f"osd.{kind}_border"] == argb(border)
        assert t.colors[f"osd.{kind}_level"] == argb(level)


def test_wallpapers(rendered):
    for tid, col in (("handtop-dark", "#1e2430"), ("handtop-light", "#dfe4ec")):
        t, d = rendered[tid]
        assert t.wallpaper["color"] == col and os.path.exists(os.path.join(d, "wallpaper.png"))
