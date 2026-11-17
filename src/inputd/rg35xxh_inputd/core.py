"""Input logic for the RG35XX H (hardware independent, unit-tested).

The daemon feeds normalized events in and executes the returned actions:

  core.button(name, pressed, t)   name: a b x y l1 r1 l2 r2 l3 r3 select start f
                                        up down left right  vol_up vol_down  power
  core.axis(name, value, t)       name: lx ly rx ry, value -1.0 .. 1.0 (y: down = +)
  core.tick(t)                    call every ~10 ms; returns movement/hold actions

Every call returns a list of actions (tuples):
  ("rel", dx, dy)                 move pointer (integer pixels)
  ("wheel", v, h)                 hi-res scroll units (120 = one notch); v>0 = up, h>0 = right
  ("mouse", "left"|"right"|"middle"|"back"|"forward", pressed)
  ("key", "KEY_ENTER", pressed)   (a combo: one per key, pressed in order, released in reverse)
  ("launch", "<desktop id>")      start an app (on press)
  ("clipboard", "copy"|"paste")   daemon picks Ctrl(+Shift)+C/V depending on focused app
  ("osk", "toggle") / ("osk", "move", dx, dy) / ("osk", "press") / ("osk", "release")
  / ("osk", "repeat") (A held on a key) / ("osk", "shift") (L2 while the keyboard is open)
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
    "dpad_speed_ratio": 0.5,       # D-pad pointer speed as a fraction of pointer_max_speed
    "scroll_speed": 8.4,          # notches/s at full tilt
    "scroll_log_k": 9.0,           # scroll curve: log(1+k*x)/log(1+k); 0 = linear
    "power_hold_seconds": 3.0,
    "power_tap_max_seconds": 1.0,
    "start_hold_seconds": 1.0,
    "haptic_strength": 1.0,        # mode-change vibration: 0 = off, 1 = as designed
    "display_speed_scale": 1.0,    # pointer speed on a bigger screen: 1 = scaled by its size vs. the
                                   # handheld's (1080p: ~2.75x), 0 = same px/s everywhere
    "osk_repeat_delay": 0.40,
    "osk_repeat_interval": 0.09,
    "osk_key_repeat_delay": 0.50,  # keyboard open, A held on a key: type it again after this
    "osk_key_repeat_interval": 0.06,
    "vol_repeat_delay": 0.40,      # hold Vol (or F+Vol): repeat after this
    "vol_repeat_interval": 0.12,
    "natural_scroll": False,       # True: content follows the stick (scroll directions reversed)
    "swap_sticks": False,          # True: right stick = pointer, left stick = scroll (desktop mode)
    "pad_layout": "position",      # gamepad mode: "position" (bottom = Xbox A) or "label" (A = A)
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
    # Advanced (Controls app, with a warning there): what used to be fixed. Desktop mode only; in
    # gamepad and External Controller modes these keep their usual jobs. Holding Power to shut
    # down is never remappable (the only way to switch off a frozen session from the handheld).
    "up": "pointer", "down": "pointer", "left": "pointer", "right": "pointer",
    "vol_up": "volume_up", "vol_down": "volume_down",
    "f": "none",                   # a tap of F; F + Vol stays brightness
    "power": "power_menu",         # a tap of Power
}
BINDABLE = BUTTONS + DPAD + ("vol_up", "vol_down", "power")
LEVEL_CMDS = ("volume_up", "volume_down", "brightness_up", "brightness_down")   # repeat while held

# Gamepad mode: by position, Xbox 360 (xpad) conventions.
# Physical bottom (label B) -> Xbox A, right (A) -> B, left (Y) -> X, top (X) -> Y.
PAD_BUTTONS = {
    "b": "BTN_A", "a": "BTN_B", "y": "BTN_X", "x": "BTN_Y",
    "l1": "BTN_TL", "r1": "BTN_TR", "select": "BTN_SELECT", "start": "BTN_START",
    "l3": "BTN_THUMBL", "r3": "BTN_THUMBR",
}
# By label (pad_layout = label, local gamepad mode only): the handheld's A sends Xbox A, and so on.
# The External Controller modes always use PAD_BUTTONS: their services translate by position.
PAD_BUTTONS_LABEL = dict(PAD_BUTTONS, a="BTN_A", b="BTN_B", x="BTN_X", y="BTN_Y")
PAD_TRIGGERS = {"l2": "ABS_Z", "r2": "ABS_RZ"}
PAD_AXES = {"lx": "ABS_X", "ly": "ABS_Y", "rx": "ABS_RX", "ry": "ABS_RY"}
# BT Controller mode exits with this combo instead of holding Start (same as Moonlight's quit
# combo), so a long Start press reaches the other device.
EXIT_COMBO = ("select", "start", "l1", "r1")
# Switch Controller mode only (request_gamepad(f_buttons=True)): F gives the buttons the handheld
# lacks. F tap = Home, F held = Home held (quick settings), F + Select = Capture. F + Vol stays
# brightness. Not in the Xbox modes: there Home would be Guide, which opens the Game Bar on Windows.
HOME_KEY, CAPTURE_KEY = "BTN_MODE", "KEY_RECORD"
HOME_HOLD_SECONDS = 0.6     # F held this long without Vol / Select: Home pressed until F is released
HOME_TAP_SECONDS = 0.1      # F tap: Home pressed this long (one report would be too short to see)


class Core:
    def __init__(self, settings=None, bindings=None):
        self._configure(settings, bindings)
        self.mode = "desktop"
        self.combo_exit = False     # gamepad mapping left with EXIT_COMBO (BT Controller mode)
        self.f_buttons = False      # F gives Home / Capture (Switch Controller mode)
        self.osk_visible = False
        self.screen_off = False
        self.axes = {"lx": 0.0, "ly": 0.0, "rx": 0.0, "ry": 0.0}
        self.pointer_scale = 1.0    # speed factor of the screen the pointer is on (set by the daemon)
        self.held = {}              # name -> press time
        self.swallowed = set()      # buttons whose press was consumed (e.g. screen wake)
        self.power_fired = False
        self.start_fired = False
        self.osk_pressed_button = None  # button that triggered the current OSK press
        self.osk_next_repeat = {}   # dpad dir -> next repeat time
        self.osk_key_next = None    # next "repeat" while the OSK key (A) is held
        self.osk_shift_button = None  # L2 pressed as Shift on the keyboard (its binding is skipped)
        self.vol_repeat = {}        # vol_up/vol_down -> [cmd, next repeat time]
        self.level_bound = set()    # Vol held under a binding other than volume / brightness
        self.dpad_bound = set()     # D-pad directions held under a binding other than the pointer
        self.combo_wait = set()     # first buttons of combinations, held, own action not run yet
        self.combo_used = set()     # ... that started a combination (no own action on release)
        self.combo_active = {}      # second button -> the combination action it is holding
        self.f_used = False         # F was used as a modifier (Vol / Select) since it went down
        self.home_down = False      # Home held on the other device (F held, external modes)
        self.home_release_at = None  # F tap: when to release Home
        self.capture_down = False   # Select is held as Capture (F + Select, external modes)
        self.last_tick = None
        self.acc = [0.0, 0.0, 0.0, 0.0]   # sub-unit accumulators: x, y, wheel v, wheel h

    def _configure(self, settings, bindings):
        self.s = dict(DEFAULT_SETTINGS)
        self.s.update(settings or {})
        if "dpad_speed" in self.s and "dpad_speed_ratio" not in (settings or {}):   # older configs: px/s
            self.s["dpad_speed_ratio"] = self.s["dpad_speed"] / max(1.0, self.s["pointer_max_speed"])
        self.bind = dict(DEFAULT_BINDINGS)
        self.bind.update(bindings or {})
        # combinations: bindings named "first+second"; first buttons wait for their release
        self.combo_first = {k.split("+")[0] for k in self.bind if "+" in k}

    def reconfigure(self, settings=None, bindings=None):
        """New settings and bindings while running (the Controls app, a changed config file).
        Whatever the old bindings hold is released first, as on a mode switch, and buttons still
        down are swallowed: their release must not act under the new binding. Only data changes
        here; the daemon touches no device for it."""
        out = []
        if self.mode == "desktop":
            # Only buttons whose binding changes are let go: a held button must survive an unrelated
            # change (dragging the Controls app's vibration slider holds A while it saves).
            new = dict(DEFAULT_BINDINGS)
            new.update(bindings or {})
            changed = {n for n in self.held if n in BINDABLE and n not in ("f", "power")
                       and self.bind.get(n) != new.get(n)}
            in_combo = set(self.combo_active) | self.combo_wait
            out = self._release_all_desktop(changed)
            self.dpad_bound -= changed
            self.level_bound -= changed
            for n in changed:
                self.vol_repeat.pop(n, None)   # a held Vol must not go on repeating its old action
            if self.osk_pressed_button in changed:
                out.append(("osk", "release"))
                self.osk_pressed_button = None
                self.osk_key_next = None
            if self.osk_shift_button in changed:
                self.osk_shift_button = None
            self.swallowed |= changed
            if ({k: v for k, v in self.bind.items() if "+" in k} != {k: v for k, v in new.items() if "+" in k}
                    or changed & in_combo):
                # the combinations change, or a button holding one gets a new binding: let go of
                # them now (a held Ctrl from select+a must not outlive the binding that made it)
                out += self._release_combos()
        elif (settings or {}).get("pad_layout", "position") != self.s["pad_layout"]:
            # Gamepad mode, layout switched: release the face buttons down under the old layout.
            for n in ("a", "b", "x", "y"):
                if n in self.held and n not in self.swallowed:
                    out.extend(self._pad_button(n, False))
                    self.swallowed.add(n)
        self._configure(settings, bindings)
        return out

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
            if "f" in self.held:
                self.f_used = True
                cmd = "brightness_" + direction             # F + Vol: always brightness
            else:
                cmd = self.bind.get(name, "volume_" + direction) if self.mode == "desktop" else "volume_" + direction
                if cmd not in LEVEL_CMDS:                   # remapped to something else
                    self.level_bound.add(name)
                    return self._binding(name, True)
            self.vol_repeat[name] = [cmd, t + self.s["vol_repeat_delay"]]
            return [("cmd", cmd)]
        if name == "f":
            self.f_used = False
            return out  # modifier, never forwarded; external modes: Home on tap / hold (_release, tick)

        if self.mode == "gamepad":
            if name == "select" and self._external() and "f" in self.held:
                self.f_used = True
                self.capture_down = True
                return [("pad_key", CAPTURE_KEY, 1)]
            if name == "start":
                self.start_fired = False
            out = self._pad_button(name, True)
            if self.combo_exit and all(b in self.held for b in EXIT_COMBO):
                for b in EXIT_COMBO:                       # release them on the other device
                    out.extend(self._pad_button(b, False))
                self.swallowed |= set(self.held)
                out.extend(self._enter_desktop())
            return out

        # desktop mode
        if not self.osk_visible:
            # Button combinations ("l1+a" bindings), hold-modifier style: hold the first button, press
            # the second, and the combination's action runs instead of the second's. The first
            # button's own action then runs only when it is tapped alone (on release).
            for first in [f for f in self.combo_first if f in self.held and f != name]:
                act = self.bind.get(f"{first}+{name}")
                if act:
                    self.combo_used.add(first)
                    self.combo_active[name] = act
                    return self._action(act, True)
            if name in self.combo_first and name != "f":
                self.combo_wait.add(name)               # its own action waits for the release
                return out
        if name in DPAD:
            if self.osk_visible:
                dx, dy = _dpad_vector(name)
                self.osk_next_repeat[name] = t + self.s["osk_repeat_delay"]
                return [("osk", "move", dx, dy)]
            if self.bind.get(name, "pointer") != "pointer":
                self.dpad_bound.add(name)
                return self._binding(name, True)
            return out  # pointer motion happens in tick()
        osk_key = next((btn for btn, act in self.bind.items() if act == "click_left"), "a")
        if name == osk_key and self.osk_visible:
            self.osk_pressed_button = name
            self.osk_key_next = t + self.s["osk_key_repeat_delay"]
            return [("osk", "press")]
        if name == "l2" and self.osk_visible:
            self.osk_shift_button = name
            return [("osk", "shift")]
        return self._binding(name, True)

    def _release(self, name, t):
        pressed_at = self.held.pop(name, None)
        self.vol_repeat.pop(name, None)       # also for a swallowed release (remapped while held)
        if name == "select" and self.capture_down:
            self.capture_down = False
            return [("pad_key", CAPTURE_KEY, 0)]
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
                return self._tap("power", "power_menu")
            return []  # held 1-3 s: cancelled
        if name in ("vol_up", "vol_down", "f"):
            self.vol_repeat.pop(name, None)
            if name == "f" and self._external():
                return self._home_on_f_release(t, dur)
            if name in self.level_bound:
                self.level_bound.discard(name)
                return self._binding(name, False)
            if name == "f" and "f" in self.combo_used:
                self.combo_used.discard("f")
                return []
            if name == "f" and not self.f_used and dur <= self.s["power_tap_max_seconds"]:
                return self._tap("f", "none")             # F tapped alone (not as F + Vol)
            return []

        if self.mode == "gamepad":
            if name == "start" and self.start_fired:
                return []  # release already sent when switching modes
            return self._pad_button(name, False)

        if name in self.combo_active:                     # the second button of a combination
            return self._action(self.combo_active.pop(name), False)
        if name in self.combo_wait:                       # a first button: its own action if alone
            self.combo_wait.discard(name)
            if name in self.combo_used:
                self.combo_used.discard(name)
                return []
            return self._binding(name, True) + self._binding(name, False)
        if name in DPAD:
            self.osk_next_repeat.pop(name, None)
            if name in self.dpad_bound:
                self.dpad_bound.discard(name)
                return self._binding(name, False)
            return []
        if self.osk_pressed_button and name == self.osk_pressed_button:
            self.osk_pressed_button = None
            self.osk_key_next = None
            return [("osk", "release")]
        if self.osk_shift_button and name == self.osk_shift_button:
            self.osk_shift_button = None
            return []
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
            if self._external():
                f = self.held.get("f")
                if (f is not None and not self.f_used and not self.home_down and "f" not in self.swallowed
                        and t - f >= HOME_HOLD_SECONDS):
                    self.home_down = True
                    self.home_release_at = None
                    out.append(("pad_key", HOME_KEY, 1))
                if self.home_release_at is not None and t >= self.home_release_at:
                    self.home_release_at = None
                    out.append(("pad_key", HOME_KEY, 0))
            st = self.held.get("start")
            if (st is not None and not self.combo_exit and not self.start_fired
                    and t - st >= self.s["start_hold_seconds"]):
                self.start_fired = True
                out.append(("pad_key", "BTN_START", 0))
                out.extend(self._enter_desktop())
            return out

        if self.screen_off or dt == 0.0:
            return out

        # Pointer: left stick (analog) + D-pad (digital, when the keyboard is hidden); swap_sticks
        # trades the sticks' roles (left-handed use).
        px, py, sx_, sy_ = ("rx", "ry", "lx", "ly") if self.s["swap_sticks"] else ("lx", "ly", "rx", "ry")
        vx, vy = self._stick_velocity(self.axes[px], self.axes[py], self.s["pointer_max_speed"],
                                      self._power_curve)
        if not self.osk_visible:
            dx, dy = 0, 0
            for d in DPAD:
                if (d in self.held and d not in self.swallowed and d not in self.dpad_bound
                        and d not in self.combo_active):     # the second button of a combination
                    ddx, ddy = _dpad_vector(d)
                    dx += ddx
                    dy += ddy
            dpad = self.s["dpad_speed_ratio"] * self.s["pointer_max_speed"]
            vx += dx * dpad
            vy += dy * dpad
        self.acc[0] += vx * self.pointer_scale * dt
        self.acc[1] += vy * self.pointer_scale * dt
        mx, my = int(self.acc[0]), int(self.acc[1])
        if mx or my:
            self.acc[0] -= mx
            self.acc[1] -= my
            out.append(("rel", mx, my))

        # Scroll: right stick, both directions. Stick up = scroll up (natural_scroll: down).
        sx, sy = self._stick_velocity(self.axes[sx_], self.axes[sy_], self.s["scroll_speed"] * 120.0,
                                      self._log_curve)
        if self.s["natural_scroll"]:
            sx, sy = -sx, -sy
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
            # A held on a key: type it again, like a real keyboard's key repeat.
            if self.osk_pressed_button in self.held and self.osk_key_next is not None \
                    and t >= self.osk_key_next:
                out.append(("osk", "repeat"))
                self.osk_key_next = t + self.s["osk_key_repeat_interval"]
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
        return self._action(self._binding_of(name), pressed)

    def _action(self, action, pressed):
        if action in ("none", "pointer"):
            return []
        if action.startswith("click_"):
            return [("mouse", action[len("click_"):], pressed)]
        if action.startswith("key:"):
            return [("key", action[4:], pressed)]
        if action.startswith("combo:"):
            keys = action[6:].split("+")
            return [("key", k, True) for k in keys] if pressed else [("key", k, False) for k in reversed(keys)]
        if not pressed:
            return []  # the rest act on press only
        if action.startswith("launch:"):
            return [("launch", action[7:])]
        if action.startswith("macro:"):
            return [("macro", action[6:])]          # the daemon plays it (or stops it if running)
        if action == "macro_record":
            return [("macro_record",)]              # recording: start / pause (Controls app arms it)
        if action in ("copy", "paste"):
            return [("clipboard", action)]
        if action == "osk_toggle":
            return [("osk", "toggle")]
        if action == "mode_gamepad":
            return self._enter_gamepad()
        if action == "power_menu":
            return [("cmd", "power_menu")]
        if action in LEVEL_CMDS:
            return [("cmd", action)]
        return []

    def _release_combos(self):
        """Let go of running combinations and forget waiting first buttons (mode switch, reload)."""
        out = []
        for act in self.combo_active.values():
            out += self._action(act, False)
        self.swallowed |= set(self.combo_active) | self.combo_wait
        self.combo_active.clear()
        self.combo_wait.clear()
        self.combo_used.clear()
        return out

    def _tap(self, name, default):
        """A button acted on only when released quickly (Power, F): its action pressed and let go."""
        if self.mode != "desktop":
            return [("cmd", default)] if default != "none" else []
        action = self.bind.get(name, default)
        if action == "power_menu" or action in LEVEL_CMDS:
            return [("cmd", action)]
        return self._binding(name, True) + self._binding(name, False)

    def _release_all_desktop(self, names=None):
        """Release what held buttons' own bindings hold down. Buttons in a combination (a second
        button holding the combination's action, a first button waiting for its release) never
        pressed their own binding: _release_combos() lets go of those."""
        out = []
        skip = set(self.combo_active) | self.combo_wait
        for name in list(self.held):
            if name in skip:
                continue
            if name in BINDABLE and name not in ("f", "power") and (names is None or name in names):

                action = self._binding_of(name)
                if action.startswith("click_"):
                    out.append(("mouse", action[len("click_"):], False))
                elif action.startswith("key:"):
                    out.append(("key", action[4:], False))
                elif action.startswith("combo:"):
                    out.extend(("key", k, False) for k in reversed(action[6:].split("+")))
        return out

    def _enter_gamepad(self):
        out = self._release_all_desktop()
        out += self._release_combos()
        self.dpad_bound.clear()            # released just now; their release comes in gamepad mode
        self.level_bound.clear()
        self.mode = "gamepad"
        self.start_fired = False
        # The Start press that triggered the switch must not reach the pad.
        self.swallowed.add("start")
        self.acc = [0.0, 0.0, 0.0, 0.0]
        out.append(("mode", "gamepad"))
        for name, v in self.axes.items():
            out.append(("pad_abs", PAD_AXES[name], int(round(v * 32767))))
        return out

    def request_gamepad(self, combo_exit=False, f_buttons=False):
        """Switch to gamepad mapping on request (BT Controller app, SIGUSR2 to the daemon).
        combo_exit: leave with EXIT_COMBO instead of holding Start. f_buttons: F gives Home /
        Capture (Switch Controller mode)."""
        self.combo_exit = combo_exit
        self.f_buttons = f_buttons and combo_exit
        self._reset_external_buttons()
        if self.mode == "gamepad":
            return []
        out = self._enter_gamepad()
        if "start" not in self.held:      # no Start press to swallow: let the next one through
            self.swallowed.discard("start")
        return out

    def request_desktop(self):
        """Leave gamepad mode on request (the BT Controller link ended)."""
        if self.mode != "gamepad":
            return []
        self.swallowed |= set(self.held)  # buttons still down must not act in desktop mode
        return self._enter_desktop()

    def _external(self):
        """Switch Controller mode: gamepad mapping left with EXIT_COMBO, F gives Home / Capture."""
        return self.mode == "gamepad" and self.combo_exit and self.f_buttons

    def _home_on_f_release(self, t, dur):
        if self.home_down:                         # F was held: release Home
            self.home_down = False
            return [("pad_key", HOME_KEY, 0)]
        if self.f_used or dur >= HOME_HOLD_SECONDS:
            return []
        self.home_release_at = t + HOME_TAP_SECONDS    # tap: press now, release from tick()
        return [("pad_key", HOME_KEY, 1)]

    def _reset_external_buttons(self):
        # The service clears its state when the link ends; only ours is left to forget.
        self.home_down = self.capture_down = False
        self.home_release_at = None

    def _enter_desktop(self):
        self.mode = "desktop"
        self.combo_exit = self.f_buttons = False
        self._reset_external_buttons()
        self.acc = [0.0, 0.0, 0.0, 0.0]
        self.osk_next_repeat.clear()
        self.osk_key_next = None
        return [("mode", "desktop")]

    def _pad_button(self, name, pressed):
        table = PAD_BUTTONS_LABEL if self.s["pad_layout"] == "label" and not self.combo_exit else PAD_BUTTONS
        if name in table:
            return [("pad_key", table[name], 1 if pressed else 0)]
        if name in PAD_TRIGGERS:
            return [("pad_abs", PAD_TRIGGERS[name], 255 if pressed else 0)]
        if name in DPAD:
            hx = (1 if "right" in self.held else 0) - (1 if "left" in self.held else 0)
            hy = (1 if "down" in self.held else 0) - (1 if "up" in self.held else 0)
            return [("pad_abs", "ABS_HAT0X", hx), ("pad_abs", "ABS_HAT0Y", hy)]
        return []


def _dpad_vector(name):
    return {"up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0)}[name]


class PointerLayout:
    """Where the pointer probably is, for per-screen pointer speed.

    The daemon only sends relative motion, and the compositor does not tell clients where the
    cursor is, so this follows the daemon's own motion over the output layout (written by
    rg35xxh-display: [{"x","y","w","h","scale"}, ...]) and clamps it the way wlroots does: a move
    that would leave every output ends at the closest point of the layout. Motion from other mice
    is not seen; the estimate then only picks the wrong speed until it reaches an edge."""

    def __init__(self, rects=None):
        self.rects = []
        self.x = self.y = 0.0
        self.placed = False
        self.set_rects(rects or [])

    def set_rects(self, rects):
        self.rects = [dict(r) for r in rects if r.get("w", 0) > 0 and r.get("h", 0) > 0]
        if not self.rects:
            return
        if not self.placed:                  # first layout: start in the middle of the first output
            r = self.rects[0]
            self.x, self.y = r["x"] + r["w"] / 2, r["y"] + r["h"] / 2
            self.placed = True
        elif not self._inside(self.x, self.y):
            self.x, self.y = self._closest(self.x, self.y)

    def _inside(self, x, y):
        return any(r["x"] <= x < r["x"] + r["w"] and r["y"] <= y < r["y"] + r["h"] for r in self.rects)

    def _closest(self, x, y):
        best, bd = (x, y), None
        for r in self.rects:
            cx = min(max(x, r["x"]), r["x"] + r["w"] - 1)
            cy = min(max(y, r["y"]), r["y"] + r["h"] - 1)
            d = (cx - x) ** 2 + (cy - y) ** 2
            if bd is None or d < bd:
                best, bd = (cx, cy), d
        return best

    def move(self, dx, dy):
        if not self.rects:
            return
        nx, ny = self.x + dx, self.y + dy
        self.x, self.y = (nx, ny) if self._inside(nx, ny) else self._closest(nx, ny)

    def scale(self, strength=1.0):
        for r in self.rects:
            if r["x"] <= self.x < r["x"] + r["w"] and r["y"] <= self.y < r["y"] + r["h"]:
                return 1.0 + (float(r.get("scale", 1.0)) - 1.0) * strength
        return 1.0
