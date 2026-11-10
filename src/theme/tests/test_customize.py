"""The Duplicate screen's choices (customize.py) and where theme files are looked for."""
import json
import os

import pytest

from handtop_theme import colors as C
from handtop_theme import customize as Z
from handtop_theme import package, theme


def dup(builtins, tmp_path, src="handtop-dark", tid="mine"):
    return package.duplicate(os.path.join(builtins, src), tid, "Mine", str(tmp_path / "user"), builtins)


def data(t):
    with open(os.path.join(t.path, "theme.json")) as f:
        return json.load(f)


def test_unchanged_copy_stays_exact(builtins, tmp_path):
    t = dup(builtins, tmp_path)
    Z.customize(t.path, icons="dark", pointer=24, text=1.0)       # what the screen sends untouched
    t2 = theme.load(t.path, builtins)
    orig = theme.load(os.path.join(builtins, "handtop-dark"), builtins)
    assert t2.colors == orig.colors and t2.own == orig.own and t2.wallpaper["image"]


def test_new_accent_rederives(builtins, tmp_path):
    t = dup(builtins, tmp_path)
    Z.customize(t.path, accent="#d70a53", icons="dark")
    d = data(t)
    assert "colors" not in d and d["palette"]["accent"] == "#d70a53"
    t2 = theme.load(t.path, builtins)
    assert t2.errors == [] and t2.colors["taskbar.apps_bg"] == "#d70a53"
    assert t2.colors["osk.sel"] == "#d70a53"
    assert t2.own                                   # same icons (base unchanged): its copies stay
    assert t2.wallpaper["image"]                    # same background: the logo wallpaper stays


def test_new_background_switches_base_and_drops_wallpaper(builtins, tmp_path):
    t = dup(builtins, tmp_path)
    Z.customize(t.path, background="#fafafa", icons="light")
    t2 = theme.load(t.path, builtins)
    assert t2.errors == [] and t2.base == "light" and t2.palette["fg"] == "#2e3436"
    assert t2.wallpaper["image"] is None and t2.gtk["color_scheme"] == "default"
    assert t2.own == set()                          # images now from handtop-light
    assert t2.images["taskbar/battery-3"][1].endswith("handtop-light/icons/taskbar/battery-3.png")
    assert t2.palette["accent_fg"] == Z.accent_fg(t2.palette["accent"], "#fafafa")


def test_icons_choice_wins(builtins, tmp_path):
    t = dup(builtins, tmp_path)
    Z.customize(t.path, background="#fafafa", icons="dark")    # light colours, dark icon set
    t2 = theme.load(t.path, builtins)
    assert t2.base == "dark" and t2.own                         # unchanged base keeps its copies


def test_grayscale_copy_keeps_grey_icons(builtins, tmp_path):
    t = dup(builtins, tmp_path, "handtop-grayscale")
    Z.customize(t.path, accent="#26a269", icons="dark")
    assert theme.load(t.path, builtins).own                      # its own grey images stay


def test_pointer_and_text(builtins, tmp_path):
    t = dup(builtins, tmp_path)
    Z.customize(t.path, pointer=48, text=1.25)
    t2 = theme.load(t.path, builtins)
    assert t2.cursor["size"] == 48 and t2.fonts["scale"] == 1.25
    with pytest.raises(ValueError):
        Z.customize(t.path, pointer=40)
    with pytest.raises(ValueError):
        Z.customize(t.path, accent="#123456")


def test_presets_are_readable():
    for bg, p in Z.BACKGROUNDS.items():
        assert Z.is_dark(bg) == Z.is_dark(p["surface"]) and Z.is_dark(bg) != Z.is_dark(p["fg"]), bg
        for a in Z.ACCENTS:
            fg = Z.accent_fg(a, bg)
            assert C.valid(fg)


def test_id_from_name():
    assert Z.id_from_name("My Blue", set()) == "my-blue"
    assert Z.id_from_name("My Blue", {"my-blue", "my-blue-2"}) == "my-blue-3"
    assert Z.id_from_name("Handtop Pink", set()) == "my-handtop-pink"
    assert Z.id_from_name("  !!! ", set()) == "theme"
    assert Z.id_from_name("Ünïcode ★ name", set()) == "n-code-name"
    assert len(Z.id_from_name("x" * 80, set())) <= 40


def test_short():
    assert Z.short("/home/x/Themes/a.handtop-theme", "/home/x") == "~/Themes/a.handtop-theme"
    assert Z.short("/home/x", "/home/x") == "~" and Z.short("/home/xy/a", "/home/x") == "/home/xy/a"
