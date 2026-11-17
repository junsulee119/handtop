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
