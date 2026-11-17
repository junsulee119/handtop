"""Unit tests for rg35xxh_inputd.macros (file format, typing map, recorder) and the daemon's player."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from rg35xxh_inputd import macros as M  # noqa: E402


def test_parse_every_step_and_skip_bad_lines():
    text = """# a comment
key KEY_ENTER
combo KEY_LEFTCTRL+KEY_C
down KEY_LEFTSHIFT
up KEY_LEFTSHIFT
click left
press right
release right
text Hello # not a comment here
wait 0.25
move 40 -12
scroll -120 0
launch chromium
do paste
bogus line
key enter
wait 99
move 1 2 3
do mode_gamepad
"""
    steps, problems = M.parse(text)
    assert steps == [("key", "KEY_ENTER"), ("combo", "KEY_LEFTCTRL+KEY_C"), ("down", "KEY_LEFTSHIFT"),
                     ("up", "KEY_LEFTSHIFT"), ("click", "left"), ("press", "right"), ("release", "right"),
                     ("text", "Hello # not a comment here"), ("wait", 0.25), ("move", 40, -12),
                     ("scroll", -120, 0), ("launch", "chromium"), ("do", "paste")]
    assert len(problems) == 5


def test_limits():
    steps, problems = M.parse("wait 10\n" * 40)
    assert sum(s[1] for s in steps) <= M.MAX_WAIT and problems
    steps, problems = M.parse("key KEY_A\n" * (M.MAX_STEPS + 5))
    assert len(steps) == M.MAX_STEPS and problems


def test_format_round_trip():
    steps = [("key", "KEY_A"), ("wait", 0.5), ("text", "hi there"), ("move", -3, 4)]
    assert M.parse(M.format_steps(steps, "t"))[0] == steps


def test_char_key_us_layout():
    assert M.char_key("a") == ([], "KEY_A")
    assert M.char_key("A") == (["KEY_LEFTSHIFT"], "KEY_A")
    assert M.char_key("!") == (["KEY_LEFTSHIFT"], "KEY_1")
    assert M.char_key("?") == (["KEY_LEFTSHIFT"], "KEY_SLASH")
    assert M.char_key(" ") == ([], "KEY_SPACE")
    assert M.char_key("é") is None


def test_recorder_taps_waits_moves_and_pause():
    r = M.Recorder(pointer=True)
    r.resume(0.0)
    r.event(0.00, ("down", "KEY_A"))
    r.event(0.05, ("up", "KEY_A"))                  # let go within 0.3 s: one tap
    r.event(0.50, ("press", "left"))
    r.event(0.50, ("release", "left"))              # nothing between: one click
    for i in range(5):
        r.event(1.0 + i * 0.01, ("move", 2, -1))     # merged
    r.event(1.30, ("scroll", -120, 0))
    r.event(1.31, ("scroll", -120, 0))
    r.resume(5.0)                                   # paused 1.31 .. 5.0: not a wait
    r.event(5.0, ("do", "copy"))
    assert r.finish() == [("key", "KEY_A"), ("wait", 0.5),        # the hold time joins the wait
                          ("click", "left"), ("wait", 0.5), ("move", 10, -5), ("wait", 0.26),
                          ("scroll", -240, 0), ("do", "copy")]


def test_recorder_without_pointer_ignores_moves():
    r = M.Recorder(pointer=False)
    r.resume(0.0)
    r.event(0.0, ("move", 5, 5))
    r.event(0.0, ("press", "left"))
    r.event(0.0, ("release", "left"))
    assert r.finish() == [("click", "left")]


def test_save_load_names(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    M.save("Login", [("text", "user"), ("key", "KEY_TAB")])
    assert M.names() == ["Login"]
    assert M.load("Login")[0] == [("text", "user"), ("key", "KEY_TAB")]


def test_recorder_without_timing_keeps_no_waits():
    r = M.Recorder(pointer=False, timing=False)
    r.resume(0.0)
    r.event(0.0, ("down", "KEY_A"))
    r.event(1.0, ("up", "KEY_A"))
    r.event(3.0, ("press", "left"))
    r.event(3.5, ("release", "left"))
    assert r.finish() == [("key", "KEY_A"), ("click", "left")]


# ---- Controls audit 2026-11-17, M06: what is saved is what plays
def test_save_refuses_what_the_player_would_cut_short(tmp_path, monkeypatch):
    import pytest
    from rg35xxh_inputd import macros
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    for steps, why in (([("text", "a" * 500)] * 140, "KB"), ([("key", "KEY_A")] * 1001, "steps"),
                       ([("wait", 10)] * 31, "waiting")):
        with pytest.raises(ValueError, match=why):
            macros.save("Big", steps)
        assert not os.path.exists(macros.path("Big")) and not os.path.exists(macros.path("Big") + ".tmp")
    macros.save("Fits", [("wait", 10)] * 30)
    assert len(macros.load("Fits")[0]) == 30


def test_recorder_stops_at_the_waiting_limit(tmp_path, monkeypatch):
    from rg35xxh_inputd import macros
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    rec = macros.Recorder(pointer=False, timing=True)
    ok = [rec.event(i * 10, ("key", "KEY_A")) for i in range(34)]
    assert ok.index(False) == 31                      # 30 waits of 10 s fit, the 31st doesn't
    steps = rec.finish()
    macros.save("Long", steps)
    loaded, problems = macros.load("Long")
    assert loaded == steps and not problems


def test_recorder_quick_press_is_a_tap_a_long_one_stays_held():
    r = M.Recorder(pointer=False)
    r.resume(0.0)
    r.event(0.0, ("down", "KEY_ESC"))
    r.event(0.15, ("up", "KEY_ESC"))                 # a real tap, as recorded on the device
    r.event(0.36, ("down", "KEY_ESC"))
    r.event(0.52, ("up", "KEY_ESC"))
    r.event(1.0, ("down", "KEY_LEFTSHIFT"))
    r.event(2.0, ("up", "KEY_LEFTSHIFT"))            # held 1 s: kept as a hold
    r.event(2.1, ("press", "left"))
    r.event(2.2, ("down", "KEY_A"))                  # something between: no merging
    r.event(2.25, ("release", "left"))
    r.event(2.3, ("up", "KEY_A"))
    assert r.finish() == [("key", "KEY_ESC"), ("wait", 0.36), ("key", "KEY_ESC"), ("wait", 0.64),
                          ("down", "KEY_LEFTSHIFT"), ("wait", 1.0), ("up", "KEY_LEFTSHIFT"),
                          ("wait", 0.1), ("press", "left"), ("wait", 0.1), ("down", "KEY_A"),
                          ("wait", 0.05), ("release", "left"), ("wait", 0.05), ("up", "KEY_A")]
    assert abs(r.waited - sum(s[1] for s in r.steps if s[0] == "wait")) < 1e-9
