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
    r.event(0.05, ("up", "KEY_A"))                  # 50 ms later: a wait stays between them
    r.event(0.50, ("press", "left"))
    r.event(0.50, ("release", "left"))              # nothing between: one click
    for i in range(5):
        r.event(1.0 + i * 0.01, ("move", 2, -1))     # merged
    r.event(1.30, ("scroll", -120, 0))
    r.event(1.31, ("scroll", -120, 0))
    r.resume(5.0)                                   # paused 1.31 .. 5.0: not a wait
    r.event(5.0, ("do", "copy"))
    assert r.finish() == [("down", "KEY_A"), ("wait", 0.05), ("up", "KEY_A"), ("wait", 0.45),
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
