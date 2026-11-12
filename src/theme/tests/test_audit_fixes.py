"""Regression tests for the theme-system review of 2026-11-11 (R01-R13). Each was a probe that
showed the fault; here it checks the fixed behaviour. The CLI (overlay/usr/local/bin/rg35xxh-theme)
runs with its desktop side stubbed: no gsettings, fontconfig, labwc or processes are touched."""
import ast
import errno
import importlib.machinery
import importlib.util
import json
import os
import struct
import subprocess
import threading
import time
import types
import zipfile
import zlib

import pytest

from conftest import REPO, StubOps, minimal, png, write_theme
from handtop_theme import customize, extras, fsutil, package, render, theme


@pytest.fixture
def cli(tmp_path, monkeypatch, builtins):
    loader = importlib.machinery.SourceFileLoader(
        "rg35xxh_theme_cli", os.path.join(REPO, "overlay/usr/local/bin/rg35xxh-theme"))
    mod = importlib.util.module_from_spec(importlib.util.spec_from_loader(loader.name, loader))
    loader.exec_module(mod)
    state = tmp_path / "state" / "theme"
    monkeypatch.setattr(mod, "STATE", str(state))
    monkeypatch.setattr(mod, "STAMP", str(state / ".stamp"))
    monkeypatch.setattr(mod, "CHOICE", str(tmp_path / "config" / "choice"))
    for name in ("_fonts", "_check_installed", "_pointer", "_waybar_refresh"):
        monkeypatch.setattr(mod, name, lambda t=None: None)
    monkeypatch.setattr(mod, "_pointer_sets", lambda keep: None)
    monkeypatch.setattr(mod, "_running_pointer", lambda: set())
    monkeypatch.setattr(mod, "_session_cursor", lambda: None)
    monkeypatch.setattr(mod, "_session", lambda t: True)
    monkeypatch.setattr(mod, "_pids", lambda name: [])
    real_render = render.render
    monkeypatch.setattr(render, "render", lambda t, d: real_render(t, d, StubOps(), ()))
    from handtop_theme import current
    monkeypatch.setattr(mod, "render_env", lambda: current.read_env(str(state / "theme.env")))
    themes = {tid: write_theme(str(tmp_path / "themes"), minimal(id=tid, name=tid))
              for tid in ("audit-a", "audit-b")}

    def find(tid):
        p = os.path.join(builtins, tid)
        return themes.get(tid) or (p if os.path.isdir(p) else None)
    monkeypatch.setattr(mod, "_load", lambda tid: theme.load(themes[tid], builtins))
    monkeypatch.setattr(package, "find", find)
    mod.audit_themes = themes
    return mod


def app_method(name, **glob):
    """One App method from app.py, run with stand-ins for GTK (no display needed)."""
    path = os.path.join(REPO, "src/theme/handtop_theme/app.py")
    with open(path, encoding="utf-8") as f:
        tree = ast.parse(f.read(), path)
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "App")
    method = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == name)
    scope = {"os": os, "Z": customize, "T": theme, "package": package, **glob}
    exec(compile(ast.Module(body=[method], type_ignores=[]), path, "exec"), scope)
    return scope[name]


# ---- R01: CSS comments do not hide url( ---------------------------------------------------------
@pytest.mark.parametrize("css", [
    b'* { background-image: url/**/("file:///tmp/x.png"); }',
    b'* { background-image: URL /* a */ ("file:///tmp/x.png"); }',
    b'* { color: red; } /* never closed',
    b'@IMPORT "x.css";',
])
def test_r01_css_refused(tmp_path, css):
    f = tmp_path / "a.css"
    f.write_bytes(css)
    assert extras.css_problem(str(f)) is not None


def test_r01_comments_still_allowed(tmp_path):
    f = tmp_path / "a.css"
    f.write_bytes(b"/* Retro: grey buttons */\nbutton { color: #000000; } /* url( in a comment */\n")
    assert extras.css_problem(str(f)) is None


def test_r01_import_refuses_it(tmp_path, builtins):
    archive = tmp_path / "css.handtop-theme"
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr("theme.json", json.dumps(minimal()))
        z.writestr("css/apps.css", b'* { background-image: url/**/("file:///tmp/x.png"); }')
    with pytest.raises(theme.ThemeError):
        package.import_theme(str(archive), str(tmp_path / "installed"), builtins, decode=False)


# ---- R02: a failed swap keeps what was there ----------------------------------------------------
def test_r02_import_failure_keeps_installed_theme(tmp_path, builtins, monkeypatch):
    user = tmp_path / "themes"
    original = write_theme(str(user), minimal(name="Original"))
    archive = tmp_path / "new.handtop-theme"
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr("theme.json", json.dumps(minimal(name="Replacement")))
    real = os.rename

    def failing(src, dst):
        if os.path.basename(src).startswith(".import-") and dst == original:
            raise OSError(errno.EIO, "injected")
        return real(src, dst)
    monkeypatch.setattr(os, "rename", failing)
    with pytest.raises(OSError, match="injected"):
        package.import_theme(str(archive), str(user), builtins, replace=True, decode=False)
    monkeypatch.setattr(os, "rename", real)
    with open(os.path.join(original, "theme.json")) as f:
        assert json.load(f)["name"] == "Original"
    assert sorted(os.listdir(user)) == ["my-blue"]


def test_r02_render_failure_keeps_rendered_theme(tmp_path, builtins, monkeypatch):
    t = theme.load(os.path.join(builtins, "handtop-dark"), builtins)
    state = str(tmp_path / "state")
    render.render(t, state, StubOps(), ())
    real = os.rename

    def failing(src, dst):
        if os.path.basename(src).startswith(".render-") and dst == state:
            raise OSError(errno.EIO, "injected")
        return real(src, dst)
    monkeypatch.setattr(os, "rename", failing)
    with pytest.raises(OSError, match="injected"):
        render.render(t, state, StubOps(), ())
    assert os.path.exists(os.path.join(state, "theme.env"))


def test_r02_recover_after_a_crash(tmp_path):
    final = tmp_path / "theme"
    final.mkdir()
    (final / "theme.env").write_text("x")
    aside = tmp_path / ".old-theme-abc"
    aside.mkdir()
    os.rename(final, aside / "theme")                # died between the two renames
    other = tmp_path / ".old-theme-blue-xyz"         # another folder's copy: left alone
    (other / "theme-blue").mkdir(parents=True)
    fsutil.recover(str(final))
    assert (final / "theme.env").read_text() == "x"
    assert not aside.exists() and other.exists()


# ---- R03: one change at a time ------------------------------------------------------------------
def test_r03_concurrent_applies_do_not_mix(cli, monkeypatch):
    a_saving = threading.Event()
    real_save = cli._save_choice

    def slow_save(tid):
        if tid == "audit-a":
            a_saving.set()
            time.sleep(0.3)                          # B tries to apply meanwhile
        real_save(tid)
    monkeypatch.setattr(cli, "_save_choice", slow_save)
    a = threading.Thread(target=cli.apply, args=("audit-a",))
    a.start()
    assert a_saving.wait(5)
    cli.apply("audit-b")
    a.join(5)
    assert cli.current() == cli.render_env()["THEME_ID"] == "audit-b"


# ---- R04: the log-in check sees missing outputs, removed files and a changed base -----------------
def test_r04_missing_output_is_rendered_again(cli):
    cli.apply("audit-a")
    css = os.path.join(cli.STATE, "waybar.css")
    os.remove(css)
    cli.ensure()
    assert os.path.exists(css)


def test_r04_stamp_follows_removed_files(cli):
    path = cli.audit_themes["audit-a"]
    f = os.path.join(path, "icons", "taskbar", "battery-3.png")
    os.makedirs(os.path.dirname(f))
    with open(f, "wb") as fh:
        fh.write(png(20, 11))
    os.utime(f, ns=(1_000_000_000, 1_000_000_000))       # older than theme.json
    before = cli._stamp(path)
    os.remove(f)
    assert cli._stamp(path) != before


def test_r04_stamp_follows_the_base(cli, builtins):
    path = cli.audit_themes["audit-a"]
    basefile = os.path.join(builtins, "handtop-dark", "theme.json")
    with open(basefile, "rb") as f:
        original = f.read()
    before = cli._stamp(path)
    try:
        data = json.loads(original)
        data["palette"]["bg"] = "#123456"
        with open(basefile, "w") as f:
            json.dump(data, f)
        assert cli._stamp(path) != before
    finally:
        with open(basefile, "wb") as f:
            f.write(original)


def test_r04_unchanged_is_fast(cli, monkeypatch):
    cli.apply("audit-a")
    called = []
    monkeypatch.setattr(cli, "prepare", lambda tid: called.append(tid))
    cli.ensure()
    assert called == []


# ---- R05: a change cut short is done again at the next log-in ------------------------------------
def test_r05_failed_session_is_retried(cli, monkeypatch):
    def fail(t):
        raise OSError(errno.EIO, "injected")
    monkeypatch.setattr(cli, "_session", fail)
    with pytest.raises(OSError):
        cli.apply("audit-a")
    assert not os.path.exists(cli.STAMP)
    retried = []
    monkeypatch.setattr(cli, "_session", lambda t: retried.append(t.id) or True)
    cli.ensure()
    assert retried == ["audit-a"] and os.path.exists(cli.STAMP)


def test_r05_unset_gtk_settings_are_retried(cli, monkeypatch):
    monkeypatch.setattr(cli, "_session", lambda t: False)        # gsettings could not be reached
    cli.apply("audit-a")
    assert not os.path.exists(cli.STAMP)


# ---- R06: Export asks before replacing the file it will really write -----------------------------
@pytest.mark.parametrize("answer", [False, True])
def test_r06_export_asks_about_the_final_name(tmp_path, builtins, answer):
    chosen, final = tmp_path / "keep", tmp_path / "keep.handtop-theme"
    final.write_bytes(b"EXISTING")
    asked = []

    class Chooser:
        def set_do_overwrite_confirmation(self, flag): pass
        def set_current_name(self, value): pass
        def run(self): return 1
        def get_filename(self): return str(chosen)
        def destroy(self): pass

    t = theme.load(os.path.join(builtins, "handtop-dark"), builtins)
    obj = types.SimpleNamespace(selected=t.id, themes={t.id: t}, _chooser=lambda *a: Chooser(),
                                confirm=lambda *a: asked.append(a[0]) or answer,
                                on_export=lambda dest: package.export_theme(t.path, dest, builtins))
    gtk = types.SimpleNamespace(FileChooserAction=types.SimpleNamespace(SAVE=0),
                                ResponseType=types.SimpleNamespace(OK=1))
    app_method("open_export", Gtk=gtk)(obj)
    assert asked == ["Replace “keep.handtop-theme”?"]
    assert zipfile.is_zipfile(final) == answer


# ---- R07: broken input is a refusal, not a crash ------------------------------------------------
def test_r07_damaged_png_is_refused(tmp_path, builtins):
    def chunk(kind, body):
        return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body))
    bad = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 20, 11, 8, 6, 0, 0, 0))
           + chunk(b"IDAT", b"not-zlib") + chunk(b"IEND", b""))
    archive = tmp_path / "damaged.handtop-theme"
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr("theme.json", json.dumps(minimal()))
        z.writestr("icons/taskbar/battery-3.png", bad)
    with pytest.raises(theme.ThemeError) as e:
        package.import_theme(str(archive), str(tmp_path / "themes"), builtins, decode=True)
    assert any("damaged" in p.message for p in e.value.problems)


@pytest.mark.parametrize("depth", [40, 30000])
def test_r07_deep_json_is_refused(tmp_path, depth):
    p = tmp_path / "deep"
    p.mkdir()
    (p / "theme.json").write_text('{"x":' + "[" * depth + "0" + "]" * depth + "}")
    t = theme.load(str(p))
    assert any("deeply" in x.message for x in t.errors)


# ---- R08 / R09 / R13 -----------------------------------------------------------------------------
def test_r08_bad_description_becomes_empty(tmp_path, builtins):
    t = theme.load(write_theme(str(tmp_path), minimal(description={"x": 1}, author=5)), builtins)
    assert not t.errors and t.description == "" and t.author == ""


@pytest.mark.parametrize("wp,pal", [({"color": "#11223380"}, {}), ({}, {"bg": "#44556680"})])
def test_r09_wallpaper_colour_has_no_alpha(tmp_path, builtins, wp, pal):
    t = theme.load(write_theme(str(tmp_path), minimal(wallpaper=wp, palette=pal)), builtins)
    assert not t.errors and len(t.wallpaper["color"]) == 7
    assert f"WALLPAPER_COLOR='{t.wallpaper['color']}'" in render.theme_env(t, "/s")


def test_r13_status_style_is_gone(tmp_path, builtins):
    t = theme.load(write_theme(str(tmp_path), minimal(status_screen={"style": "solid"})), builtins)
    assert not t.errors and any(p.where == "status_screen" for p in t.problems)
    assert "STATUS_STYLE" not in render.theme_env(t, "/s")


# ---- R10: switching back starts a stopped wallpaper / notifications ------------------------------
@pytest.mark.parametrize("live", [True, False])
def test_r10_stopped_components_start_in_the_session(cli, monkeypatch, live):
    started, restarted = [], []
    monkeypatch.setattr(cli, "_start", started.append)
    monkeypatch.setattr(cli, "_restart", restarted.append)
    monkeypatch.setattr(cli, "_pids", lambda n: [1] if n == "waybar" or (n == "labwc" and live) else [])
    monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-0")
    cli.apply("audit-a")
    assert restarted == ["waybar"]
    assert started == (["swaybg", "mako"] if live else [])


# ---- R12: external commands have a time limit ----------------------------------------------------
def test_r12_stuck_command_counts_as_failed(cli):
    r = cli._run(["sleep", "5"], 0.2)
    assert r.returncode != 0
    assert cli._run(["no-such-command-here"], 1).returncode != 0
    assert cli._run(["true"], 5).returncode == 0
    assert isinstance(r, subprocess.CompletedProcess)


# ---- review of the extra themes (D01-D04, 2026-11-11) --------------------------------------------
EXTRA = os.path.join(REPO, "src", "theme", "extra")
EXTRA_IDS = sorted(os.listdir(EXTRA)) if os.path.isdir(EXTRA) else []


@pytest.mark.parametrize("tid", EXTRA_IDS)
def test_d01_hotspots_on_the_drawing(tid):
    """Each pointer's hotspot is on an opaque pixel (Pocket's moved off when the art was centred)."""
    Image = pytest.importorskip("PIL.Image")
    with open(os.path.join(EXTRA, tid, "theme.json")) as f:
        cur = json.load(f).get("cursor", {})
    for shape, (x, y) in cur.get("hotspots", {}).items():
        img = Image.open(os.path.join(EXTRA, tid, "cursors", f"{shape}.png")).convert("RGBA")
        assert img.getpixel((x, y))[3] > 0, (tid, shape, x, y)


@pytest.mark.parametrize("tid", EXTRA_IDS)
def test_d03_headerbar_title_colour_spares_buttons(tid):
    """A colour for every label in a header bar also hits its buttons' labels (white on white)."""
    f = os.path.join(EXTRA, tid, "css", "apps.css")
    if os.path.exists(f):
        with open(f) as fh:
            css = fh.read()
        assert "headerbar label" not in css and ".titlebar label" not in css


def test_d04_preview_tiles_a_tiled_wallpaper(tmp_path, builtins):
    cairo = pytest.importorskip("cairo")
    from handtop_theme import preview
    tile = tmp_path / "w.png"
    s = cairo.ImageSurface(cairo.FORMAT_ARGB32, 8, 8)
    cr = cairo.Context(s)
    cr.set_source_rgb(1, 0, 0)
    cr.paint()
    s.write_to_png(str(tile))
    t = theme.load(os.path.join(builtins, "handtop-dark"), builtins)
    t.wallpaper = {"color": "#000000", "image": str(tile), "mode": "tile"}
    out = preview.draw(t, 640, 480, own_picture=False)
    data, stride = out.get_data(), out.get_stride()
    b, g, r, a = data[2 * stride + 4 * 2: 2 * stride + 4 * 2 + 4]       # (2, 2): a corner tile
    assert (r, g, b) == (255, 0, 0)
