"""Input logic for the RG35XX H (hardware independent, unit-tested).

The daemon feeds normalized events in and executes the returned actions:

  core.button(name, pressed, t)   name: a b x y l1 r1 l2 r2 l3 r3 select start f
                                        up down left right  vol_up vol_down  power
  core.axis(name, value, t)       name: lx ly rx ry, value -1.0 .. 1.0 (y: down = +)
  core.tick(t)                    call every ~10 ms; returns movement/hold actions

Every call returns a list of actions (tuples):
  ("rel", dx, dy)                 move pointer (integer pixels)
  ("wheel", v, h)                 hi-res scroll units (120 = one notch); v>0 = up, h>0 = right
  ("mouse", "left"|"right"|"middle", pressed)
  ("key", "KEY_ENTER", pressed)
  ("clipboard", "copy"|"paste")   daemon picks Ctrl(+Shift)+C/V depending on focused app
  ("osk", "toggle") / ("osk", "move", dx, dy) / ("osk", "press") / ("osk", "release")
  ("mode", "gamepad"|"desktop")
  ("pad_key", "BTN_A", value)     virtual Xbox-style pad (gamepad mode)
  ("pad_abs", "ABS_X", value)
  ("cmd", "power_menu"|"volume_up"|"volume_down"|"brightness_up"|"brightness_down")
  ("screen_wake",)
  ("shutdown",)                   daemon: haptic + LED + notification + poweroff
"""

import math

BUTTONS = ("a", "b", "x", "y", "l1", "r1", "l2", "r2", "l3", "r3", "select", "start", "f")
DPAD = ("up", "down", "left", "right")

DEFAULT_SETTINGS = {
    "deadzone": 0.12,              # fraction of stick travel ignored (drift)
    "pointer_max_speed": 450.0,    # px/s at full tilt
    "pointer_curve": 2.0,          # 1 = linear, 2 = slow near centre, fast at the edge
    "dpad_speed": 286.0,           # px/s while a D-pad direction is held
    "scroll_speed": 8.4,          # notches/s at full tilt
    "scroll_log_k": 9.0,           # scroll curve: log(1+k*x)/log(1+k); 0 = linear
    "power_hold_seconds": 3.0,
    "power_tap_max_seconds": 1.0,
    "start_hold_seconds": 1.0,
    "osk_repeat_delay": 0.40,
    "osk_repeat_interval": 0.09,
    "vol_repeat_delay": 0.40,      # hold Vol (or F+Vol): repeat after this
    "vol_repeat_interval": 0.12,
}

# Desktop-mode bindings (overridable from the config file).
DEFAULT_BINDINGS = {
    "a": "click_left",
    "b": "click_right",
    "x": "osk_toggle",
    "y": "none",
    "l1": "key:KEY_ESC",
    "r1": "key:KEY_ENTER",
    "l2": "none",
    "r2": "key:KEY_BACKSPACE",
    "l3": "copy",
    "r3": "paste",
    "start": "mode_gamepad",
    "select": "none",
}

# Gamepad mode: by position, Xbox 360 (xpad) conventions.
# Physical bottom (label B) -> Xbox A, right (A) -> B, left (Y) -> X, top (X) -> Y.
PAD_BUTTONS = {
    "b": "BTN_A", "a": "BTN_B", "y": "BTN_X", "x": "BTN_Y",
    "l1": "BTN_TL", "r1": "BTN_TR", "select": "BTN_SELECT", "start": "BTN_START",
    "l3": "BTN_THUMBL", "r3": "BTN_THUMBR",
}
PAD_TRIGGERS = {"l2": "ABS_Z", "r2": "ABS_RZ"}
PAD_AXES = {"lx": "ABS_X", "ly": "ABS_Y", "rx": "ABS_RX", "ry": "ABS_RY"}


class Core:
    def __init__(self, settings=None, bindings=None):
        self.s = dict(DEFAULT_SETTINGS)
        self.s.update(settings or {})
        self.bind = dict(DEFAULT_BINDINGS)
        self.bind.update(bindings or {})
        self.mode = "desktop"
        self.osk_visible = False
        self.screen_off = False
        self.axes = {"lx": 0.0, "ly": 0.0, "rx": 0.0, "ry": 0.0}
        self.held = {}              # name -> press time
        self.swallowed = set()      # buttons whose press was consumed (e.g. screen wake)
        self.power_fired = False
        self.start_fired = False
        self.osk_pressed_button = None  # button that triggered the current OSK press
        self.osk_next_repeat = {}   # dpad dir -> next repeat time
        self.vol_repeat = {}        # vol_up/vol_down -> [cmd, next repeat time]
        self.last_tick = None
        self.acc = [0.0, 0.0, 0.0, 0.0]   # sub-unit accumulators: x, y, wheel v, wheel h

    # ---------------------------------------------------------------- inputs
    def set_osk_visible(self, visible):
        self.osk_visible = bool(visible)

    def set_screen_off(self, off):
        self.screen_off = bool(off)

    def axis(self, name, value, t):
        value = max(-1.0, min(1.0, float(value)))
        self.axes[name] = value
        if self.mode == "gamepad":
            return [("pad_abs", PAD_AXES[name], int(round(value * 32767)))]
        return []

    def button(self, name, pressed, t):
        if pressed:
            return self._press(name, t)
        return self._release(name, t)

    # -------------------------------------------------------------- presses
    def _press(self, name, t):
        self.held[name] = t
        out = []

        if self.screen_off and name != "power":
            # Any button wakes the screen; the press itself is not acted on.
            self.swallowed.add(name)
            return [("screen_wake",)]

        if name == "power":
            self.power_fired = False
            return out
        if name in ("vol_up", "vol_down"):
            direction = "up" if name == "vol_up" else "down"
            cmd = ("brightness_" if "f" in self.held else "volume_") + direction
            self.vol_repeat[name] = [cmd, t + self.s["vol_repeat_delay"]]
            return [("cmd", cmd)]
        if name == "f":
            return out  # modifier only; never forwarded

        if self.mode == "gamepad":
            if name == "start":
                self.start_fired = False
            return self._pad_button(name, True)

        # desktop mode
        if name in DPAD:
            if self.osk_visible:
                dx, dy = _dpad_vector(name)
                self.osk_next_repeat[name] = t + self.s["osk_repeat_delay"]
                return [("osk", "move", dx, dy)]
            return out  # pointer motion happens in tick()
        osk_key = next((btn for btn, act in self.bind.items() if act == "click_left"), "a")
        if name == osk_key and self.osk_visible:
            self.osk_pressed_button = name
            return [("osk", "press")]
        return self._binding(name, True)

    def _release(self, name, t):
        pressed_at = self.held.pop(name, None)
        if name in self.swallowed:
            self.swallowed.discard(name)
            return []
        if pressed_at is None:
            return []
        dur = t - pressed_at

        if name == "power":
            if self.power_fired:
                return []
            if self.screen_off:
                return [("screen_wake",)]
            if dur <= self.s["power_tap_max_seconds"]:
                return [("cmd", "power_menu")]
            return []  # held 1-3 s: cancelled
        if name in ("vol_up", "vol_down", "f"):
            self.vol_repeat.pop(name, None)
            return []

        if self.mode == "gamepad":
            if name == "start" and self.start_fired:
                return []  # release already sent when switching modes
            return self._pad_button(name, False)

        if name in DPAD:
            self.osk_next_repeat.pop(name, None)
            return []
        if self.osk_pressed_button and name == self.osk_pressed_button:
            self.osk_pressed_button = None
            return [("osk", "release")]
        return self._binding(name, False)

    # ------------------------------------------------------------------ tick
    def tick(self, t):
        out = []
        dt = 0.0 if self.last_tick is None else max(0.0, min(0.1, t - self.last_tick))
        self.last_tick = t

        # Power: hold to shut down.
        p = self.held.get("power")
        if p is not None and not self.power_fired and t - p >= self.s["power_hold_seconds"]:
            self.power_fired = True
            out.append(("shutdown",))

        # Vol / F+Vol: auto-repeat while held (both modes).
        for name, rep in self.vol_repeat.items():
            if name in self.held and t >= rep[1]:
                out.append(("cmd", rep[0]))
                rep[1] = t + self.s["vol_repeat_interval"]

        if self.mode == "gamepad":
            st = self.held.get("start")
            if st is not None and not self.start_fired and t - st >= self.s["start_hold_seconds"]:
                self.start_fired = True
                out.append(("pad_key", "BTN_START", 0))
                out.extend(self._enter_desktop())
            return out

        if self.screen_off or dt == 0.0:
            return out

        # Pointer: left stick (analog) + D-pad (digital, when the keyboard is hidden).
        vx, vy = self._stick_velocity(self.axes["lx"], self.axes["ly"], self.s["pointer_max_speed"],
                                      self._power_curve)
        if not self.osk_visible:
            dx, dy = 0, 0
            for d in DPAD:
                if d in self.held and d not in self.swallowed:
                    ddx, ddy = _dpad_vector(d)
                    dx += ddx
                    dy += ddy
            vx += dx * self.s["dpad_speed"]
            vy += dy * self.s["dpad_speed"]
        self.acc[0] += vx * dt
        self.acc[1] += vy * dt
        mx, my = int(self.acc[0]), int(self.acc[1])
        if mx or my:
            self.acc[0] -= mx
            self.acc[1] -= my
            out.append(("rel", mx, my))

        # Scroll: right stick, both directions. Stick up = scroll up.
        sx, sy = self._stick_velocity(self.axes["rx"], self.axes["ry"], self.s["scroll_speed"] * 120.0,
                                      self._log_curve)
        self.acc[2] += -sy * dt
        self.acc[3] += sx * dt
        wv, wh = int(self.acc[2]), int(self.acc[3])
        if wv or wh:
            self.acc[2] -= wv
            self.acc[3] -= wh
            out.append(("wheel", wv, wh))

        # On-screen keyboard: D-pad auto-repeat.
        if self.osk_visible:
            for d, nxt in list(self.osk_next_repeat.items()):
                if d in self.held and t >= nxt:
                    dx, dy = _dpad_vector(d)
                    out.append(("osk", "move", dx, dy))
                    self.osk_next_repeat[d] = t + self.s["osk_repeat_interval"]
        return out

    # --------------------------------------------------------------- helpers
    def _stick_velocity(self, x, y, max_speed, curve):
        r = math.hypot(x, y)
        dz = self.s["deadzone"]
        if r <= dz:
            return 0.0, 0.0
        mag = curve(min(1.0, (r - dz) / (1.0 - dz)))
        return x / r * mag * max_speed, y / r * mag * max_speed

    def _power_curve(self, m):
        """Pointer: slow near centre, fast at the edge."""
        return m ** self.s["pointer_curve"]

    def _log_curve(self, m):
        """Scroll: rises quickly with a small push, levels off near full tilt."""
        k = self.s["scroll_log_k"]
        return m if k <= 0 else math.log1p(k * m) / math.log1p(k)

    def _binding_of(self, name):
        return self.bind.get(name, "none")

    def _binding(self, name, pressed):
        action = self._binding_of(name)
        if action == "none":
            return []
        if action.startswith("click_"):
            return [("mouse", action[len("click_"):], pressed)]
        if action.startswith("key:"):
            return [("key", action[4:], pressed)]
        if not pressed:
            return []  # the rest act on press only
        if action in ("copy", "paste"):
            return [("clipboard", action)]
        if action == "osk_toggle":
            return [("osk", "toggle")]
        if action == "mode_gamepad":
            return self._enter_gamepad()
        if action == "power_menu":
            return [("cmd", "power_menu")]
        return []

    def _release_all_desktop(self):
        out = []
        for name in list(self.held):
            if name in BUTTONS and name not in ("f",):
                action = self._binding_of(name)
                if action.startswith("click_"):
                    out.append(("mouse", action[len("click_"):], False))
                elif action.startswith("key:"):
                    out.append(("key", action[4:], False))
        return out

    def _enter_gamepad(self):
        out = self._release_all_desktop()
        self.mode = "gamepad"
        self.start_fired = False
        # The Start press that triggered the switch must not reach the pad.
        self.swallowed.add("start")
        self.acc = [0.0, 0.0, 0.0, 0.0]
        out.append(("mode", "gamepad"))
        for name, v in self.axes.items():
            out.append(("pad_abs", PAD_AXES[name], int(round(v * 32767))))
        return out

    def _enter_desktop(self):
        self.mode = "desktop"
        self.acc = [0.0, 0.0, 0.0, 0.0]
        self.osk_next_repeat.clear()
        return [("mode", "desktop")]

    def _pad_button(self, name, pressed):
        if name in PAD_BUTTONS:
            return [("pad_key", PAD_BUTTONS[name], 1 if pressed else 0)]
        if name in PAD_TRIGGERS:
            return [("pad_abs", PAD_TRIGGERS[name], 255 if pressed else 0)]
        if name in DPAD:
            hx = (1 if "right" in self.held else 0) - (1 if "left" in self.held else 0)
            hy = (1 if "down" in self.held else 0) - (1 if "up" in self.held else 0)
            return [("pad_abs", "ABS_HAT0X", hx), ("pad_abs", "ABS_HAT0Y", hy)]
        return []


def _dpad_vector(name):
    return {"up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0)}[name]
