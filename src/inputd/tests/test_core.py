"""Unit tests for rg35xxh_inputd.core (no hardware, no evdev). Run: python3 tests/test_core.py"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from rg35xxh_inputd.core import Core  # noqa: E402


def kinds(actions):
    return [a[0] for a in actions]


def run_ticks(c, t0, seconds, step=0.01):
    out = []
    t = t0
    while t < t0 + seconds - 1e-9:
        t += step
        out += c.tick(t)
    return out, t


def test_face_buttons_desktop():
    c = Core()
    assert c.button("a", True, 0) == [("mouse", "left", True)]
    assert c.button("a", False, 0.1) == [("mouse", "left", False)]
    assert c.button("b", True, 0) == [("mouse", "right", True)]
    assert c.button("b", False, 0.1) == [("mouse", "right", False)]
    assert c.button("y", True, 0) == []
    assert c.button("l1", True, 0) == [("key", "KEY_ESC", True)]
    assert c.button("l1", False, 0.1) == [("key", "KEY_ESC", False)]
    assert c.button("r1", True, 0) == [("key", "KEY_ENTER", True)]
    assert c.button("r2", True, 0) == [("key", "KEY_BACKSPACE", True)]
    assert c.button("l2", True, 0) == []
    assert c.button("l3", True, 0) == [("clipboard", "copy")]
    assert c.button("l3", False, 0.1) == []
    assert c.button("r3", True, 0) == [("clipboard", "paste")]
    assert c.button("x", True, 0) == [("osk", "toggle")]
    assert c.button("select", True, 0) == []


def test_pointer_left_stick_deadzone_and_speed():
    c = Core()
    c.tick(0.0)
    c.axis("lx", 0.10, 0.0)  # inside dead zone
    out, t = run_ticks(c, 0.0, 0.5)
    assert out == []
    c.axis("lx", 1.0, t)  # full right
    out, t = run_ticks(c, t, 1.0)
    total = sum(a[1] for a in out if a[0] == "rel")
    assert 425 <= total <= 455, total  # 450 px/s
    c.axis("lx", 0.0, t)
    c.axis("ly", -0.5, t)  # half up: slow (curve)
    out, t = run_ticks(c, t, 1.0)
    dy = sum(a[2] for a in out if a[0] == "rel")
    assert -125 < dy < -50, dy


def test_dpad_pointer_and_osk_navigation():
    c = Core()
    c.tick(0.0)
    c.button("right", True, 0.0)
    out, t = run_ticks(c, 0.0, 1.0)
    assert 275 <= sum(a[1] for a in out if a[0] == "rel") <= 295  # 286 px/s
    c.button("right", False, t)
    # Keyboard open: D-pad moves the key highlight, with auto-repeat.
    c.set_osk_visible(True)
    assert c.button("down", True, t) == [("osk", "move", 0, 1)]
    out, t2 = run_ticks(c, t, 0.6)
    assert [a for a in out if a[0] == "rel"] == []
    moves = [a for a in out if a[0] == "osk"]
    assert 2 <= len(moves) <= 3, moves  # 0.4 s delay, then every 0.09 s
    c.button("down", False, t2)
    # Button bound to click_left types the selected key instead of clicking.
    assert c.button("a", True, t2) == [("osk", "press")]
    assert c.button("a", False, t2 + 0.1) == [("osk", "release")]


def test_osk_follows_click_left_binding():
    # If the user remaps click_left to 'b' (e.g. PlayStation style), OSK typing follows 'b'.
    c = Core(bindings={"b": "click_left", "a": "click_right"})
    c.set_osk_visible(True)
    assert c.button("b", True, 0) == [("osk", "press")]
    assert c.button("b", False, 0.1) == [("osk", "release")]
    # 'a' is right click now, not typing
    assert c.button("a", True, 0.2) == [("mouse", "right", True)]


def test_a_release_matches_press_when_osk_toggles():
    c = Core()
    assert c.button("a", True, 0) == [("mouse", "left", True)]
    c.set_osk_visible(True)
    assert c.button("a", False, 0.2) == [("mouse", "left", False)]


def test_scroll_right_stick_both_axes():
    c = Core()
    c.tick(0.0)
    c.axis("ry", -1.0, 0.0)  # stick up -> scroll up (positive)
    out, t = run_ticks(c, 0.0, 1.0)
    v = sum(a[1] for a in out if a[0] == "wheel")
    assert 940 <= v <= 1080, v  # ~8.4 notches * 120
    c.axis("ry", 0.0, t)
    c.axis("rx", 1.0, t)
    out, t = run_ticks(c, t, 0.5)
    h = sum(a[2] for a in out if a[0] == "wheel")
    assert h > 420, h


def test_scroll_log_curve_small_push_is_useful():
    c = Core()
    c.tick(0.0)
    # 30% of the travel past the dead zone -> log curve gives ~55% speed (power curve would give 9%)
    c.axis("ry", -(0.12 + 0.88 * 0.3), 0.0)
    out, t = run_ticks(c, 0.0, 1.0)
    v = sum(a[1] for a in out if a[0] == "wheel")
    assert 500 <= v <= 640, v


def test_volume_and_brightness_hold_repeats():
    c = Core()
    c.tick(0.0)
    assert c.button("vol_up", True, 0.0) == [("cmd", "volume_up")]
    out, t = run_ticks(c, 0.0, 1.0)          # 0.4 s delay, then every 0.12 s -> 5-6 repeats
    reps = [a for a in out if a == ("cmd", "volume_up")]
    assert 5 <= len(reps) <= 6, reps
    c.button("vol_up", False, t)
    out, t = run_ticks(c, t, 1.0)
    assert [a for a in out if a[0] == "cmd"] == []
    # F + Vol- held: brightness repeats, also in gamepad mode
    c.button("start", True, t); c.button("start", False, t + 0.05)
    assert c.mode == "gamepad"
    c.button("f", True, t + 0.1)
    assert c.button("vol_down", True, t + 0.1) == [("cmd", "brightness_down")]
    out, t = run_ticks(c, t + 0.1, 1.0)
    assert len([a for a in out if a == ("cmd", "brightness_down")]) >= 5


def test_power_tap_menu_hold_shutdown_and_cancel():
    c = Core()
    c.tick(0.0)
    c.button("power", True, 0.0)
    assert c.button("power", False, 0.3) == [("cmd", "power_menu")]
    # 2 s hold: cancelled, nothing happens
    c.button("power", True, 1.0)
    out, t = run_ticks(c, 1.0, 2.0)
    assert ("shutdown",) not in out
    assert c.button("power", False, t) == []
    # 3 s hold: shutdown exactly once, release does nothing
    c.button("power", True, 10.0)
    out, t = run_ticks(c, 10.0, 3.5)
    assert out.count(("shutdown",)) == 1
    assert c.button("power", False, t) == []


def test_volume_and_brightness():
    c = Core()
    assert c.button("vol_up", True, 0) == [("cmd", "volume_up")]
    c.button("vol_up", False, 0.1)
    assert c.button("f", True, 0.2) == []
    assert c.button("vol_down", True, 0.3) == [("cmd", "brightness_down")]
    c.button("vol_down", False, 0.4)
    assert c.button("f", False, 0.5) == []
    assert c.button("vol_down", True, 0.6) == [("cmd", "volume_down")]


def test_screen_off_wake_swallows_press():
    c = Core()
    c.set_screen_off(True)
    assert c.button("a", True, 0) == [("screen_wake",)]
    c.set_screen_off(False)
    assert c.button("a", False, 0.1) == []  # no stray click
    c.set_screen_off(True)
    c.button("power", True, 1.0)
    assert c.button("power", False, 1.2) == [("screen_wake",)]


def test_mode_switch_and_gamepad_mapping():
    c = Core()
    c.tick(0.0)
    c.axis("lx", 0.5, 0.0)
    out = c.button("start", True, 0.0)
    assert ("mode", "gamepad") in out
    assert ("pad_abs", "ABS_X", 16384) in out  # current stick state sent on entry
    assert c.button("start", False, 0.2) == []  # the switching press is not forwarded
    # by position: bottom (label B) -> Xbox A, top (label X) -> Xbox Y
    assert c.button("b", True, 1) == [("pad_key", "BTN_A", 1)]
    assert c.button("x", True, 1) == [("pad_key", "BTN_Y", 1)]
    assert c.button("y", True, 1) == [("pad_key", "BTN_X", 1)]
    assert c.button("a", True, 1) == [("pad_key", "BTN_B", 1)]
    assert c.button("l2", True, 1) == [("pad_abs", "ABS_Z", 255)]
    assert c.button("up", True, 1) == [("pad_abs", "ABS_HAT0X", 0), ("pad_abs", "ABS_HAT0Y", -1)]
    assert c.axis("ry", -1.0, 1) == [("pad_abs", "ABS_RY", -32767)]
    assert c.button("f", True, 1) == []  # F never forwarded
    c.button("f", False, 1.1)
    # no pointer motion in gamepad mode
    out, t = run_ticks(c, 1.0, 0.5)
    assert [a for a in out if a[0] in ("rel", "wheel")] == []


def test_start_tap_forwarded_hold_returns_to_desktop():
    c = Core()
    c.tick(0.0)
    c.button("start", True, 0.0)
    c.button("start", False, 0.1)
    assert c.mode == "gamepad"
    assert c.button("start", True, 1.0) == [("pad_key", "BTN_START", 1)]
    assert c.button("start", False, 1.2) == [("pad_key", "BTN_START", 0)]
    c.button("start", True, 2.0)
    out, t = run_ticks(c, 2.0, 1.2)
    assert ("pad_key", "BTN_START", 0) in out and ("mode", "desktop") in out
    assert c.mode == "desktop"
    assert c.button("start", False, t) == []  # does not bounce back to gamepad mode


def test_switch_releases_held_desktop_buttons():
    c = Core()
    c.button("a", True, 0)
    out = c.button("start", True, 0.1)
    assert ("mouse", "left", False) in out


def test_custom_bindings():
    c = Core(bindings={"y": "key:KEY_TAB", "l2": "click_middle", "select": "power_menu"})
    assert c.button("y", True, 0) == [("key", "KEY_TAB", True)]
    assert c.button("l2", True, 0) == [("mouse", "middle", True)]
    assert c.button("select", True, 0) == [("cmd", "power_menu")]


if __name__ == "__main__":
    failed = 0
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_")]
    for name, fn in tests:
        try:
            fn()
            print("ok   ", name)
        except AssertionError as e:
            failed += 1
            print("FAIL ", name, e)
    print(f"{len(tests) - failed}/{len(tests)} passed")
    sys.exit(1 if failed else 0)
