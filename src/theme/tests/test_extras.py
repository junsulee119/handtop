"""A theme's own pointer, fonts and CSS: checks, import, render."""
import json
import os
import shutil
import struct
import zipfile

import pytest

from handtop_theme import package, render, xcursor
from handtop_theme import schema as S
from handtop_theme import theme as T
from handtop_theme.theme import ThemeError

from conftest import minimal, png, write_theme


def problems(t, level="error"):
    return [(p.where, p.message) for p in t.problems if p.level == level]


def _a_font():
    """A small real font: the Retro theme's (in the repo)."""
    from conftest import REPO
    f = os.path.join(REPO, "src", "theme", "themes", "handtop-retro", "fonts", "mono.ttf")
    return f if os.path.isfile(f) else None


FONT = _a_font()
needs_font = pytest.mark.skipif(FONT is None or not shutil.which("fc-scan"),
                                reason="needs fontconfig's fc-scan")


# ---- pointer -------------------------------------------------------------------------------------------
def test_pointer_images_and_hotspots(tmp_path, builtins):
    d = write_theme(str(tmp_path), minimal(cursor={"hotspots": {"hand": [12, 3]}, "size": 48}),
                    {"cursors/arrow.png": png(48, 48), "cursors/hand.png": png(48, 48)})
    t = T.load(d, builtins)
    assert t.errors == []
    assert set(t.cursor_images) == {"arrow", "hand"}
    assert t.cursor["hotspots"] == {"arrow": (0, 0), "hand": (12, 3)}
    assert t.cursor["theme"] == S.CURSOR_SET_PREFIX + "my-blue" and t.cursor["size"] == 48


def test_pointer_wrong_size_and_bad_hotspot(tmp_path, builtins):
    d = write_theme(str(tmp_path), minimal(cursor={"hotspots": {"arrow": [48, 0], "nope": [1, 1]}}),
                    {"cursors/arrow.png": png(24, 24)})
    t = T.load(d, builtins)
    where = [w for w, _m in problems(t)]
    assert "cursor.hotspots.arrow" in where
    assert ("cursor.hotspots.nope", "unknown pointer shape, ignored") in problems(t, "warning")


def test_no_pointer_images_keeps_named_theme(tmp_path, builtins):
    t = T.load(write_theme(str(tmp_path), minimal(cursor={"theme": "Adwaita"})), builtins)
    assert t.cursor_images == {} and t.cursor["theme"] == "Adwaita"


def test_pointer_set_written(tmp_path, builtins, ops):
    d = write_theme(str(tmp_path), minimal(cursor={"hotspots": {"hand": [11, 3]}}),
                    {"cursors/hand.png": png(48, 48)})
    t = T.load(d, builtins)
    out = render.render(t, str(tmp_path / "state"), ops)
    p = os.path.join(out, "pointer")
    assert os.path.exists(os.path.join(p, xcursor.MARK))
    assert "Inherits=Handtop" in open(os.path.join(p, "index.theme")).read()
    for name in S.CURSOR_SHAPES["hand"][0]:
        data = open(os.path.join(p, "cursors", name), "rb").read()
        magic, _hdr, _ver, n = struct.unpack("<4sIII", data[:16])
        assert magic == b"Xcur" and n == 2
        # second image: nominal 48, hotspot as given; first: 24, hotspot halved
        toc = [struct.unpack("<3I", data[16 + 12 * i:28 + 12 * i]) for i in range(n)]
        sizes = []
        for _t, nominal, pos in toc:
            _h, _ty, nom, _v, w, h, hx, hy, _d = struct.unpack("<9I", data[pos:pos + 36])
            sizes.append((nom, w, h, hx, hy))
        assert sizes == [(24, 24, 24, 5, 1), (48, 48, 48, 11, 3)]
    assert not os.path.exists(os.path.join(p, "cursors", "left_ptr"))     # not drawn: Handtop's


def test_no_pointer_folder_without_images(tmp_path, builtins, ops):
    t = T.load(write_theme(str(tmp_path), minimal()), builtins)
    out = render.render(t, str(tmp_path / "state"), ops)
    assert not os.path.exists(os.path.join(out, "pointer"))


# ---- CSS -------------------------------------------------------------------------------------------------
def test_css_added_after_handtops_rules(tmp_path, builtins, ops):
    files = {f"css/{p}.css": f"/* {p} */ .x {{ color: red; }}\n".encode() for p in S.CSS_PARTS}
    t = T.load(write_theme(str(tmp_path), minimal(), files), builtins)
    assert t.errors == [] and set(t.css) == set(S.CSS_PARTS)
    out = render.render(t, str(tmp_path / "state"), ops)
    for f, part in (("waybar.css", "taskbar"), ("nwg-drawer.css", "drawer"),
                    ("wlogout.css", "powermenu"), ("gtk.css", "apps")):
        text = open(os.path.join(out, f)).read()
        assert text.rstrip().endswith(f"/* {part} */ .x {{ color: red; }}")


def test_gtk_css_header_only_without_theme_css(tmp_path, builtins, ops):
    t = T.load(write_theme(str(tmp_path), minimal()), builtins)
    out = render.render(t, str(tmp_path / "state"), ops)
    text = open(os.path.join(out, "gtk.css")).read()
    assert text.startswith("/* Generated") and "{" not in text


@pytest.mark.parametrize("css", [b'@import "x.css";', b"a { background: url('/etc/x.png'); }",
                                 b"a { background: URL ( x ) }", b"a { b: \\75rl(x) }",
                                 b"\xff\xfe not utf-8"])
def test_bad_css_refused(tmp_path, builtins, css):
    t = T.load(write_theme(str(tmp_path), minimal(), {"css/taskbar.css": css}), builtins)
    assert [w for w, _m in problems(t)] == ["css/taskbar.css"]


def test_css_too_large(tmp_path, builtins):
    t = T.load(write_theme(str(tmp_path), minimal(), {"css/apps.css": b"a{}" * 30000}), builtins)
    assert problems(t)[0][0] == "css/apps.css"


# ---- fonts -----------------------------------------------------------------------------------------------
def test_font_not_a_font(tmp_path, builtins):
    t = T.load(write_theme(str(tmp_path), minimal(fonts={"ui": "X"}), {"fonts/ui.ttf": b"PK\x03\x04zip"}),
               builtins)
    assert problems(t) == [("fonts/ui.ttf", "not a TrueType / OpenType font (font collections are not allowed)")]


def test_font_needs_a_name(tmp_path, builtins):
    t = T.load(write_theme(str(tmp_path), minimal(), {"fonts/ui.ttf": b"\x00\x01\x00\x00" + b"\x00" * 60}),
               builtins)
    assert problems(t) == [("fonts.ui", "must name the family of fonts/ui.ttf")]


def test_two_fonts_for_one_role(tmp_path, builtins):
    f = b"\x00\x01\x00\x00" + b"\x00" * 60
    t = T.load(write_theme(str(tmp_path), minimal(fonts={"ui": "X"}), {"fonts/ui.ttf": f, "fonts/ui.otf": f}),
               builtins)
    assert problems(t)[0][1] == "only one ui font (.ttf or .otf)"


def test_font_without_licence_warns(tmp_path, builtins):
    f = b"\x00\x01\x00\x00" + b"\x00" * 60
    t = T.load(write_theme(str(tmp_path), minimal(fonts={"mono": "X"}), {"fonts/mono.ttf": f}), builtins)
    assert t.errors == [] and t.font_files == {"mono": os.path.join(t.path, "fonts/mono.ttf")}
    assert ("fonts/LICENSE.txt", "missing: say which licence lets the fonts be shared") in problems(t, "warning")


@needs_font
def test_font_family_checked_on_import(tmp_path, builtins):
    data = open(FONT, "rb").read()
    fam = __import__("handtop_theme.extras", fromlist=["x"]).font_families(FONT)
    ok = write_theme(str(tmp_path / "a"), minimal(fonts={"ui": fam[0]}),
                     {"fonts/ui.ttf": data, "fonts/LICENSE.txt": b"licence"})
    assert T.load(ok, builtins, decode=True).errors == []
    bad = write_theme(str(tmp_path / "b"), minimal(fonts={"ui": "Not That Font"}), {"fonts/ui.ttf": data})
    assert [w for w, _m in problems(T.load(bad, builtins, decode=True))] == ["fonts.ui"]


@needs_font
def test_damaged_font_refused_on_import(tmp_path, builtins):
    d = write_theme(str(tmp_path), minimal(fonts={"ui": "X"}),
                    {"fonts/ui.ttf": b"\x00\x01\x00\x00" + b"\x00" * 200})
    assert problems(T.load(d, builtins, decode=True)) == [("fonts/ui.ttf", "fontconfig cannot read it as one font")]


def test_fonts_copied_on_render(tmp_path, builtins, ops):
    f = b"\x00\x01\x00\x00" + b"\x00" * 60
    t = T.load(write_theme(str(tmp_path), minimal(fonts={"ui": "X"}), {"fonts/ui.ttf": f}), builtins)
    out = render.render(t, str(tmp_path / "state"), ops)
    assert os.listdir(os.path.join(out, "fonts")) == ["my-blue-ui.ttf"]


# ---- round trip --------------------------------------------------------------------------------------------
def test_export_import_keeps_extras(tmp_path, builtins):
    f = b"\x00\x01\x00\x00" + b"\x00" * 60
    files = {"cursors/arrow.png": png(48, 48), "fonts/ui.ttf": f, "fonts/LICENSE.txt": b"OFL",
             "css/taskbar.css": b"#clock { color: red; }"}
    d = write_theme(str(tmp_path / "src"), minimal(fonts={"ui": "X"}), files)
    z = package.export_theme(d, str(tmp_path / "x.handtop-theme"), builtins)
    names = set(zipfile.ZipFile(z).namelist())
    assert set(files) <= names
    t = package.import_theme(z, str(tmp_path / "user"), builtins, decode=False)
    assert t.errors == [] and set(t.cursor_images) == {"arrow"} and "taskbar" in t.css
    assert os.path.exists(os.path.join(t.path, "fonts", "LICENSE.txt"))


def test_duplicate_gets_its_own_pointer_set_name(tmp_path, builtins):
    d = write_theme(str(tmp_path / "src"), minimal(), {"cursors/arrow.png": png(48, 48)})
    t = package.duplicate(d, "copy", "Copy", str(tmp_path / "user"), builtins)
    assert t.cursor["theme"] == S.CURSOR_SET_PREFIX + "copy"


def test_guide_lists_extras():
    from handtop_theme import guide
    g = guide.generate()
    for rel in [S.cursor_file(s) for s in S.CURSOR_SHAPES] + [S.css_file(p) for p in S.CSS_PARTS]:
        assert f"`{rel}`" in g
    assert S.FONT_LICENSE_FILE in g


@needs_font
def test_variable_font_accepted(tmp_path, builtins):
    """A variable font: fontconfig lists its named instances, all one family (Glass's Inter)."""
    from conftest import REPO
    var = os.path.join(REPO, "src", "theme", "themes", "handtop-glass", "fonts", "ui.ttf")
    from handtop_theme.extras import font_families
    assert font_families(var) == ["Inter Variable"]
    d = write_theme(str(tmp_path), minimal(fonts={"ui": "Inter Variable"}),
                    {"fonts/ui.ttf": open(var, "rb").read(), "fonts/LICENSE.txt": b"x"})
    assert T.load(d, builtins, decode=True).errors == []


def test_docs_copy_of_the_guide_is_current():
    """docs/theme-format.md is GUIDE.md as the Theme app writes it (for people and AI agents without
    an exported theme). Regenerate: cd src/theme && python3 -c "from handtop_theme import guide;
    open('../../docs/theme-format.md', 'w').write(guide.generate())" """
    from conftest import REPO
    from handtop_theme import guide
    with open(os.path.join(REPO, "docs", "theme-format.md"), encoding="utf-8") as f:
        assert f.read() == guide.generate(), "docs/theme-format.md is out of date (see this test's docstring)"
