"""Unit tests for handtop_controls.store (profiles, trials) against the input daemon's layers."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(HERE, "..", "..", "inputd"))

import pytest  # noqa: E402

from handtop_controls import store  # noqa: E402
from rg35xxh_inputd import config  # noqa: E402


@pytest.fixture(autouse=True)
def dirs(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path / "run"))
    (tmp_path / "run").mkdir()
    sysconf = tmp_path / "input.conf"
    sysconf.write_text(open(os.path.join(HERE, "..", "..", "..", "overlay", "etc", "rg35xxh", "input.conf")).read())
    monkeypatch.setattr(config, "SYSTEM", str(sysconf))
    monkeypatch.setattr(config, "BOOT", str(tmp_path / "boot.conf"))
    return tmp_path


def test_profile_holds_only_what_differs_and_the_daemon_reads_it():
    v = store.system_values()
    v.settings["scroll_speed"] = 12.0
    v.bindings["y"] = "copy"
    store.write_profile("default", v)
    text = open(config.profile_path("default")).read()
    assert "scroll_speed = 12" in text and "y = copy" in text and "pointer_max_speed" not in text
    eff, cfg = store.effective()
    assert eff.settings["scroll_speed"] == 12 and eff.bindings["y"] == "copy" and not cfg.locked


def test_trial_writes_every_key_so_a_value_set_back_wins_over_the_profile():
    v = store.system_values()
    v.bindings["a"] = "none"
    v.bindings["y"] = "click_left"
    store.write_profile("default", v)
    back = store.system_values()                            # a back to click_left
    store.start_trial(back, now=1000, seconds=15)
    cfg = config.load_layers(now=1001)
    assert cfg.bindings["a"] == "click_left" and cfg.trial_until == 1015


def test_keep_saves_into_the_profile_and_ends_the_trial():
    v = store.system_values()
    v.bindings["x"] = "none"
    store.start_trial(v)
    store.keep(v)
    assert not store.trial_running()
    assert store.read_profile("default")[1] == {"x": "none"}


def test_cancel_leaves_the_profile_alone():
    v = store.system_values()
    v.bindings["x"] = "none"
    store.start_trial(v)
    store.cancel()
    assert not store.trial_running() and store.read_profile("default") == ({}, {}, {})


def test_profiles_new_rename_delete_and_active():
    assert store.profiles() == ["default"]
    v = store.system_values()
    v.settings["natural_scroll"] = True
    store.write_profile("default", v)
    assert store.new_profile("Games", copy_from="default")
    assert not store.new_profile("Games")                       # exists
    assert not store.new_profile("../x")                        # not a name
    store.set_active("Games")
    assert store.rename_profile("Games", "Play")
    assert store.active() == "Play" and store.profiles() == ["default", "Play"]
    assert store.read_profile("Play")[0] == {"natural_scroll": True}
    assert not store.delete_profile("default")
    assert store.delete_profile("Play")
    assert store.active() == "default" and store.profiles() == ["default"]


def test_locked_keys_come_from_the_boot_file(dirs):
    (dirs / "boot.conf").write_text("[desktop]\na = click_left\n")
    _, cfg = store.effective()
    assert cfg.locked == {"desktop.a"}


def test_needs_trial_and_problems():
    assert store.needs_trial("desktop", "a") and store.needs_trial("settings", "deadzone")
    assert not store.needs_trial("settings", "haptic_strength")
    v = store.system_values()
    v.bindings["a"] = "none"
    assert store.problems(v) == ["No button would give a left click."]


def test_describe_actions():
    from handtop_controls import actions as A
    assert A.describe("click_left") == "Left click"
    assert A.describe("key:KEY_ESC") == "Key: Esc"
    assert A.describe("combo:KEY_LEFTCTRL+KEY_LEFTSHIFT+KEY_T") == "Ctrl + Shift + T"
    assert A.describe("launch:chromium", {"chromium": "Web Browser"}) == "Open Web Browser"
    assert A.describe("key:KEY_KPENTER") == "Key: Kpenter"


def test_export_import_and_free_name(tmp_path):
    v = store.system_values()
    v.bindings["y"] = "copy"
    store.write_profile("default", v)
    out = tmp_path / "x.conf"
    store.export_profile("default", str(out))
    assert "y = copy" in out.read_text()
    name = store.free_name("default")
    assert name == "default 2"
    assert store.import_profile(str(out), name) == 1
    assert store.read_profile(name)[1] == {"y": "copy"}
    assert store.free_name("../evil!") == "evil"


# ---- Controls audit 2026-11-17 (controls-audit-2026-11-17/REPORT.md)
def test_removed_combination_is_gone_during_the_trial():   # H01
    before = store.system_values()
    before.bindings["select+a"] = "click_right"
    store.write_profile("default", before)
    after = before.copy()
    del after.bindings["select+a"]
    store.start_trial(after, now=1000)
    assert "select+a" not in config.load_layers(now=1001).bindings
    assert config.load_layers(now=1016).bindings["select+a"] == "click_right"   # undone


def test_switching_to_a_profile_without_a_combination_previews_it_right():   # H01
    old = store.system_values()
    old.bindings["a+b"] = "copy"
    store.write_profile("default", old)
    store.write_profile("Clean", store.system_values())
    store.start_trial(store.profile_values("Clean"), now=1000, name="Clean")
    assert "a+b" not in config.load_layers(now=1001).bindings


def test_saving_keeps_the_profiles_own_value_under_a_boot_lock():   # M03
    own = store.system_values()
    own.bindings["y"] = "copy"
    store.write_profile("default", own)
    open(config.BOOT, "w").write("[desktop]\ny = paste\n")
    shown, cfg = store.effective()
    assert shown.bindings["y"] == "paste" and "desktop.y" in cfg.locked
    shown.settings["scroll_speed"] = 12
    store.write_profile(store.active(), shown)
    store.start_trial(shown, now=1000)
    assert "y = copy" in open(config.trial_path()).read()
    os.unlink(config.BOOT)
    after, _ = store.effective()
    assert after.bindings["y"] == "copy" and after.settings["scroll_speed"] == 12


def test_macro_users_and_rename_cover_every_profile_and_the_boot_file():   # M05
    from rg35xxh_inputd import macros
    macros.save("Shared", [("key", "KEY_A")])
    v = store.system_values()
    v.bindings["y"] = "macro:Shared"
    v.bindings["select+a"] = "macro:Shared"
    store.write_profile("default", v)
    store.write_profile("Other", v)
    assert sorted(store.macro_users("Shared")) == [("Other", "select+a"), ("Other", "y"),
                                                   ("default", "select+a"), ("default", "y")]
    store.rename_macro_refs("Shared", "Renamed")
    assert store.macro_users("Shared") == []
    assert store.read_profile("Other")[1]["select+a"] == "macro:Renamed"
    open(config.BOOT, "w").write("[desktop]\nx = macro:Renamed\n")
    assert ("boot file", "x") in store.macro_users("Renamed")


def test_failed_trial_write_frees_the_app(monkeypatch):   # M04
    import ast
    from types import SimpleNamespace
    src = os.path.join(HERE, "..", "handtop_controls", "app.py")
    tree = ast.parse(open(src).read())
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "App")
    fn = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == "trial")
    ns = {"store": store}
    exec(compile(ast.Module(body=[fn], type_ignores=[]), src, "exec"), ns)
    errors, cancelled = [], []

    def full(*_):
        raise OSError(28, "No space left on device")
    monkeypatch.setattr(store, "cancel", lambda: cancelled.append(1))
    app = SimpleNamespace(busy=False, _trial_run=full, _error=lambda *a: errors.append(a),
                          refresh=lambda: None, _warn=lambda p: True)
    ns["trial"](app, store.system_values())
    assert app.busy is False and errors and cancelled


def test_atomic_write_leaves_no_temp_file_on_failure(monkeypatch, tmp_path):
    p = str(tmp_path / "x.conf")
    monkeypatch.setattr(os, "replace", lambda *a: (_ for _ in ()).throw(OSError(28, "full")))
    with pytest.raises(OSError):
        store._write_atomic(p, "x")
    assert not os.path.exists(p + ".tmp")


# ---------------------------------------------------------------- auto-switch per app
def test_link_moves_an_app_and_the_daemon_reads_it():
    store.new_profile("games")
    store.link_app("retroarch", "games")
    store.link_app("Thunar", "default")
    store.link_app("RetroArch", "default")         # same app in another letter case: moved, not doubled
    assert store.links() == {"Thunar": "default", "RetroArch": "default"}
    assert store.apps_of("default") == ["RetroArch", "Thunar"] and store.linked_to("thunar") == "default"
    assert config.linked_profile(config.read_links(), "retroarch") == "default"
    store.unlink_app("Thunar")
    assert store.links() == {"RetroArch": "default"}
    with pytest.raises(ValueError):
        store.link_app("rg35xxh-controls", "games")    # Controls edits the hand-picked profile
    with pytest.raises(ValueError):
        store.link_app("foot", "../x")


def test_rename_and_delete_carry_the_links():
    store.new_profile("games")
    store.link_app("retroarch", "games")
    store.link_app("foot", "default")
    assert store.rename_profile("games", "retro")
    assert store.links() == {"retroarch": "retro", "foot": "default"}
    assert store.delete_profile("retro")
    assert store.links() == {"foot": "default"}


def test_open_windows_from_the_daemon(dirs):
    assert store.open_windows() == (False, [])
    (dirs / "run" / store.WINDOWS_FILE).write_text(
        '{"windows": [["foot", "foot"], ["Thunar", "Home"], ["foot", "second"], ["rg35xxh-controls", "Controls"],'
        ' [3, "bad"], "bad"], "focused": "foot", "auto": null, "connected": true}')
    assert store.open_windows() == (True, [("foot", "foot"), ("Thunar", "Home")])
    (dirs / "run" / store.WINDOWS_FILE).write_text("not json")
    assert store.open_windows() == (False, [])


def test_window_ids_prefer_startup_wm_class(monkeypatch, tmp_path):
    from handtop_controls import actions as A
    apps = tmp_path / "apps"
    apps.mkdir()
    (apps / "thunar.desktop").write_text("[Desktop Entry]\nType=Application\nName=File Manager\n")
    (apps / "game.desktop").write_text("[Desktop Entry]\nType=Application\nName=Game\nStartupWMClass=GameWin\n")
    (apps / "hidden.desktop").write_text("[Desktop Entry]\nType=Application\nName=H\nNoDisplay=true\n")
    monkeypatch.setattr(A, "APP_DIRS", [str(apps)])
    assert A.window_ids() == [("thunar", "File Manager"), ("GameWin", "Game")]
    assert A.apps() == [("thunar", "File Manager"), ("game", "Game")]
