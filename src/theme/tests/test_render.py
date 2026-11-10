"""The renderer: generated images, theme.env, safety of what goes into configs."""
import os

from handtop_theme import current, render, theme
from handtop_theme import schema as S

from conftest import minimal, png, write_theme


def test_render_custom_theme(tmp_path, builtins, ops):
    d = write_theme(str(tmp_path), minimal(name="It's */ { evil }", palette={"bg": "#102030"},
                                           icons={"apps/thunar": "system"},
                                           fonts={"scale": 1.25}),
                    {"icons/taskbar/inputmode-gamepad.png": png(23, 23),
                     "icons/apps/foot.png": png(56, 56)})
    t = theme.load(d, builtins)
    assert t.errors == []
    out = render.render(t, str(tmp_path / "state" / "theme"), ops)
    shifts = sorted(c[3] for c in ops.calls if c[0] == "shift")
    assert shifts == sorted(S.SHAKES)                                  # only the own icon's frames
    scales = sorted((os.path.basename(c[2]), c[3]) for c in ops.calls if c[0] == "scale")
    assert ("foot.png", 20) in scales and ("foot.png", 22) in scales
    assert not os.path.exists(os.path.join(out, "icon-theme/scalable/apps/org.xfce.thunar.png"))
    assert os.path.exists(os.path.join(out, "icon-theme/scalable/apps/rg35xxh-theme.png"))
    css = open(os.path.join(out, "waybar.css")).read()
    assert "evil" not in css and "font-size: 15px" in css and "#102030" in css
    assert not os.path.exists(os.path.join(out, "wallpaper.png"))
    env = current.read_env(os.path.join(out, "theme.env"))
    assert env["THEME_NAME"] == "It's */ { evil }"
    assert env["WALLPAPER"] == "" and env["COLOR_TASKBAR_BG"] == "#102030"
    assert env["ICONS"] == os.path.join(out, "icons")
    assert len([k for k in env if k.startswith("COLOR_")]) == len(S.COLORS)


def test_rerender_replaces_whole_folder(tmp_path, builtins, ops):
    t = theme.load(os.path.join(builtins, "handtop-dark"), builtins)
    target = str(tmp_path / "theme")
    render.render(t, target, ops)
    open(os.path.join(target, "stale"), "w").close()
    render.render(t, target, ops)
    assert not os.path.exists(os.path.join(target, "stale"))
    assert sorted(os.listdir(tmp_path)) == ["theme"]


def test_icon_theme_index(tmp_path, builtins, ops):
    t = theme.load(os.path.join(builtins, "handtop-dark"), builtins)
    out = render.render(t, str(tmp_path / "theme"), ops)
    idx = open(os.path.join(out, "icon-theme/index.theme")).read()
    assert "Inherits=Adwaita,hicolor" in idx
    for w in S.WIFI:
        assert os.path.exists(os.path.join(out, "icon-theme/22x22/apps", f"{w}.png"))
        assert os.path.exists(os.path.join(out, "icon-theme/24x24/apps", f"{w}.png"))
    flat = os.listdir(os.path.join(out, "icons"))
    assert "panel-apps.png" in flat and "power-saver-focus.png" in flat and "usbtarget-pc.png" in flat
    assert "battery-charging-low-5-saver.png" in flat and "inputmode-bt-shake-2.png" in flat


def test_env_quoting(tmp_path):
    p = tmp_path / "e"
    p.write_text("# c\nA='it'\\''s'\nB='x=y'\nbad line\n")
    assert current.read_env(str(p)) == {"A": "it's", "B": "x=y"}
    assert current.read_env(str(tmp_path / "missing")) == {}


def test_current_helpers(tmp_path, builtins, ops):
    t = theme.load(os.path.join(builtins, "handtop-light"), builtins)
    out = render.render(t, str(tmp_path / "theme"), ops)
    env = current.read_env(os.path.join(out, "theme.env"))
    osk = current.colors("osk", env)
    assert osk["bg"] == "#d5dbe5" and len(osk) == 17
    st = current.colors("status", env)
    assert st["label"] == "#2e5499" and st["screen_text"] == "#e8ebed"
    assert current.colors("titlebar", current.read_env(os.path.join(builtins, "nothing")))  == {}
    assert current.rgba("#ff000080") == (1.0, 0.0, 0.0, 128 / 255) and current.rgba(None) is None
    assert current.rgba("#ff0000ff") == (1.0, 0.0, 0.0) == current.rgba("#ff0000")
    dark = current.colors("status", current.read_env(os.path.join(
        render.render(theme.load(os.path.join(builtins, "handtop-dark"), builtins), str(tmp_path / "d"), ops),
        "theme.env")))
    assert dark["label"] is None                     # a null colour comes back as None
