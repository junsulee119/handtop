"""Filling in a theme: palette from the base, part colours derived, images from the base or made
from the theme's own, "system" slots, the wallpaper rule."""
import os

from handtop_theme import schema as S
from handtop_theme import theme

from conftest import minimal, png, write_theme


def load(tmp_path, builtins, data, files=None):
    return theme.load(write_theme(str(tmp_path), data, files), builtins)


def test_builtins_are_complete(builtins):
    for tid in ("handtop-dark", "handtop-light", "handtop-grayscale"):
        t = theme.load(os.path.join(builtins, tid), builtins)
        assert t.problems == []
        assert set(t.own) >= {s for s, v in S.IMAGE_SLOTS.items() if v[2] != "generated"}
        assert t.wallpaper["image"]


def test_builtins_load_cleanly(builtins):
    from handtop_theme import builtin
    assert sorted(os.listdir(builtins)) == sorted(builtin.IDS)
    for tid in builtin.IDS:
        t = theme.load(os.path.join(builtins, tid), builtins)
        assert t.problems == [], tid
        assert t.name and t.description


def test_debian_theme(builtins):
    t = theme.load(os.path.join(builtins, "handtop-debian"), builtins)
    for a in S.DEFAULT_APPS:
        assert t.images[f"apps/{a}"] == ("system",) and t.images[f"apps/{a}@22"] == ("system",)
    assert all(t.images[f"tray/{w}"] == ("system",) for w in S.WIFI)
    assert t.images["apps/theme"][1].endswith("handtop-light/icons/apps/theme.png")   # Handtop's own app
    assert t.cursor == {"theme": "Adwaita", "size": 24} and t.wallpaper["image"] is None
    assert t.colors["osk.sel"] == t.palette["accent"]                                   # derived


def test_high_contrast_theme(builtins):
    t = theme.load(os.path.join(builtins, "handtop-high-contrast"), builtins)
    assert t.borders == 2 and t.fonts["scale"] == 1.25 and t.cursor["size"] == 48
    assert t.gtk["theme"] == "HighContrastInverse"
    assert t.images["taskbar/battery-3"][1].endswith("handtop-dark/icons/taskbar/battery-3.png")


def test_grayscale_theme(builtins):
    from handtop_theme import colors as C
    t = theme.load(os.path.join(builtins, "handtop-grayscale"), builtins)
    for v in list(t.palette.values()) + [v for v in t.colors.values() if v] + [t.wallpaper["color"]]:
        r, g, b, _a = C.parse(v)
        assert r == g == b, v
    assert t.colors["status.label"] is None


def test_palette_only_theme(tmp_path, builtins):
    t = load(tmp_path, builtins, minimal(palette={"bg": "#102030", "accent": "#aa0000"}))
    assert t.errors == []
    dark = theme.load(os.path.join(builtins, "handtop-dark"), builtins)
    assert t.palette["fg"] == dark.palette["fg"]               # from the base
    assert t.colors["taskbar.bg"] == "#102030"                 # derived from its own palette
    assert t.colors["taskbar.apps_bg"] == "#aa0000"
    assert t.colors["notify.bg"] == "#102030e6"
    assert t.colors["titlebar.active_button"] == t.palette["fg"]   # derived, not the base's null
    assert t.wallpaper == {"color": "#102030", "image": None, "mode": "center"}
    assert t.images["taskbar/battery-3"] == dark.images["taskbar/battery-3"]
    assert t.own == set()


def test_light_base(tmp_path, builtins):
    t = load(tmp_path, builtins, minimal(base="light"))
    light = theme.load(os.path.join(builtins, "handtop-light"), builtins)
    assert t.palette == light.palette
    assert t.wallpaper["color"] == "#dfe4ec" and t.wallpaper["image"] is None
    assert t.gtk["color_scheme"] == "default"


def test_explicit_colours_win(tmp_path, builtins):
    t = load(tmp_path, builtins, minimal(colors={"osk.bg": "#010203", "titlebar.active_button": None}))
    assert t.colors["osk.bg"] == "#010203" and t.colors["titlebar.active_button"] is None


def test_own_inputmode_icon_generates_its_shake_frames(tmp_path, builtins):
    t = load(tmp_path, builtins, minimal(), {"icons/taskbar/inputmode-gamepad.png": png(23, 23)})
    assert t.errors == []
    own = t.images["taskbar/inputmode-gamepad"][1]
    for dx in S.SHAKES:
        assert t.images[f"taskbar/inputmode-gamepad-shake{dx}"] == ("generate", own)
    # another mode keeps the base's own drawn frames
    assert t.images["taskbar/inputmode-bt-shake1"][0] == "file"


def test_own_frames_are_used(tmp_path, builtins):
    t = load(tmp_path, builtins, minimal(), {"icons/taskbar/inputmode-gamepad.png": png(23, 23),
                                             "icons/taskbar/inputmode-gamepad-shake1.png": png(23, 23)})
    assert t.images["taskbar/inputmode-gamepad-shake1"][0] == "file"
    assert t.images["taskbar/inputmode-gamepad-shake2"][0] == "generate"


def test_app_icon_small_sizes(tmp_path, builtins):
    t = load(tmp_path, builtins, minimal(), {"icons/apps/thunar.png": png(56, 56),
                                             "icons/apps/thunar@20.png": png(20, 20)})
    assert t.images["apps/thunar@22"] == ("generate", t.images["apps/thunar"][1])
    assert t.images["apps/thunar@20"][0] == "file"


def test_system_slots(tmp_path, builtins):
    t = load(tmp_path, builtins, minimal(icons={"apps/thunar": "system", "tray/nm-signal-50": "system"}))
    assert t.images["apps/thunar"] == ("system",)
    assert t.images["apps/thunar@22"] == ("system",) and t.images["apps/thunar@20"] == ("system",)
    assert t.images["tray/nm-signal-50"] == ("system",)


def test_wrong_size_and_bad_png(tmp_path, builtins):
    t = load(tmp_path, builtins, minimal(), {"icons/taskbar/battery-3.png": png(20, 12),
                                             "icons/apps/theme.png": b"GIF89a....",
                                             "icons/taskbar/apps.png": png(16, 16)[:-20]})
    where = {p.where for p in t.errors}
    assert where == {"icons/taskbar/battery-3.png", "icons/apps/theme.png", "icons/taskbar/apps.png"}
    assert any("must be 20x11" in p.message for p in t.errors)


def test_wallpaper(tmp_path, builtins):
    t = load(tmp_path, builtins, minimal(wallpaper={"image": "images/wallpaper.png", "mode": "fill"}),
             {"images/wallpaper.png": png(800, 600)})
    assert t.errors == [] and t.wallpaper["image"].endswith("wallpaper.png")
    assert t.wallpaper["mode"] == "fill"
    t = load(tmp_path / "b", builtins, minimal(wallpaper={"image": "images/wallpaper.png"}))
    assert [p.where for p in t.errors] == ["wallpaper.image"]
    t = load(tmp_path / "c", builtins, minimal(wallpaper={"image": "images/wallpaper.png"}),
             {"images/wallpaper.png": png(4000, 10)})
    assert t.errors


def test_stray_files_warn(tmp_path, builtins):
    t = load(tmp_path, builtins, minimal(), {"run.sh": b"#!/bin/sh", "icons/apps/x.png": png(56, 56)})
    assert t.errors == []
    assert {p.where for p in t.problems} == {"run.sh", "icons/apps/x.png"}


def test_missing_or_broken_json(tmp_path, builtins):
    d = tmp_path / "x"
    d.mkdir()
    assert [p.where for p in theme.load(str(d), builtins).errors] == ["theme.json"]
    (d / "theme.json").write_text("{nope")
    assert "not valid JSON" in theme.load(str(d), builtins).errors[0].message
    (d / "theme.json").write_text("[]")
    assert theme.load(str(d), builtins).errors


def test_broken_base_is_reported(tmp_path, builtins):
    t = theme.load(write_theme(str(tmp_path), minimal()), str(tmp_path / "nowhere"))
    assert [p.where for p in t.errors] == ["base"]


def test_base_theme_must_be_complete(tmp_path):
    d = write_theme(str(tmp_path), minimal(id="handtop-dark", palette={"bg": "#000000"}))
    t = theme.load(d, str(tmp_path))
    assert any(p.where == "palette.fg" for p in t.errors)
