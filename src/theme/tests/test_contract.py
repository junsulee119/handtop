"""The contract itself (schema.py), colours, theme.json validation and GUIDE.md."""
import pytest

from handtop_theme import colors as C
from handtop_theme import guide, theme
from handtop_theme import schema as S

from conftest import minimal


def test_slot_counts():
    kinds = {}
    for _s, (_w, _h, k) in S.IMAGE_SLOTS.items():
        kinds[k] = kinds.get(k, 0) + 1
    assert sum(1 for s in S.IMAGE_SLOTS if s.startswith("taskbar/battery")) == 48
    assert len(S.WIFI) == 46 and all(S.IMAGE_SLOTS[f"tray/{w}"][2] == "optional" for w in S.WIFI)
    assert kinds["generated"] == 16 + 2 * 14          # shake frames + @22/@20 of 14 apps
    assert len(S.COLORS) == 115


def test_parents_exist_and_are_required():
    for s, (_w, _h, k) in S.IMAGE_SLOTS.items():
        p = S.parent(s)
        assert (p is None) == (k != "generated")
        if p:
            assert S.IMAGE_SLOTS[p][2] == "required"


def test_system_ok_only_tray_and_default_apps():
    for s in S.SYSTEM_OK:
        assert s.startswith("tray/") or s.split("/")[1].split("@")[0] in S.DEFAULT_APPS
    assert "apps/theme" not in S.SYSTEM_OK and "taskbar/apps" not in S.SYSTEM_OK


def test_rules_only_use_palette_names():
    for k, (rule, _d, _n) in S.COLORS.items():
        refs = [rule] if isinstance(rule, str) else list(rule[1:3] if rule[0] == "mix" else rule[1:2])
        for r in refs:
            assert r.startswith("#") or r in S.PALETTE, k
        theme.derive(rule, {p: "#808080" for p in S.PALETTE})


def test_colors():
    assert C.parse("#102030") == (16, 32, 48, 255)
    assert C.parse("#10203040") == (16, 32, 48, 64)
    assert C.css("#141820eb") == "rgba(20, 24, 32, 0.92)"
    assert C.css("#242f4ff2") == "rgba(36, 47, 79, 0.95)"
    assert C.mix("#000000", "#ffffff", 0.5) == "#808080"
    assert C.with_alpha("#1a1e26", 0.9) == "#1a1e26e6"
    for bad in ("1a1e26", "#1a1e2", "#1a1e26e", "#gggggg", None, 5, "#1a1e26 "):
        assert not C.valid(bad)
        with pytest.raises(ValueError):
            C.parse(bad)


def errors(data):
    return {p.where for p in theme.validate(data) if p.level == "error"}


def warnings(data):
    return {p.where for p in theme.validate(data) if p.level == "warning"}


def test_minimal_is_valid():
    assert theme.validate(minimal()) == []


@pytest.mark.parametrize("field,value", [
    ("schema", 2), ("schema", 0), ("schema", "1"), ("schema", True),
    ("id", "My Theme"), ("id", "-x"), ("id", "a" * 41), ("id", "../x"), ("id", ""),
    ("name", ""), ("name", "x" * 33), ("name", "two\nlines"), ("name", 3),
    ("base", "grey"), ("base", None),
    ("borders", 0), ("borders", 4), ("borders", "2"), ("borders", True),
])
def test_bad_top_fields(field, value):
    assert field in errors(minimal(**{field: value}))


def test_newer_schema_message():
    msgs = [p.message for p in theme.validate(minimal(schema=9))]
    assert any("newer Handtop" in m for m in msgs)


def test_bad_sections():
    d = minimal(palette={"bg": "blue", "nope": "#000000"}, colors={"osk.bg": "#12", "x.y": "#000000",
                "titlebar.active_button": None, "taskbar.bg": None},
                wallpaper={"image": "../../etc/passwd", "mode": "zoom", "color": "red"},
                status_screen={"style": "neon"}, gtk={"color_scheme": "dark", "theme": "Adw\"aita"},
                cursor={"size": 200, "theme": "a/b"}, fonts={"scale": 3, "ui": "x;y"},
                icons={"apps/thunar": "icons/x.png", "apps/theme": "system", "nope": "system"},
                names={"foot": "", "theme": "X", "thunar": "Files"})
    e, w = errors(d), warnings(d)
    assert {"palette.bg", "colors.osk.bg", "colors.taskbar.bg", "wallpaper.image", "wallpaper.mode",
            "wallpaper.color", "status_screen.style", "gtk.color_scheme", "gtk.theme", "cursor.size",
            "cursor.theme", "fonts.scale", "fonts.ui", "icons.apps/thunar", "icons.apps/theme",
            "names.foot"} <= e
    assert "colors.titlebar.active_button" not in e          # nullable
    assert {"palette.nope", "colors.x.y", "icons.nope", "names.theme"} <= w
    assert "names.thunar" not in e | w


def test_sections_must_be_objects():
    assert "palette" in errors(minimal(palette=["#000000"]))


def test_unknown_top_field_warns():
    assert "extends" in warnings(minimal(extends="handtop-dark"))


def test_guide_covers_everything():
    g = guide.generate()
    for k in S.PALETTE:
        assert f"`{k}`" in g
    for k in S.COLORS:
        assert f"`{k}`" in g
    for s in S.IMAGE_SLOTS:
        assert f"`{S.slot_file(s)}`" in g
