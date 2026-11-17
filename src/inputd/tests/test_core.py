"""Unit tests for rg35xxh_inputd.core (no hardware, no evdev). Run: python3 tests/test_core.py"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from rg35xxh_inputd.core import Core, PointerLayout  # noqa: E402


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
    assert 215 <= sum(a[1] for a in out if a[0] == "rel") <= 235  # 0.5 x 450 = 225 px/s
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


def test_request_gamepad_from_app():
    c = Core()
    c.tick(0.0)
    assert ("mode", "gamepad") in c.request_gamepad()
    assert c.mode == "gamepad"
    assert c.request_gamepad() == []
    # No Start press to swallow: the next tap reaches the virtual pad.
    assert c.button("start", True, 1.0) == [("pad_key", "BTN_START", 1)]
    assert c.button("start", False, 1.1) == [("pad_key", "BTN_START", 0)]


def test_request_desktop_when_bt_link_ends():
    c = Core()
    c.tick(0.0)
    assert c.request_desktop() == []          # already in desktop mode
    c.request_gamepad()
    c.button("a", True, 1.0)                  # A held on the remote pad when the link ends
    assert c.request_desktop() == [("mode", "desktop")]
    assert c.mode == "desktop"
    assert c.button("a", False, 1.2) == []    # its release must not click in desktop mode


def test_bt_mode_exits_with_combo_not_start_hold():
    c = Core()
    c.tick(0.0)
    c.request_gamepad(combo_exit=True)
    assert c.button("start", True, 1.0) == [("pad_key", "BTN_START", 1)]
    assert ("mode", "desktop") not in c.tick(3.0)       # long Start press: still BT mode
    assert c.mode == "gamepad"
    c.button("select", True, 3.1)
    c.button("l1", True, 3.2)
    out = c.button("r1", True, 3.3)
    assert out[-1] == ("mode", "desktop") and c.mode == "desktop"
    for b in ("BTN_SELECT", "BTN_START", "BTN_TL", "BTN_TR"):
        assert ("pad_key", b, 0) in out
    assert not c.combo_exit
    for b in ("r1", "l1", "select", "start"):             # releases do nothing in desktop mode
        assert c.button(b, False, 3.5) == []




def ext_core():
    c = Core()
    c.tick(0.0)
    c.request_gamepad(combo_exit=True, f_buttons=True)
    return c


def test_external_f_tap_is_home():
    c = ext_core()
    assert c.button("f", True, 1.0) == []
    assert c.button("f", False, 1.15) == [("pad_key", "BTN_MODE", 1)]
    out, t = run_ticks(c, 1.15, 0.3)
    assert out.count(("pad_key", "BTN_MODE", 0)) == 1      # released by itself ~0.1 s later
    assert ("pad_key", "BTN_MODE", 1) not in out


def test_external_f_hold_holds_home():
    c = ext_core()
    c.button("f", True, 1.0)
    out, t = run_ticks(c, 1.0, 1.0)
    assert out == [("pad_key", "BTN_MODE", 1)]               # after 0.6 s, once
    assert c.button("f", False, t) == [("pad_key", "BTN_MODE", 0)]
    out, t = run_ticks(c, t, 0.3)
    assert out == []


def test_external_f_vol_is_brightness_not_home():
    c = ext_core()
    c.button("f", True, 1.0)
    assert c.button("vol_up", True, 1.05) == [("cmd", "brightness_up")]
    c.button("vol_up", False, 1.1)
    out, t = run_ticks(c, 1.1, 1.0)
    assert [a for a in out if a[0] == "pad_key"] == []
    assert c.button("f", False, t) == []


def test_external_f_select_is_capture():
    c = ext_core()
    c.button("f", True, 1.0)
    assert c.button("select", True, 1.05) == [("pad_key", "KEY_RECORD", 1)]
    c.button("f", False, 1.1)                                # F released first: no Home
    assert c.button("select", False, 1.2) == [("pad_key", "KEY_RECORD", 0)]
    out, t = run_ticks(c, 1.2, 1.0)
    assert out == []
    assert c.button("select", True, t) == [("pad_key", "BTN_SELECT", 1)]   # plain Select again


def test_f_does_nothing_in_local_gamepad_mode():
    c = Core()
    c.tick(0.0)
    c.button("start", True, 0.1); c.button("start", False, 0.15)
    assert c.mode == "gamepad"
    c.button("f", True, 1.0)
    out, t = run_ticks(c, 1.0, 1.0)
    assert out == [] and c.button("f", False, t) == []
    c.button("f", True, t)
    assert c.button("select", True, t + 0.05) == [("pad_key", "BTN_SELECT", 1)]


def test_f_does_nothing_in_xbox_external_modes():
    c = Core()
    c.tick(0.0)
    c.request_gamepad(combo_exit=True)                       # BT / wired Xbox: no Guide (Game Bar)
    c.button("f", True, 1.0)
    out, t = run_ticks(c, 1.0, 1.0)
    assert out == [] and c.button("f", False, t) == []
    c.button("f", True, t)
    assert c.button("select", True, t + 0.05) == [("pad_key", "BTN_SELECT", 1)]


def test_external_home_state_cleared_when_mode_ends():
    c = ext_core()
    c.button("f", True, 1.0)
    run_ticks(c, 1.0, 1.0)                                   # Home held
    assert c.home_down
    c.request_desktop()
    assert not c.home_down and c.mode == "desktop"
    assert c.button("f", False, 2.5) == []


EXTEND = [{"x": 0, "y": 0, "w": 1920, "h": 1080, "scale": 2.754},     # monitor
          {"x": 640, "y": 1080, "w": 640, "h": 480, "scale": 1.0}]     # handheld below, centred


def test_pointer_scale_speeds_up_pointer():
    c = Core()
    c.axis("lx", 1.0, 0.0)
    out1, _ = run_ticks(c, 0.0, 1.0)
    c2 = Core()
    c2.pointer_scale = 2.0
    c2.axis("lx", 1.0, 0.0)
    out2, _ = run_ticks(c2, 0.0, 1.0)
    d1 = sum(a[1] for a in out1 if a[0] == "rel")
    d2 = sum(a[1] for a in out2 if a[0] == "rel")
    assert abs(d2 - 2 * d1) <= 2, (d1, d2)


def test_layout_starts_on_first_output_and_picks_its_speed():
    lay = PointerLayout(EXTEND)
    assert (lay.x, lay.y) == (960, 540)
    assert abs(lay.scale() - 2.754) < 1e-6
    assert lay.scale(0.0) == 1.0              # display_speed_scale = 0: off
    assert abs(lay.scale(0.5) - 1.877) < 1e-6


def test_layout_crosses_to_handheld_only_where_it_touches():
    lay = PointerLayout(EXTEND)
    for _ in range(100):                       # straight down from the middle: onto the handheld
        lay.move(0, 10)
    assert lay.y >= 1080 and lay.scale() == 1.0, (lay.x, lay.y)
    lay2 = PointerLayout(EXTEND)
    lay2.move(-860, 0)                         # to the left part of the monitor (x 100) ...
    for _ in range(100):                       # ... then down: no handheld below, stays on the monitor
        lay2.move(0, 10)
    assert (lay2.x, lay2.y) == (100, 1079) and abs(lay2.scale() - 2.754) < 1e-6, (lay2.x, lay2.y)


def test_layout_change_keeps_or_clamps_position():
    lay = PointerLayout([{"x": 0, "y": 0, "w": 640, "h": 480, "scale": 1.0}])   # handheld only
    lay.move(-1000, -1000)
    assert (lay.x, lay.y) == (0, 0)
    lay.set_rects([{"x": 0, "y": 0, "w": 1920, "h": 1080, "scale": 2.754}])     # monitor only
    assert (lay.x, lay.y) == (0, 0) and abs(lay.scale() - 2.754) < 1e-6
    lay.set_rects([])                          # no layout: speed 1
    assert lay.scale() == 1.0



def test_osk_hold_a_repeats():
    c = Core()
    c.set_osk_visible(True)
    assert c.button("a", True, 0) == [("osk", "press")]
    out, t = run_ticks(c, 0, 0.45)
    assert [a for a in out if a[0] == "osk"] == []            # not before the delay
    out, t = run_ticks(c, t, 0.30)
    reps = [a for a in out if a == ("osk", "repeat")]
    assert 3 <= len(reps) <= 6                                # every 0.06 s after 0.5 s
    assert c.button("a", False, t) == [("osk", "release")]
    out, _ = run_ticks(c, t, 0.3)
    assert ("osk", "repeat") not in out


def test_osk_l2_is_shift_only_while_open():
    c = Core()
    c.set_osk_visible(True)
    assert c.button("l2", True, 0) == [("osk", "shift")]
    assert c.button("l2", False, 0.1) == []
    c.set_osk_visible(False)
    assert c.button("l2", True, 1) == []                     # default binding: none
    assert c.button("l2", False, 1.1) == []



# ---- config file: a bad value keeps the default instead of stopping the daemon
# (codebase audit 2026-10-30, M04)
def _load_conf(text):
    import tempfile
    from rg35xxh_inputd import config
    with tempfile.TemporaryDirectory() as tmp:
        p = os.path.join(tmp, "input.conf")
        with open(p, "w") as f:
            f.write(text)
        return config.load([p])


def test_config_bad_boolean_keeps_default():
    _, _, hw, _ = _load_conf("[hardware]\ninvert_lx = maybe\ninvert_ly = yes\n")
    assert hw["invert_lx"] is False and hw["invert_ly"] is True


def test_config_numbers_outside_range_keep_default():
    s, _, _, _ = _load_conf("[settings]\npointer_max_speed = inf\ndeadzone = 1\n"
                            "pointer_curve = nan\nscroll_speed = -3\nhaptic_strength = 0.5\n")
    assert "pointer_max_speed" not in s and "deadzone" not in s
    assert "pointer_curve" not in s and "scroll_speed" not in s
    assert s["haptic_strength"] == 0.5


def test_config_kept_defaults_run():
    s, b, _, _ = _load_conf("[settings]\ndeadzone = 1\npointer_max_speed = inf\n")
    c = Core(s, b)
    c.axis("lx", 0.7, 0.0)
    c.axis("ly", 0.7, 0.0)
    out, _ = run_ticks(c, 0.0, 0.2)
    assert any(a[0] == "rel" for a in out)


def test_config_unknown_key_keeps_default():
    from rg35xxh_inputd import config
    real = config._known_key
    config._known_key = lambda name: name != "KEY_DOES_NOT_EXIST"
    try:
        _, b, _, _ = _load_conf("[desktop]\ny = key:KEY_DOES_NOT_EXIST\nselect = key:KEY_TAB\n")
    finally:
        config._known_key = real
    assert "y" not in b and b["select"] == "key:KEY_TAB"


# ---- settings layers (Controls app): system < profile < trial < boot partition, per key
def _layers(files, now=1000.0):
    import tempfile
    from rg35xxh_inputd import config
    tmp = tempfile.mkdtemp()
    layers = []
    for kind in ("system", "profile", "trial", "boot"):
        p = os.path.join(tmp, kind + ".conf")
        if kind in files:
            with open(p, "w") as f:
                f.write(files[kind])
        layers.append((kind, p))
    return config.load_layers(layers, now=now)


def test_layers_merge_per_key_and_boot_wins():
    cfg = _layers({"system": "[settings]\npointer_max_speed = 450\nscroll_speed = 8\n[desktop]\na = click_left\n",
                   "profile": "[settings]\npointer_max_speed = 600\n[desktop]\na = none\ny = copy\n",
                   "boot": "[desktop]\na = click_left\n[hardware]\ninvert_lx = yes\n"})
    assert cfg.settings == {"pointer_max_speed": 600.0, "scroll_speed": 8.0}
    assert cfg.bindings == {"a": "click_left", "y": "copy"}
    assert cfg.hardware["invert_lx"] is True and cfg.hardware["invert_ly"] is False
    assert cfg.locked == {"desktop.a", "hardware.invert_lx"}


def test_layers_bad_value_in_profile_keeps_lower_layer():
    cfg = _layers({"system": "[settings]\ndeadzone = 0.2\n", "profile": "[settings]\ndeadzone = 5\n"})
    assert cfg.settings["deadzone"] == 0.2


def test_trial_applies_until_it_expires():
    files = {"profile": "[desktop]\na = click_left\n",
             "trial": "[trial]\nexpires = 1015\n[desktop]\na = none\n"}
    cfg = _layers(files, now=1000.0)
    assert cfg.bindings["a"] == "none" and not cfg.trial_expired
    cfg = _layers(files, now=1015.0)
    assert cfg.bindings["a"] == "click_left" and cfg.trial_expired


def test_trial_without_expiry_is_ignored():
    cfg = _layers({"trial": "[desktop]\na = none\n"})
    assert "a" not in cfg.bindings and cfg.trial_expired


def test_reconfigure_releases_held_binding_and_swallows_its_release():
    c = Core()
    assert c.button("a", True, 0.0) == [("mouse", "left", True)]
    out = c.reconfigure({}, {"a": "key:KEY_ENTER"})
    assert out == [("mouse", "left", False)]
    assert c.button("a", False, 0.1) == []                     # not a stray Enter release
    assert c.button("a", True, 0.2) == [("key", "KEY_ENTER", True)]


def test_reconfigure_releases_osk_key():
    c = Core()
    c.set_osk_visible(True)
    assert c.button("a", True, 0.0) == [("osk", "press")]
    out = c.reconfigure({}, {"a": "key:KEY_ENTER"})            # A's binding changes under it
    assert ("osk", "release") in out
    assert c.button("a", False, 0.1) == []


def test_reconfigure_in_gamepad_mode_keeps_pad_and_applies_settings():
    c = Core()
    c.button("start", True, 0.0)
    c.button("start", False, 0.1)
    assert c.mode == "gamepad"
    assert c.button("b", True, 0.2) == [("pad_key", "BTN_A", 1)]
    assert c.reconfigure({"start_hold_seconds": 2.0}, {"b": "copy"}) == []
    assert c.button("b", False, 0.3) == [("pad_key", "BTN_A", 0)]
    assert c.s["start_hold_seconds"] == 2.0 and c.bind["b"] == "copy"


def _template():
    from rg35xxh_inputd import config
    here = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(here, "..", "..", "..", "overlay", "etc", "rg35xxh", "input.conf")) as f:
        return config.boot_template(f.read())


def test_shipped_boot_file_locks_nothing():
    cfg = _layers({"profile": "[desktop]\na = none\n", "boot": _template()})
    assert cfg.locked == set() and cfg.bindings["a"] == "none" and cfg.app_settings


def test_uncommenting_one_line_in_the_boot_file_wins():
    boot = _template().replace("# a = click_left", "a = click_left", 1)
    cfg = _layers({"profile": "[desktop]\na = none\n", "boot": boot})
    assert cfg.locked == {"desktop.a"} and cfg.bindings["a"] == "click_left"


def test_rescue_switch_ignores_profile_and_trial():
    boot = _template().replace("# use_app_settings = no", "use_app_settings = no", 1)
    cfg = _layers({"system": "[settings]\nscroll_speed = 9\n",
                   "profile": "[desktop]\na = none\n[settings]\nscroll_speed = 30\n",
                   "trial": "[trial]\nexpires = 2000\n[desktop]\nb = none\n", "boot": boot})
    assert not cfg.app_settings
    assert "a" not in cfg.bindings and "b" not in cfg.bindings and cfg.settings["scroll_speed"] == 9


def test_minimal_controls_check():
    from rg35xxh_inputd import config
    assert config.minimal_problems({}, {}) == []
    assert len(config.minimal_problems({}, {"a": "none"})) == 1                       # no left click
    assert config.minimal_problems({}, {"a": "none", "y": "click_left"}) == []        # moved, fine
    assert config.minimal_problems({"deadzone": 0.9}, {}) == []                       # D-pad still moves it
    assert len(config.minimal_problems({"deadzone": 0.9, "dpad_speed_ratio": 0.05}, {})) == 1
    assert len(config.minimal_problems({"pointer_max_speed": 20}, {"a": "none"})) == 2


# ---- options added for the Controls app
def _scroll(c):
    out, _ = run_ticks(c, 0.0, 0.3)
    return sum(a[1] for a in out if a[0] == "wheel"), sum(a[2] for a in out if a[0] == "wheel")


def test_natural_scroll_reverses_both_directions():
    c = Core()
    c.axis("ry", -0.8, 0.0)                     # stick up
    c.axis("rx", 0.8, 0.0)                      # and right
    v, h = _scroll(c)
    n = Core({"natural_scroll": True})
    n.axis("ry", -0.8, 0.0)
    n.axis("rx", 0.8, 0.0)
    nv, nh = _scroll(n)
    assert v > 0 and h > 0 and nv < 0 and nh < 0


def test_swap_sticks_moves_pointer_with_the_right_stick():
    c = Core({"swap_sticks": True})
    c.axis("rx", 0.8, 0.0)
    out, _ = run_ticks(c, 0.0, 0.2)
    assert any(a[0] == "rel" and a[1] > 0 for a in out)
    assert not any(a[0] == "wheel" for a in out)
    c.axis("rx", 0.0, 0.3)
    c.axis("ly", -0.8, 0.3)
    out, _ = run_ticks(c, 0.3, 0.2)
    assert any(a[0] == "wheel" for a in out) and not any(a[0] == "rel" for a in out)


def _to_gamepad(c):
    c.button("start", True, 0.0)
    c.button("start", False, 0.1)
    assert c.mode == "gamepad"


def test_pad_layout_by_label_local_mode_only():
    c = Core({"pad_layout": "label"})
    _to_gamepad(c)
    assert c.button("a", True, 0.2) == [("pad_key", "BTN_A", 1)]
    assert c.button("a", False, 0.3) == [("pad_key", "BTN_A", 0)]
    e = Core({"pad_layout": "label"})
    e.request_gamepad(combo_exit=True)          # External Controller: always by position
    assert e.button("a", True, 0.2) == [("pad_key", "BTN_B", 1)]


def test_pad_layout_switch_releases_held_face_button():
    c = Core()
    _to_gamepad(c)
    assert c.button("b", True, 0.2) == [("pad_key", "BTN_A", 1)]
    assert c.reconfigure({"pad_layout": "label"}, {}) == [("pad_key", "BTN_A", 0)]
    assert c.button("b", False, 0.3) == []      # not a stray BTN_B release
    assert c.button("b", True, 0.4) == [("pad_key", "BTN_B", 1)]


def test_mouse_back_forward_combo_and_launch():
    c = Core(bindings={"y": "click_back", "select": "click_forward", "l2": "combo:KEY_LEFTALT+KEY_TAB",
                       "r3": "launch:chromium"})
    assert c.button("y", True, 0.0) == [("mouse", "back", True)]
    assert c.button("select", True, 0.0) == [("mouse", "forward", True)]
    assert c.button("l2", True, 0.0) == [("key", "KEY_LEFTALT", True), ("key", "KEY_TAB", True)]
    assert c.button("l2", False, 0.1) == [("key", "KEY_TAB", False), ("key", "KEY_LEFTALT", False)]
    assert c.button("r3", True, 0.0) == [("launch", "chromium")]
    assert c.button("r3", False, 0.1) == []


def test_reconfigure_releases_a_held_combo_in_reverse():
    c = Core(bindings={"l2": "combo:KEY_LEFTCTRL+KEY_LEFTSHIFT+KEY_T"})
    c.button("l2", True, 0.0)
    assert c.reconfigure({}, {}) == [("key", "KEY_T", False), ("key", "KEY_LEFTSHIFT", False),
                                     ("key", "KEY_LEFTCTRL", False)]


def test_config_new_options_validated():
    s, b, _, _ = _load_conf("[settings]\nnatural_scroll = yes\nswap_sticks = maybe\npad_layout = Label\n"
                            "[desktop]\ny = combo:KEY_LEFTCTRL+KEY_C\nx = combo:KEY_A\nl2 = launch:../evil\n"
                            "r3 = launch:org.xfce.mousepad\nselect = click_back\n")
    assert s == {"natural_scroll": True, "pad_layout": "label"}
    assert b == {"y": "combo:KEY_LEFTCTRL+KEY_C", "r3": "launch:org.xfce.mousepad", "select": "click_back"}


def test_reconfigure_keeps_a_held_button_whose_binding_did_not_change():
    """Dragging the Controls app's vibration slider holds A while the profile is saved: the drag
    must not be cut (2026-11-17)."""
    c = Core()
    assert c.button("a", True, 0.0) == [("mouse", "left", True)]
    assert c.reconfigure({"haptic_strength": 0.5}, {}) == []
    assert c.button("a", False, 0.2) == [("mouse", "left", False)]


def test_reconfigure_keeps_the_osk_key_when_bindings_stay():
    c = Core()
    c.set_osk_visible(True)
    c.button("a", True, 0.0)
    assert c.reconfigure({"scroll_speed": 3.0}, {"y": "copy"}) == []
    assert c.button("a", False, 0.1) == [("osk", "release")]


# ---- the formerly fixed controls (Controls app, Advanced)
def test_dpad_direction_bound_to_a_key_and_others_keep_the_pointer():
    c = Core(bindings={"up": "key:KEY_UP"})
    assert c.button("up", True, 0.0) == [("key", "KEY_UP", True)]
    out, t = run_ticks(c, 0.0, 0.1)
    assert not any(a[0] == "rel" for a in out)              # no pointer motion from it
    assert c.button("up", False, t) == [("key", "KEY_UP", False)]
    c.button("right", True, t)
    out, _ = run_ticks(c, t, 0.1)
    assert any(a[0] == "rel" and a[1] > 0 for a in out)


def test_dpad_still_moves_the_keyboard_selection():
    c = Core(bindings={"up": "key:KEY_UP"})
    c.set_osk_visible(True)
    assert c.button("up", True, 0.0) == [("osk", "move", 0, -1)]


def test_volume_rebound_and_f_plus_volume_still_brightness():
    c = Core(bindings={"vol_up": "key:KEY_PAGEUP", "vol_down": "brightness_down"})
    assert c.button("vol_up", True, 0.0) == [("key", "KEY_PAGEUP", True)]
    assert c.button("vol_up", False, 0.1) == [("key", "KEY_PAGEUP", False)]
    assert c.button("vol_down", True, 0.2) == [("cmd", "brightness_down")]
    c.button("vol_down", False, 0.3)
    c.button("f", True, 0.4)
    assert c.button("vol_up", True, 0.5) == [("cmd", "brightness_up")]


def test_f_tap_and_power_tap_bindings_hold_still_shuts_down():
    c = Core(bindings={"f": "osk_toggle", "power": "key:KEY_ESC"})
    c.button("f", True, 0.0)
    assert c.button("f", False, 0.2) == [("osk", "toggle")]
    c.button("power", True, 1.0)
    assert c.button("power", False, 1.2) == [("key", "KEY_ESC", True), ("key", "KEY_ESC", False)]
    c.button("power", True, 2.0)
    out, _ = run_ticks(c, 2.0, 3.2)
    assert ("shutdown",) in out


def test_gamepad_mode_keeps_dpad_vol_and_power():
    c = Core(bindings={"up": "key:KEY_UP", "vol_up": "click_left", "power": "none", "f": "copy"})
    c.button("start", True, 0.0)
    c.button("start", False, 0.1)
    assert c.button("up", True, 0.2)[0][0] == "pad_abs"
    assert c.button("vol_up", True, 0.3) == [("cmd", "volume_up")]
    c.button("power", True, 0.4)
    assert c.button("power", False, 0.5) == [("cmd", "power_menu")]
    c.button("f", True, 0.6)
    assert c.button("f", False, 0.7) == []


def test_dpad_bound_key_released_on_gamepad_switch_and_pointer_back_after():
    c = Core(bindings={"up": "key:KEY_UP"})
    c.button("up", True, 0.0)
    out = c.button("start", True, 0.1)
    assert ("key", "KEY_UP", False) in out
    c.button("start", False, 0.2)
    c.button("up", False, 0.3)
    c.reconfigure({}, {})                                     # up back to the pointer
    c.button("start", True, 0.4)                             # (gamepad: hold Start to leave)
    run_ticks(c, 0.4, 1.2)
    c.button("start", False, 1.7)
    assert c.mode == "desktop"
    c.button("up", True, 2.0)
    out, _ = run_ticks(c, 2.0, 0.1)
    assert any(a[0] == "rel" and a[2] < 0 for a in out)


def test_minimal_check_counts_the_dpad_only_with_all_four_on_the_pointer():
    from rg35xxh_inputd import config
    assert config.minimal_problems({"deadzone": 0.9}, {}) == []
    assert len(config.minimal_problems({"deadzone": 0.9}, {"left": "key:KEY_LEFT"})) == 1


def test_config_pointer_only_for_dpad():
    _, b, _, _ = _load_conf("[desktop]\nup = pointer\na = pointer\npower = key:KEY_ESC\nvol_up = brightness_up\n")
    assert b == {"up": "pointer", "power": "key:KEY_ESC", "vol_up": "brightness_up"}


# ---- combinations (hold-modifier style)
def test_combo_fires_instead_of_the_second_and_first_taps_alone():
    c = Core(bindings={"l1+a": "key:KEY_SYSRQ"})
    assert c.button("l1", True, 0.0) == []                     # waits: L1 starts a combination
    assert c.button("a", True, 0.1) == [("key", "KEY_SYSRQ", True)]
    assert c.button("a", False, 0.2) == [("key", "KEY_SYSRQ", False)]
    assert c.button("l1", False, 0.3) == []                    # used by the combination: no Esc
    c.button("l1", True, 1.0)
    assert c.button("l1", False, 1.1) == [("key", "KEY_ESC", True), ("key", "KEY_ESC", False)]
    assert c.button("a", True, 2.0) == [("mouse", "left", True)]  # A alone: unchanged


def test_combo_with_f_as_the_first_and_f_plus_volume_still_brightness():
    c = Core(bindings={"f+x": "osk_toggle", "f": "copy"})
    c.button("f", True, 0.0)
    assert c.button("x", True, 0.1) == [("osk", "toggle")]
    c.button("x", False, 0.2)
    assert c.button("f", False, 0.3) == []                     # no F-tap copy after the combination
    c.button("f", True, 1.0)
    assert c.button("vol_up", True, 1.1) == [("cmd", "brightness_up")]


def test_combos_off_while_the_keyboard_is_open_and_in_gamepad_mode():
    c = Core(bindings={"l1+a": "key:KEY_SYSRQ"})
    c.set_osk_visible(True)
    c.button("l1", True, 0.0)
    assert c.button("a", True, 0.1) == [("osk", "press")]
    d = Core(bindings={"l1+a": "key:KEY_SYSRQ"})
    d.button("start", True, 0.0)
    d.button("start", False, 0.1)
    d.button("l1", True, 0.2)
    assert d.button("a", True, 0.3) == [("pad_key", "BTN_B", 1)]


def test_config_combos_validated():
    _, b, _, _ = _load_conf("[desktop]\nl1+a = key:KEY_SYSRQ\nf+up = osk_toggle\nvol_up+a = copy\n"
                            "a+a = copy\npower+a = copy\nl1+r1 = pointer\n")
    assert b == {"l1+a": "key:KEY_SYSRQ", "f+up": "osk_toggle"}

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
