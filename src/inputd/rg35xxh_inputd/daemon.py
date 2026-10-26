"""rg35xxh-inputd: turns the RG35XX H controls into mouse/keyboard (desktop mode) or an
Xbox-style controller (gamepad mode). Runs inside the labwc session as the user.

Devices (grabbed exclusively while running):
  "H700 Gamepad"              buttons + sticks (+ rumble motor)
  device with KEY_VOLUMEUP    volume keys (gpio-keys)
  device with KEY_POWER       power button (AXP717)
Virtual devices (uinput): mouse, keyboard, and in gamepad mode an Xbox 360 pad.
External controller modes (BT Controller: rg35xxh-btpad, wired: rg35xxh-usbpad) use the gamepad
mapping too, but send the pad events over a Unix socket to that service instead of creating the
local pad, so apps on the handheld see nothing. Only one of the two services runs at a time.
"""
import json
import logging
import math
import os
import shutil
import signal
import socket
import struct
import subprocess
import sys
import time

import evdev
from evdev import ecodes as E
from evdev import ff
from gi.repository import GLib

from . import config
from .core import PAD_AXES, Core, PointerLayout

log = logging.getLogger("rg35xxh-inputd")

GAMEPAD_NAME = "H700 Gamepad"
BUILTIN = {GAMEPAD_NAME: "gamepad", "gpio-keys-volume": "volume", "axp20x-pek": "power"}
# Physical codes (rocknix-singleadc-joypad, see docs/hardware.md) -> button names.
HW_BUTTONS = {
    0x131: "a", 0x130: "b", 0x134: "x", 0x133: "y",   # all four verified on device (debug log)
    0x136: "l1", 0x137: "r1", 0x138: "l2", 0x139: "r2",
    0x13d: "l3", 0x13e: "r3", 0x13a: "select", 0x13b: "start", 0x13c: "f",
    0x220: "up", 0x221: "down", 0x222: "left", 0x223: "right",
    E.KEY_VOLUMEUP: "vol_up", E.KEY_VOLUMEDOWN: "vol_down", E.KEY_POWER: "power",
}
HW_AXES = {E.ABS_X: "lx", E.ABS_Y: "ly", E.ABS_RX: "rx", E.ABS_RY: "ry"}
TERMINALS = ("foot", "footclient", "org.codeberg.dnkl.foot", "xterm", "uxterm", "kitty", "alacritty")
STATUS_LED = "/sys/class/leds/red:status"
EXT_SOCKET = "/run/rg35xxh-extpad.sock"        # created by rg35xxh-btpad / -usbpad (root, group input)
# Messages from the service: b"hello bt" | b"hello usb" first, later b"rumble <big> <small>" (0-255).
EXT_MODES = {   # transport: (flag file, notification title, notification text, taskbar icon)
    "bt": ("rg35xxh-bt-mode", "BT Controller mode",
           "Controls go to the paired PC/phone. Select + Start + L1 + R1 to stop.", "bt"),
    "usb": ("rg35xxh-wired-mode", "Wired Controller mode",
            "Controls go to the PC over the USB cable. Select + Start + L1 + R1 to stop.", "wired"),
}
BT_EVENT = struct.Struct("<HHi")               # evdev type, code, value
# Mode-change feedback: the taskbar icon shakes and the motor wobbles with it, both driven from
# here on one clock and one damped-spring model, x(t) = A e^(-DECAY t) sin(2 pi FREQ t):
#  - icon: the OLD mode's icon is shown at each swing peak (every half period = STEP_MS, sides
#    alternating; offsets rounded to whole pixels, e.g. 2 -2 1 -1 1 -1), then the new icon;
#  - motor: one pulse per swing, strength following the spring's decaying envelope.
# The motor is an ERM on one PWM line (strength = duty cycle), slow to spin up and without
# braking, so the pulses blur into a decaying wobble. Waybar redraws ~HAPTIC_LAG_MS after a
# signal (it re-runs rg35xxh-inputmode), so the pulses are delayed by that much to line up.
SPRING_FREQ, SPRING_DECAY, SPRING_AMP_PX = 8.33, 3.85, 2.6    # Hz, 1/s, px
SPRING_SWINGS, SPRING_STEP_MS = 6, 60                         # 60 ms = half a period
SPRING_PULSE_MS, SPRING_FLOOR = 40, 0.4                       # pulse length; weakest strength
HAPTIC_LAG_MS = 70


def _spring(t):
    return math.exp(-SPRING_DECAY * t) * math.sin(2 * math.pi * SPRING_FREQ * t)


_PEAKS = [(k + 0.5) * SPRING_STEP_MS / 1000 for k in range(SPRING_SWINGS)]
ICON_FRAMES = [max(-2, min(2, round(SPRING_AMP_PX * _spring(t)))) or (1 if _spring(t) > 0 else -1)
               for t in _PEAKS]                               # px; frames exist for -2..2
SPRING_PULSES = [round(SPRING_FLOOR + (1 - SPRING_FLOOR) * math.exp(-SPRING_DECAY * t), 2) for t in _PEAKS]
INPUTMODE_FRAME = "rg35xxh-inputmode-frame"
# Hiding the pointer outside desktop mode: labwc has no "hide cursor" action, but it hides the
# pointer after touch input until the next real pointer motion. So on entering gamepad / BT
# Controller mode a short-lived virtual touchscreen taps once at the top-left corner, onto our own
# 2x2 px transparent overlay window shown there just for that moment, so the tap reaches nothing
# else (an earlier version tapped the taskbar border and opened tray icons). The pointer is warped
# there and hidden; it shows again as soon as the stick moves it in desktop mode.
# Motor safety: changing the vibration many times a second (re-uploading the effect) locked up
# the whole system twice (kernel side: ROCKNIX joypad driver, ff-memless + PWM work). Games and
# the PC can ask that fast (SDL re-sends rumble every frame; test pages stream it), so every
# vibration coming from outside (games in gamepad mode, the PC in wired mode) goes through one
# gate: at most one hardware update per MOTOR_INTERVAL, always with the latest request, and
# strengths rounded to MOTOR_LEVELS steps. Handtop's own short haptics are not affected.
# Never endless effects either: an effect with replay length 0 ("until stopped") locked the system
# up even at a few updates a second (all three freezes had one; our fixed-length haptics never
# did). So every effect has a length, and long vibrations are re-triggered (MOTOR_REFRESH) while
# wanted. Wired mode pre-uploads one MOTOR_EFFECT_MS effect per level and only plays/stops them.
MOTOR_INTERVAL = 0.1           # s
MOTOR_LEVELS = 8
MOTOR_EFFECT_MS = 500          # PC vibration: per-level effect length
MOTOR_GAME_MAX_MS = 1000       # games: length used for an endless (0) effect
MOTOR_REFRESH = 0.4            # s: re-trigger interval while a long vibration is wanted
TOUCH_W, TOUCH_H = 640, 480
TOUCH_TAP = (0, 0)                   # "<mode> <dx>" while shaking
WAYBAR_SIGNAL = 8                              # image#inputmode in the Waybar config


def runtime_flag(name):
    return os.path.join(os.environ.get("XDG_RUNTIME_DIR", "/tmp"), name)


def set_flag(name, on):
    """Runtime flag files, read by rg35xxh-autosleep and the Waybar input-mode indicator."""
    if on:
        open(runtime_flag(name), "w").close()
    else:
        try:
            os.unlink(runtime_flag(name))
        except FileNotFoundError:
            pass


def _comm(pid):
    try:
        with open(f"/proc/{pid}/comm") as f:
            return f.read().strip()
    except OSError:
        return None


def _proc_age(pid):
    """Seconds since process pid started (0 if unknown)."""
    try:
        with open(f"/proc/{pid}/stat") as f:
            start = int(f.read().rsplit(")", 1)[1].split()[19]) / os.sysconf("SC_CLK_TCK")
        with open("/proc/uptime") as f:
            return float(f.read().split()[0]) - start
    except (OSError, ValueError, IndexError):
        return 0


def spawn(*argv):
    try:
        subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, start_new_session=True)
    except OSError as e:
        log.warning("cannot run %s: %s", argv[0], e)


class Daemon:
    def __init__(self):
        self._loop = None
        settings, bindings, self.hw, self.config_path = config.load()
        self.core = Core(settings, bindings)
        self.layout = PointerLayout()   # per-screen pointer speed (rg35xxh-display writes the layout)
        self.layout_mtime = None
        self.devices = []          # grabbed physical devices
        self.gamepad = None
        self.absinfo = {}
        self.pad = None            # virtual Xbox pad (gamepad mode only)
        self.pad_ff = {}           # virtual effect id -> physical effect id
        self.bt = None             # socket to rg35xxh-btpad / -usbpad (external controller modes)
        self.ext = "bt"             # its transport, from the service's hello: "bt" | "usb"
        self.ext_rumble_id = None   # effect id for vibration requested by the PC
        self.motor_timer = None     # motor gate (MOTOR_INTERVAL): pending updates, last update time
        self.motor_last = 0.0
        self.motor_pending_upload = {}
        self.motor_pending_play = {}
        self.motor_ext_want = self.motor_ext_applied = 0   # level 0..MOTOR_LEVELS
        self.motor_ext_ids = {}     # level -> effect id (wired mode, uploaded on first use)
        self.motor_game_endless = set()   # game effects that asked for endless length
        self.motor_game_active = set()    # ... currently playing (re-triggered)
        self.motor_refresh_timer = None
        self.bt_watch = None
        self.icon_mode = "desktop"  # mode whose icon the taskbar shows (lags during the shake)
        self.touch = None           # short-lived virtual touchscreen (pointer hiding)
        self.anim = None
        self.waybar_pid = None
        self.haptic_id = None
        self.step_ids = {}
        self.axis_offset = {}      # software centre correction per axis (set by re-centre)
        self.watches = {}          # fd -> GLib watch id
        self.ui = None              # display side (on-screen keyboard, touch target): own process, ui.py
        self.ui_watch = None
        self.ui_buf = b""
        self.ui_retry = None        # respawn timer after the UI process ended
        self.ui_backoff = 2         # s, doubled per failed start (no display after a log-out)
        self.osk_visible = False
        self.ticks = 0
        for flag in ("rg35xxh-gamepad-mode", "rg35xxh-bt-mode", "rg35xxh-wired-mode", INPUTMODE_FRAME):
            set_flag(flag, False)
        self._open_devices()
        self._create_virtual_devices()
        self._ui_start()

    # ------------------------------------------------------------ devices
    def _open_devices(self, wait=15.0):
        deadline = time.monotonic() + wait
        found = {}
        while time.monotonic() < deadline:
            for path in evdev.list_devices():
                try:
                    d = evdev.InputDevice(path)
                except OSError:
                    continue
                # Match the built-in devices by name: USB/BT keyboards also report
                # KEY_VOLUMEUP / KEY_POWER and must not be grabbed.
                role = BUILTIN.get(d.name)
                if role and role not in found:
                    found[role] = d
                else:
                    d.close()
            if len(found) == len(BUILTIN):
                break
            time.sleep(0.5)
        for role, d in found.items():
            try:
                d.grab()
            except OSError as e:
                log.error("cannot grab %s (%s): %s", role, d.path, e)
                continue
            log.info("%s: %s (%s)", role, d.name, d.path)
            self.devices.append(d)
        self.gamepad = found.get("gamepad")
        if not self.gamepad:
            log.error("gamepad '%s' not found", GAMEPAD_NAME)
        else:
            self._setup_gamepad()
        for d in self.devices:
            self._watch(d)

    def _watch(self, d):
        self.watches[d.fd] = GLib.io_add_watch(d.fd, GLib.IO_IN | GLib.IO_HUP | GLib.IO_ERR,
                                               self._on_device, d)

    def _setup_gamepad(self):
        self.absinfo = {}
        for code, info in self.gamepad.capabilities().get(E.EV_ABS, []):
            self.absinfo[code] = info
        self.haptic_id = None
        self.step_ids = {}     # (magnitude, ms) -> uploaded effect id, for SPRING_PULSES
        if E.EV_FF in self.gamepad.capabilities():
            try:
                self.haptic_id = self._upload_rumble(0xFFFF, 450)   # shutdown, re-centre
                for strength in SPRING_PULSES:
                    mag = self._magnitude(strength)
                    if mag and (mag, SPRING_PULSE_MS) not in self.step_ids:
                        self.step_ids[(mag, SPRING_PULSE_MS)] = self._upload_rumble(mag, SPRING_PULSE_MS)
            except OSError as e:
                log.warning("rumble not available: %s", e)

    def _magnitude(self, strength):
        scale = max(0.0, min(1.0, self.core.s["haptic_strength"]))
        return int(round(strength * scale * 0xFFFF))

    def _upload_rumble(self, magnitude, ms):
        rumble = ff.Rumble(strong_magnitude=magnitude, weak_magnitude=magnitude)
        eff = ff.Effect(E.FF_RUMBLE, -1, 0, ff.Trigger(0, 0), ff.Replay(ms, 0),
                        ff.EffectType(ff_rumble_effect=rumble))
        return self.gamepad.upload_effect(eff)

    # ---------------------------------------------------- stick re-centre
    # The stick driver (rocknix-singleadc-joypad) measures each axis' centre ONCE, from a single
    # ADC reading, when the device is first opened; a bad reading leaves a stick drifting until
    # the device is reopened. We are the only user of the device, so closing and reopening it
    # makes the driver measure the centre again. Any axis still off-centre afterwards gets a
    # software correction. Triggered by SIGUSR1 (the "Re-center sticks" app).
    RECENTER_THRESHOLD = 0.08      # fraction of full travel still counted as "off-centre"

    def _recenter(self):
        g = self.gamepad
        if g is None:
            spawn("notify-send", "-t", "4000", "Re-center sticks", "Gamepad not found")
            return True
        log.info("re-centre: reopening %s", g.path)
        path = g.path
        wid = self.watches.pop(g.fd, None)
        if wid:
            GLib.source_remove(wid)
        try:
            g.ungrab()
        except OSError:
            pass
        g.close()
        self.devices.remove(g)
        self.pad_ff = {}           # effects lived on the old file handle
        time.sleep(0.2)
        try:
            g = evdev.InputDevice(path)
            g.grab()
        except OSError as e:
            log.error("re-centre: cannot reopen %s: %s; restarting", path, e)
            GLib.idle_add(self._quit)
            return True
        self.gamepad = g
        self.devices.append(g)
        self._setup_gamepad()
        self._watch(g)

        # Verify: sample the axes for ~0.5 s and correct what is still off-centre.
        samples = {code: [] for code in HW_AXES}
        for _ in range(10):
            time.sleep(0.05)
            for code in HW_AXES:
                samples[code].append(g.absinfo(code).value)
        self.axis_offset = {}
        report = []
        for code, vals in samples.items():
            info = self.absinfo.get(code)
            if not info or info.max == info.min:
                continue
            half = (info.max - info.min) / 2.0
            avg = sum(vals) / len(vals)
            steady = (max(vals) - min(vals)) <= 2 * max(info.fuzz, 1) + 8
            if steady and abs(avg) > self.RECENTER_THRESHOLD * half:
                self.axis_offset[code] = int(round(avg))
            report.append("%s %+d%%" % (HW_AXES[code], round(100 * avg / half)))
        now = time.monotonic()
        for name in HW_AXES.values():
            self._run(self.core.axis(name, 0.0, now))
        log.info("re-centre: driver centre re-measured; rest %s; software offsets %s",
                 ", ".join(report), self.axis_offset or "none")
        self._haptic()
        msg = "Sticks re-centered." + (" Correction applied to " + ", ".join(HW_AXES[c] for c in self.axis_offset)
                                       if self.axis_offset else "")
        spawn("notify-send", "-t", "4000", "Re-center sticks", msg)
        return True

    def _create_virtual_devices(self):
        self.mouse = evdev.UInput({
            E.EV_KEY: [E.BTN_LEFT, E.BTN_RIGHT, E.BTN_MIDDLE],
            E.EV_REL: [E.REL_X, E.REL_Y, E.REL_WHEEL, E.REL_HWHEEL, E.REL_WHEEL_HI_RES, E.REL_HWHEEL_HI_RES],
        }, name="rg35xxh virtual mouse")
        # No power/sleep keys: logind would otherwise watch this device for them.
        keys = [k for k in range(1, 249) if k not in (E.KEY_POWER, E.KEY_SLEEP, E.KEY_SUSPEND, E.KEY_WAKEUP)]
        self.keyboard = evdev.UInput({E.EV_KEY: keys}, name="rg35xxh virtual keyboard")

    def _create_pad(self):
        caps = {
            E.EV_KEY: [E.BTN_A, E.BTN_B, E.BTN_X, E.BTN_Y, E.BTN_TL, E.BTN_TR, E.BTN_SELECT,
                       E.BTN_START, E.BTN_MODE, E.BTN_THUMBL, E.BTN_THUMBR],
            E.EV_ABS: [(c, evdev.AbsInfo(0, -32768, 32767, 16, 128, 0)) for c in (E.ABS_X, E.ABS_Y, E.ABS_RX, E.ABS_RY)]
            + [(c, evdev.AbsInfo(0, 0, 255, 0, 0, 0)) for c in (E.ABS_Z, E.ABS_RZ)]
            + [(c, evdev.AbsInfo(0, -1, 1, 0, 0, 0)) for c in (E.ABS_HAT0X, E.ABS_HAT0Y)],
            E.EV_FF: [E.FF_RUMBLE],
        }
        # Identify as an Xbox 360 controller so SDL/Moonlight use the standard mapping.
        self.pad = evdev.UInput(caps, name="Microsoft X-Box 360 pad", vendor=0x045E, product=0x028E,
                                version=0x110, bustype=E.BUS_USB, max_effects=16)
        self.pad_ff = {}
        self.pad_watch = GLib.io_add_watch(self.pad.fd, GLib.IO_IN, self._on_pad_fd)
        log.info("gamepad mode: virtual Xbox pad created")

    def _destroy_pad(self):
        if self.pad:
            GLib.source_remove(self.pad_watch)
            for phys in self.pad_ff.values():
                try:
                    self.gamepad.erase_effect(phys)
                except OSError:
                    pass
            self.pad.close()
            self.pad = None
            log.info("desktop mode: virtual pad removed")

    # ------------------------------------------- display side (ui.py, own process)
    # The daemon itself never connects to the display: GDK ends a process with _exit() when its
    # Wayland display goes away (every log-out), which would skip the clean exit. The on-screen
    # keyboard and the touch target live in a child process instead (JSON lines over its
    # stdin/stdout); it is restarted if it ends, and ends by itself when the daemon does.
    def _ui_start(self):
        self.ui_retry = None
        if not os.environ.get("WAYLAND_DISPLAY"):
            log.warning("no WAYLAND_DISPLAY: on-screen keyboard unavailable")
            return False
        try:
            self.ui = subprocess.Popen(
                [sys.executable, "-m", "rg35xxh_inputd.ui", json.dumps(self.core.bind)],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE)   # stderr: same log as ours
        except OSError as e:
            log.warning("cannot start the on-screen keyboard process: %s", e)
            self._ui_schedule()
            return False
        os.set_blocking(self.ui.stdin.fileno(), False)   # a stuck UI must never block input
        self.ui_buf = b""
        self.ui_watch = GLib.io_add_watch(self.ui.stdout.fileno(), GLib.IO_IN | GLib.IO_HUP | GLib.IO_ERR,
                                          self._on_ui)
        return False

    def _ui_schedule(self):
        if self.ui_retry is None:
            self.ui_retry = GLib.timeout_add(int(self.ui_backoff * 1000), self._ui_start)
            self.ui_backoff = min(self.ui_backoff * 2, 60)

    def _ui_send(self, *cmd):
        if self.ui is None:
            return
        try:
            os.write(self.ui.stdin.fileno(), (json.dumps(cmd) + "\n").encode())
        except BlockingIOError:
            log.warning("on-screen keyboard process not reading: dropped %s", cmd[:2])
        except OSError:
            pass                            # it ended: _on_ui sees the hang-up

    def _on_ui(self, fd, cond):
        try:
            data = os.read(fd, 65536)
        except OSError:
            data = b""
        if not data:
            self._ui_stop("ended")
            self._ui_schedule()
            return False
        self.ui_buf += data
        while b"\n" in self.ui_buf:
            line, self.ui_buf = self.ui_buf.split(b"\n", 1)
            try:
                kind, *args = json.loads(line)
                if kind == "ready":
                    self.ui_backoff = 2
                    log.info("on-screen keyboard process ready (pid %d)", self.ui.pid)
                elif kind == "visible":
                    self.osk_visible = bool(args[0])
                    self.core.set_osk_visible(self.osk_visible)
                elif kind == "type":
                    self._type_combo(args[0], args[1])
            except Exception as e:          # bad line or unknown key: ignore it
                log.warning("on-screen keyboard process: %r: %s", line[:80], e)
        return True

    def _ui_stop(self, why):
        """Stop the UI process (if still running) and forget it."""
        ui, self.ui = self.ui, None
        if self.ui_watch:
            GLib.source_remove(self.ui_watch)
            self.ui_watch = None
        if self.osk_visible:
            self.osk_visible = False
            self.core.set_osk_visible(False)
        if ui is None:
            return
        for f in (ui.stdin, ui.stdout):
            try:
                f.close()                   # stdin EOF: the UI process exits by itself
            except OSError:
                pass
        try:
            ui.wait(timeout=1)
        except subprocess.TimeoutExpired:
            ui.terminate()
            try:
                ui.wait(timeout=1)
            except subprocess.TimeoutExpired:
                ui.kill()
                ui.wait()
        log.info("on-screen keyboard process %s (exit %s)", why, ui.returncode)

    def _type_combo(self, mods, key):
        codes = [E.ecodes[m] for m in mods]
        k = E.ecodes[key]
        for c in codes:
            self.keyboard.write(E.EV_KEY, c, 1)
        self.keyboard.write(E.EV_KEY, k, 1)
        self.keyboard.syn()
        self.keyboard.write(E.EV_KEY, k, 0)
        for c in reversed(codes):
            self.keyboard.write(E.EV_KEY, c, 0)
        self.keyboard.syn()

    # ------------------------------------------------------------- events
    def _on_device(self, fd, cond, dev):
        if cond & (GLib.IO_HUP | GLib.IO_ERR):
            # Built-in devices can be re-created (e.g. after resume): exit and let the
            # session's restart loop start a fresh daemon that opens them again.
            log.error("device lost: %s (%s), restarting", dev.path, dev.name)
            GLib.idle_add(self._quit)
            return False
        now = time.monotonic()
        try:
            for ev in dev.read():
                if ev.type == E.EV_KEY and ev.value in (0, 1):
                    log.debug("key 0x%x %s -> %s", ev.code, "down" if ev.value else "up",
                              HW_BUTTONS.get(ev.code))
                if ev.type == E.EV_KEY and ev.code in HW_BUTTONS and ev.value in (0, 1):
                    self._run(self.core.button(HW_BUTTONS[ev.code], ev.value == 1, now))
                elif ev.type == E.EV_ABS and ev.code in HW_AXES:
                    self._run(self.core.axis(HW_AXES[ev.code], self._norm(ev.code, ev.value), now))
        except BlockingIOError:
            pass
        except OSError as e:
            log.error("read error on %s: %s", dev.path, e)
        return True

    def _norm(self, code, value):
        info = self.absinfo.get(code)
        if not info or info.max == info.min:
            return 0.0
        value -= self.axis_offset.get(code, 0)
        mid = (info.max + info.min) / 2.0
        v = (value - mid) / ((info.max - info.min) / 2.0)
        if self.hw.get("invert_" + HW_AXES[code]):
            v = -v
        return v

    def _tick(self):
        self.ticks += 1
        now = time.monotonic()
        if self.ticks % 10 == 0:
            self.core.set_screen_off(os.path.exists(runtime_flag("rg35xxh-screen-off")))
            self._layout_reload()
            self.core.set_osk_visible(self.osk_visible)
        self._run(self.core.tick(now))
        return True

    def _layout_reload(self):
        """Screen layout for per-screen pointer speed: JSON written by rg35xxh-display on every
        layout change ([{"x","y","w","h","scale"}, ...]); none = handheld only, speed 1."""
        path = runtime_flag("rg35xxh-pointer-layout")
        try:
            mtime = os.stat(path).st_mtime
        except OSError:
            mtime = None
        if mtime == self.layout_mtime:
            return
        self.layout_mtime = mtime
        rects = []
        if mtime is not None:
            try:
                import json
                with open(path) as f:
                    rects = json.load(f)
            except (OSError, ValueError):
                rects = []
        self.layout.set_rects(rects)
        if len(self.layout.rects) > 1 and getattr(self, "mouse", None):
            # Two screens: start from a known point. A long move up-left ends in the layout's
            # top-left corner (the compositor clamps it), and the estimate starts there too.
            self.mouse.write(E.EV_REL, E.REL_X, -30000)
            self.mouse.write(E.EV_REL, E.REL_Y, -30000)
            self.mouse.syn()
            self.layout.x, self.layout.y = self.layout._closest(-30000, -30000)
        self.core.pointer_scale = self.layout.scale(self.core.s["display_speed_scale"])
        log.info("screen layout for pointer speed: %s -> x%.2f", rects, self.core.pointer_scale)

    # ------------------------------------------------------------ actions
    def _run(self, actions):
        mouse_dirty = False
        for a in actions:
            kind = a[0]
            if kind == "rel":
                self.mouse.write(E.EV_REL, E.REL_X, a[1])
                self.mouse.write(E.EV_REL, E.REL_Y, a[2])
                mouse_dirty = True
                self.layout.move(a[1], a[2])
                self.core.pointer_scale = self.layout.scale(self.core.s["display_speed_scale"])
            elif kind == "wheel":
                if a[1]:
                    self.mouse.write(E.EV_REL, E.REL_WHEEL_HI_RES, a[1])
                    self._wheel_notch(E.REL_WHEEL, a[1], 0)
                if a[2]:
                    self.mouse.write(E.EV_REL, E.REL_HWHEEL_HI_RES, a[2])
                    self._wheel_notch(E.REL_HWHEEL, a[2], 1)
                mouse_dirty = True
            elif kind == "mouse":
                btn = {"left": E.BTN_LEFT, "right": E.BTN_RIGHT, "middle": E.BTN_MIDDLE}[a[1]]
                self.mouse.write(E.EV_KEY, btn, 1 if a[2] else 0)
                mouse_dirty = True
            elif kind == "key":
                self.keyboard.write(E.EV_KEY, E.ecodes[a[1]], 1 if a[2] else 0)
                self.keyboard.syn()
                if self.osk_visible:                    # L1 / R1 / R2: show it on the keyboard too
                    self._ui_send("osk", "key_state", a[1], a[2])
            elif kind == "clipboard":
                self._clipboard(a[1])
            elif kind == "osk" and not self.ui:
                log.warning("on-screen keyboard requested but unavailable")
            elif kind == "osk":
                if a[1] == "toggle":
                    self._ui_send("osk", "toggle")
                    self.osk_visible = not self.osk_visible     # the UI process confirms it
                    self.core.set_osk_visible(self.osk_visible)
                    log.info("on-screen keyboard %s", "shown" if self.osk_visible else "hidden")
                elif a[1] == "move":
                    self._ui_send("osk", "move", a[2], a[3])
                elif a[1] in ("press", "release", "repeat", "shift"):
                    self._ui_send("osk", a[1])
            elif kind == "mode":
                if a[1] == "gamepad":
                    if self.osk_visible:
                        self._ui_send("osk", "hide")
                        self.osk_visible = False
                        self.core.set_osk_visible(False)
                    self._hide_cursor()                   # no pointer outside desktop mode
                    if self.bt:
                        flag, title, text, _icon = EXT_MODES[self.ext]
                        set_flag(flag, True)
                        spawn("notify-send", "-t", "6000", title, text)
                    else:
                        self._create_pad()
                        set_flag("rg35xxh-gamepad-mode", True)
                        spawn("notify-send", "-t", "2500", "Gamepad mode", "Hold Start for 1 s to return to desktop mode")
                else:
                    if self.bt:
                        title = EXT_MODES[self.ext][1]
                        self._bt_close()
                        spawn("notify-send", "-t", "2500", "Desktop mode", f"{title} stopped")
                    else:
                        self._destroy_pad()
                        spawn("notify-send", "-t", "1500", "Desktop mode")
                    set_flag("rg35xxh-gamepad-mode", False)
                self._mode_feedback(EXT_MODES[self.ext][3] if self.bt else a[1])   # icon shake + haptic wobble
            elif kind in ("pad_key", "pad_abs"):
                etype = E.EV_KEY if kind == "pad_key" else E.EV_ABS
                if self.bt:
                    self._bt_send(etype, E.ecodes[a[1]], a[2])
                elif self.pad:
                    self.pad.write(etype, E.ecodes[a[1]], a[2])
                    self.pad.syn()
            elif kind == "cmd":
                self._command(a[1])
            elif kind == "screen_wake":
                spawn("rg35xxh-screen-on")
            elif kind == "shutdown":
                self._shutdown()
        if mouse_dirty:
            self.mouse.syn()

    def _wheel_notch(self, code, hires, idx):
        # Legacy wheel events for apps without hi-res support: one per 120 units.
        acc = getattr(self, "_notch_acc", [0, 0])
        acc[idx] += hires
        notches = int(acc[idx] / 120)
        if notches:
            acc[idx] -= notches * 120
            self.mouse.write(E.EV_REL, code, notches)
        self._notch_acc = acc

    def _clipboard(self, what):
        letter = "KEY_C" if what == "copy" else "KEY_V"
        mods = ["KEY_LEFTCTRL"]
        if self._focused_is_terminal():
            mods.append("KEY_LEFTSHIFT")
        self._type_combo(mods, letter)

    def _focused_is_terminal(self):
        # One query: repeated app_id matches are OR-ed by wlrctl; state:active = focused window.
        if not shutil.which("wlrctl"):
            return False
        argv = ["wlrctl", "toplevel", "find"] + ["app_id:" + a for a in TERMINALS] + ["state:active"]
        try:
            return subprocess.run(argv, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                  timeout=0.5).returncode == 0
        except (OSError, subprocess.TimeoutExpired):
            return False

    def _command(self, name):
        if name == "power_menu":
            spawn("rg35xxh-power-menu")
        elif name in ("volume_up", "volume_down"):
            step = "5%+" if name == "volume_up" else "5%-"
            try:
                subprocess.run(["wpctl", "set-volume", "-l", "1.0", "@DEFAULT_AUDIO_SINK@", step],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=1)
                out = subprocess.run(["wpctl", "get-volume", "@DEFAULT_AUDIO_SINK@"], capture_output=True,
                                     text=True, timeout=1).stdout       # "Volume: 0.55 [MUTED]"
                vol = round(float(out.split()[1]) * 100)
                self._osd(0 if "MUTED" in out else vol, "volume")
            except (OSError, subprocess.TimeoutExpired, ValueError, IndexError) as e:
                log.warning("volume: %s", e)
        elif name in ("brightness_up", "brightness_down"):
            self._brightness(+1 if name == "brightness_up" else -1)

    BACKLIGHT = "/sys/class/backlight/backlight"
    BRIGHTNESS_MIN = 0.05      # never fully dark
    BRIGHTNESS_STEP = 0.10

    def _brightness(self, direction):
        try:
            with open(self.BACKLIGHT + "/max_brightness") as f:
                mx = int(f.read())
            with open(self.BACKLIGHT + "/brightness") as f:
                cur = int(f.read())
            new = cur + direction * round(mx * self.BRIGHTNESS_STEP)
            new = max(round(mx * self.BRIGHTNESS_MIN), min(mx, new))
            with open(self.BACKLIGHT + "/brightness", "w") as f:
                f.write(str(new))
            self._osd(round(new * 100 / mx), "brightness")
        except (OSError, ValueError) as e:
            log.warning("brightness: %s", e)

    def _osd(self, percent, style):
        """Show a volume/brightness bar: one wob per kind (wob 0.14 has no per-value styles),
        fed through $XDG_RUNTIME_DIR/wob-<kind>.sock, started by the session autostart."""
        path = runtime_flag(f"wob-{style}.sock")
        try:
            fd = os.open(path, os.O_WRONLY | os.O_NONBLOCK)
        except OSError:
            return  # no OSD running
        try:
            os.write(fd, f"{max(0, min(100, percent))}\n".encode())
        except OSError:
            pass
        finally:
            os.close(fd)

    def _shutdown(self):
        log.info("power held: shutting down")
        self._haptic()
        try:
            with open(os.path.join(STATUS_LED, "trigger"), "w") as f:
                f.write("timer")
        except OSError as e:
            log.warning("status LED: %s", e)
        spawn("notify-send", "-u", "critical", "-t", "10000", "Shutting down…")
        GLib.timeout_add(600, lambda: spawn("systemctl", "poweroff") or False)

    def _haptic(self):
        self._play_effect(self.haptic_id)

    def _play_effect(self, eid):
        if self.gamepad is not None and eid is not None:
            try:
                self.gamepad.write(E.EV_FF, eid, 1)
            except OSError as e:
                log.warning("rumble failed: %s", e)
        return False

    # ------------------------------------------------ pointer hiding
    def _hide_cursor(self):
        if self.touch:
            return
        if not self.ui:                     # no display side: cannot show the tap target
            return
        self._ui_send("target", "show")      # 2x2 px transparent overlay window, top-left corner
        caps = {E.EV_KEY: [E.BTN_TOUCH],
                E.EV_ABS: [(E.ABS_X, evdev.AbsInfo(0, 0, TOUCH_W - 1, 0, 0, 0)),
                           (E.ABS_Y, evdev.AbsInfo(0, 0, TOUCH_H - 1, 0, 0, 0)),
                           (E.ABS_MT_SLOT, evdev.AbsInfo(0, 0, 0, 0, 0, 0)),
                           (E.ABS_MT_TRACKING_ID, evdev.AbsInfo(0, 0, 65535, 0, 0, 0)),
                           (E.ABS_MT_POSITION_X, evdev.AbsInfo(0, 0, TOUCH_W - 1, 0, 0, 0)),
                           (E.ABS_MT_POSITION_Y, evdev.AbsInfo(0, 0, TOUCH_H - 1, 0, 0, 0))]}
        try:
            self.touch = evdev.UInput(caps, name="rg35xxh virtual touch", input_props=[E.INPUT_PROP_DIRECT])
        except (OSError, evdev.UInputError) as e:
            log.warning("cannot hide the pointer (virtual touch): %s", e)
            self._ui_send("target", "hide")
            return
        GLib.timeout_add(400, self._touch_tap)       # let libinput pick the new device up first

    def _touch_tap(self):
        t = self.touch
        if self.core.mode == "gamepad":
            x, y = TOUCH_TAP
            for code, v in ((E.ABS_MT_SLOT, 0), (E.ABS_MT_TRACKING_ID, 1), (E.ABS_MT_POSITION_X, x),
                            (E.ABS_MT_POSITION_Y, y), (E.ABS_X, x), (E.ABS_Y, y)):
                t.write(E.EV_ABS, code, v)
            t.write(E.EV_KEY, E.BTN_TOUCH, 1)
            t.syn()
            t.write(E.EV_ABS, E.ABS_MT_TRACKING_ID, -1)
            t.write(E.EV_KEY, E.BTN_TOUCH, 0)
            t.syn()
        GLib.timeout_add(300, self._touch_close)
        return False

    def _touch_close(self):
        if self.touch:
            self.touch.close()
            self.touch = None
        self._ui_send("target", "hide")
        return False

    # ------------------------------------------------ mode-change feedback
    def _mode_feedback(self, new):
        """Shake the old mode's taskbar icon and wobble the motor, then show the new icon."""
        if self.anim:
            GLib.source_remove(self.anim["timer"])
            self.anim = None
        if self.icon_mode == new:
            set_flag(INPUTMODE_FRAME, False)
            self._signal_waybar()
            return
        self.anim = {"old": self.icon_mode, "new": new, "k": 0}
        self._anim_step()
        self.anim["timer"] = GLib.timeout_add(SPRING_STEP_MS, self._anim_step)

    def _anim_step(self):
        an = self.anim
        k = an["k"]
        if k < len(ICON_FRAMES):
            with open(runtime_flag(INPUTMODE_FRAME), "w") as f:
                f.write(f"{an['old']} {ICON_FRAMES[k]}\n")
            eid = self.step_ids.get((self._magnitude(SPRING_PULSES[k]), SPRING_PULSE_MS))
            if eid is not None:
                GLib.timeout_add(HAPTIC_LAG_MS, self._play_effect, eid)
            an["k"] = k + 1
            self._signal_waybar()
            return True
        set_flag(INPUTMODE_FRAME, False)
        self.icon_mode = an["new"]
        self.anim = None
        self._signal_waybar()
        return False

    def _signal_waybar(self):
        """SIGRTMIN+WAYBAR_SIGNAL to Waybar (re-runs rg35xxh-inputmode). Cheaper than pkill."""
        for _ in range(2):
            if self.waybar_pid is None or _comm(self.waybar_pid) != "waybar":   # gone or restarted
                self.waybar_pid = next((int(d) for d in os.listdir("/proc") if d.isdigit()
                                        and _comm(d) == "waybar"), None)
                if self.waybar_pid is None:
                    return
            if _proc_age(self.waybar_pid) < 3:     # starting up: a real-time signal would kill it
                return
            try:
                os.kill(self.waybar_pid, signal.SIGRTMIN + WAYBAR_SIGNAL)
                return
            except ProcessLookupError:
                self.waybar_pid = None

    # ------------------------------------------- rumble from the virtual pad
    _EV = struct.Struct("llHHi")

    def _on_pad_fd(self, fd, cond):
        if not self.pad:
            return False
        try:
            data = os.read(fd, self._EV.size * 16)
        except BlockingIOError:
            return True
        except OSError:
            return True
        for i in range(0, len(data) - self._EV.size + 1, self._EV.size):
            _, _, etype, code, value = self._EV.unpack_from(data, i)
            try:
                if etype == E.EV_UINPUT and code == E.UI_FF_UPLOAD:
                    # acknowledge at once; the hardware upload goes through the motor gate
                    up = self.pad.begin_upload(value)
                    eff = ff.Effect.from_buffer_copy(up.effect)
                    if eff.ff_replay.length == 0:          # endless: cap it, re-trigger while playing
                        eff.ff_replay.length = MOTOR_GAME_MAX_MS
                        self.motor_game_endless.add(up.effect.id)
                    else:
                        self.motor_game_endless.discard(up.effect.id)
                    self.motor_pending_upload[up.effect.id] = eff
                    up.retval = 0
                    self.pad.end_upload(up)
                    self._motor_kick()
                elif etype == E.EV_UINPUT and code == E.UI_FF_ERASE:
                    er = self.pad.begin_erase(value)
                    self.motor_pending_upload.pop(er.effect_id, None)
                    self.motor_pending_play.pop(er.effect_id, None)
                    self.motor_game_endless.discard(er.effect_id)
                    self.motor_game_active.discard(er.effect_id)
                    phys = self.pad_ff.pop(er.effect_id, None)
                    if phys is not None:
                        self.gamepad.erase_effect(phys)
                    er.retval = 0
                    self.pad.end_erase(er)
                elif etype == E.EV_FF and (code in self.pad_ff or code in self.motor_pending_upload):
                    self.motor_pending_play[code] = value
                    self._motor_kick()
            except Exception as e:  # rumble is best effort
                log.debug("rumble forward: %s", e)
        return True

    # ---------------------------------------------------------------- run
    def _quit(self):
        self._loop.quit()
        return False

    # ------------------------------------------------- BT Controller mode
    def _request_bt(self):
        """SIGUSR2 (External Controller app): connect to the running external-controller service
        (rg35xxh-btpad or rg35xxh-usbpad) and send it the controls."""
        if self.bt:
            return True
        try:
            s = socket.socket(socket.AF_UNIX, socket.SOCK_SEQPACKET)
            s.settimeout(1.0)
            s.connect(EXT_SOCKET)
            hello = s.recv(64)
            s.settimeout(0.2)
        except OSError as e:
            log.warning("External controller: cannot connect to %s: %s", EXT_SOCKET, e)
            spawn("notify-send", "-t", "5000", "External Controller", "Could not connect to the controller service")
            return True
        self.ext = "usb" if hello == b"hello usb" else "bt"
        self.bt = s
        self.bt_watch = GLib.io_add_watch(s.fileno(), GLib.IO_IN | GLib.IO_HUP | GLib.IO_ERR, self._on_bt_data)
        log.info("%s: connected to %s", EXT_MODES[self.ext][1], EXT_SOCKET)
        if self.core.mode == "gamepad":           # local gamepad mode -> BT Controller mode
            self._destroy_pad()
            set_flag("rg35xxh-gamepad-mode", False)
            self.core.request_gamepad(combo_exit=True)
            self._run([("mode", "gamepad")] + [("pad_abs", PAD_AXES[n], int(round(v * 32767)))
                                               for n, v in self.core.axes.items()])
        else:
            self._run(self.core.request_gamepad(combo_exit=True))
        return True

    def _bt_send(self, etype, code, value):
        try:
            self.bt.send(BT_EVENT.pack(etype, code, value))
        except OSError as e:
            log.warning("BT Controller: send failed: %s", e)
            self._bt_lost()

    def _on_bt_data(self, fd, cond):
        """Message from the service (vibration), or EOF / hang-up: the service stopped."""
        data = b""
        if cond & GLib.IO_IN:
            try:
                data = self.bt.recv(64)
            except BlockingIOError:
                return True
            except OSError:
                data = b""
        if data.startswith(b"rumble "):
            try:
                big, small = (int(v) for v in data.split()[1:3])
                self._ext_rumble(big, small)
            except ValueError:
                pass
            return True
        if data:
            return True                            # unknown message: ignore
        self.bt_watch = None
        self._bt_lost()
        return False

    def _ext_rumble(self, big, small):
        """Vibration requested by the PC (Wired, or BT with the Xbox profile): the stronger of the two motors' values, on the
        handheld's single motor, through the motor gate. Runs until the PC sends 0 0 / the mode ends."""
        self.motor_ext_want = round(max(big, small) / 255 * MOTOR_LEVELS)
        self._motor_kick()

    # ------------------------------------------------ motor gate (see MOTOR_INTERVAL)
    def _motor_kick(self):
        if self.motor_timer:
            return
        wait = max(0.0, self.motor_last + MOTOR_INTERVAL - time.monotonic())
        self.motor_timer = GLib.timeout_add(int(wait * 1000), self._motor_flush)

    def _motor_ok(self):
        return self.gamepad is not None and E.EV_FF in self.gamepad.capabilities()

    def _ext_levels_upload(self):
        """One fixed-length effect per strength level, uploaded while the motor is idle."""
        if self.motor_ext_ids:
            return
        for lvl in range(1, MOTOR_LEVELS + 1):
            mag = lvl * 0xFFFF // MOTOR_LEVELS
            rumble = ff.Rumble(strong_magnitude=mag, weak_magnitude=mag)
            eff = ff.Effect(E.FF_RUMBLE, -1, 0, ff.Trigger(0, 0), ff.Replay(MOTOR_EFFECT_MS, 0),
                            ff.EffectType(ff_rumble_effect=rumble))
            self.motor_ext_ids[lvl] = self.gamepad.upload_effect(eff)

    def _ext_levels_free(self):
        for eid in self.motor_ext_ids.values():
            try:
                self.gamepad.write(E.EV_FF, eid, 0)
                self.gamepad.erase_effect(eid)
            except OSError:
                pass
        self.motor_ext_ids = {}
        self.motor_ext_applied = 0
        self.motor_ext_want = 0

    def _motor_flush(self):
        self.motor_timer = None
        if not self._motor_ok():
            self.motor_pending_upload.clear()
            self.motor_pending_play.clear()
            return False
        self.motor_last = time.monotonic()
        try:
            # games (virtual pad): latest upload per effect, then play/stop changes
            for vid, eff in list(self.motor_pending_upload.items()):
                existing = self.pad_ff.get(vid)
                eff.id = existing if existing is not None else -1
                self.pad_ff[vid] = self.gamepad.upload_effect(eff)
            self.motor_pending_upload.clear()
            for vid, val in list(self.motor_pending_play.items()):
                if vid in self.pad_ff:
                    self.gamepad.write(E.EV_FF, self.pad_ff[vid], val)
                    if vid in self.motor_game_endless and val:
                        self.motor_game_active.add(vid)
                    else:
                        self.motor_game_active.discard(vid)
            self.motor_pending_play.clear()
            # PC (external modes): switch between the pre-uploaded level effects
            want = self.motor_ext_want
            if want != self.motor_ext_applied:
                if self.motor_ext_applied and self.motor_ext_applied in self.motor_ext_ids:
                    self.gamepad.write(E.EV_FF, self.motor_ext_ids[self.motor_ext_applied], 0)
                if want:
                    self._ext_levels_upload()
                    self.gamepad.write(E.EV_FF, self.motor_ext_ids[want], 1)
                self.motor_ext_applied = want
        except OSError as e:
            log.debug("motor: %s", e)
        self._motor_refresh_schedule()
        return False

    def _motor_refresh_schedule(self):
        if self.motor_refresh_timer is None and (self.motor_ext_applied or self.motor_game_active):
            self.motor_refresh_timer = GLib.timeout_add(int(MOTOR_REFRESH * 1000), self._motor_refresh)

    def _motor_refresh(self):
        """Re-trigger long vibrations before their fixed-length effect runs out."""
        self.motor_refresh_timer = None
        if not self._motor_ok():
            return False
        try:
            if self.motor_ext_applied in self.motor_ext_ids:
                self.gamepad.write(E.EV_FF, self.motor_ext_ids[self.motor_ext_applied], 1)
            for vid in list(self.motor_game_active):
                if vid in self.pad_ff:
                    self.gamepad.write(E.EV_FF, self.pad_ff[vid], 1)
        except OSError as e:
            log.debug("motor refresh: %s", e)
        self._motor_refresh_schedule()
        return False

    def _bt_lost(self):
        if not self.bt:
            return
        log.info("%s: service ended, back to desktop mode", EXT_MODES[self.ext][1])
        actions = self.core.request_desktop()
        if actions:
            self._run(actions)                    # closes the socket via the "mode" action
        else:
            self._bt_close()

    def _bt_close(self):
        if self._motor_ok():
            self._ext_levels_free()               # stop any vibration the PC left on
        if self.bt_watch:
            GLib.source_remove(self.bt_watch)
            self.bt_watch = None
        if self.bt:
            try:
                self.bt.close()                   # btpad sees EOF and stops
            except OSError:
                pass
            self.bt = None
            log.info("%s: disconnected", EXT_MODES[self.ext][1])
        for flag, *_ in EXT_MODES.values():
            set_flag(flag, False)

    def run(self):
        GLib.timeout_add(10, self._tick)
        self.beats = 0
        self._heartbeat()
        GLib.timeout_add(HEARTBEAT_MS, self._heartbeat)
        GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGUSR1, self._recenter)
        GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGUSR2, self._request_bt)
        for sig in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
            GLib.unix_signal_add(GLib.PRIORITY_HIGH, sig, self._on_term, sig)
        # A plain GLib main loop (no GTK in this process, see ui.py). Quitting PyGObject's Gtk.main()
        # from a signal handler deadlocked (7 of 8 tries on the device); ui.py avoids it too.
        self._loop = GLib.MainLoop()
        self._loop.run()

    # Watchdog (rg35xxh-inputd wrapper): the daemon grabs every button, the power key included, so
    # a hung main loop would leave no way to switch the handheld off but the power chip's forced
    # cut. The main loop writes a counter here every second; the wrapper restarts a daemon whose
    # counter stops. The file exists only while the main loop runs (not during start-up or the
    # clean exit), so neither is mistaken for a hang.
    def _heartbeat(self):
        self.beats += 1
        try:
            with open(HEARTBEAT, "w") as f:
                f.write(f"{self.beats}\n")
        except OSError as e:
            log.warning("heartbeat: %s", e)
        return True

    def _on_term(self, sig):
        log.info("%s: clean exit", signal.Signals(sig).name)
        self._quit()
        return False

    # ------------------------------------------------ clean exit
    # SIGTERM (log-out: the next session's autostart stops this one), SIGINT/SIGHUP and errors all
    # end here. We stop the motor and free every vibration effect, the virtual devices and the grabs
    # ourselves, one step at a time, instead of leaving it all to the kernel's teardown when the
    # process dies -- while the next session's daemon may already be grabbing the same gamepad and
    # uploading its effects. The joypad driver's vibration path (ff-memless + PWM work) has locked
    # the whole system up before (see MOTOR_INTERVAL); a log-out that killed the old daemon right as
    # the new one started froze the handheld (input, Wi-Fi, SSH) and needed a battery reset.
    # The single-instance lock (main) makes the next daemon wait until this one is gone.
    def cleanup(self):
        # Also runs for a daemon that was stopped during start-up (__init__ not finished), so
        # every attribute may still be missing: read them with get().
        def step(what, fn, *a):
            try:
                fn(*a)
            except Exception as e:      # keep going: every later step still matters
                log.warning("clean exit: %s: %s", what, e)

        def get(name, default=None):
            return getattr(self, name, default)
        try:
            os.unlink(HEARTBEAT)                    # disarm the watchdog: exiting, not hung
        except FileNotFoundError:                   # (not armed yet: stopped during start-up)
            pass
        for name in ("motor_timer", "motor_refresh_timer", "ui_retry"):
            if get(name):
                step(name, GLib.source_remove, get(name))
                setattr(self, name, None)
        for name in ("motor_game_active", "motor_game_endless", "motor_pending_upload", "motor_pending_play"):
            if get(name) is not None:
                get(name).clear()
        if get("bt"):
            step("external controller", self._bt_close)   # stops + frees the PC's vibration levels
        if get("pad"):
            step("virtual pad", self._destroy_pad)          # frees the games' effects
        g = get("gamepad")
        if g is not None:
            ids = [i for i in [get("haptic_id"), *get("step_ids", {}).values(),
                               *get("motor_ext_ids", {}).values()] if i is not None]
            for eid in ids:
                step("stop effect %d" % eid, g.write, E.EV_FF, eid, 0)
            if ids:
                time.sleep(0.05)
            for eid in ids:
                step("erase effect %d" % eid, g.erase_effect, eid)
            self.haptic_id = None
            self.step_ids = {}
            self.motor_ext_ids = {}
        if get("touch") is not None:
            step("touch", self._touch_close)
        if get("ui") is not None:
            step("on-screen keyboard process", self._ui_stop, "stopped")
        for d in list(get("devices", [])):
            step("ungrab %s" % d.path, d.ungrab)
            step("close %s" % d.path, d.close)
        self.devices = []
        self.gamepad = None
        for name in ("mouse", "keyboard"):
            if get(name) is not None:
                step(name, get(name).close)
        for flag in ("rg35xxh-gamepad-mode", "rg35xxh-bt-mode", "rg35xxh-wired-mode", INPUTMODE_FRAME):
            step(flag, set_flag, flag, False)
        log.info("clean exit: gamepad, vibration and virtual devices released")


HEARTBEAT = runtime_flag("rg35xxh-inputd.alive")   # see _heartbeat (watchdog)
HEARTBEAT_MS = 1000
LOCK_WAIT = 10.0   # s: how long a new daemon waits for the previous one to finish its clean exit


def single_instance():
    """One daemon at a time (see "clean exit"): returns the held lock file, or None if another
    daemon still runs after LOCK_WAIT. The kernel drops the lock when the holder's process is gone,
    so the next daemon never grabs the gamepad while the old one still owns effects on it."""
    import fcntl
    f = open(runtime_flag("rg35xxh-inputd.lock"), "w")
    deadline = time.monotonic() + LOCK_WAIT
    waited = False
    while True:
        try:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
            if waited:
                log.info("previous daemon gone, starting")
            return f
        except BlockingIOError:
            if time.monotonic() >= deadline:
                f.close()
                return None
            if not waited:
                log.info("previous daemon still running: waiting up to %.0f s", LOCK_WAIT)
                waited = True
            time.sleep(0.2)


def main():
    # Touch $XDG_RUNTIME_DIR/rg35xxh-inputd.debug and restart the daemon to log every key event.
    debug = os.path.exists(runtime_flag("rg35xxh-inputd.debug"))
    logging.basicConfig(level=logging.DEBUG if debug else logging.INFO, stream=sys.stderr,
                        format="%(asctime)s %(levelname)s %(message)s")
    lock = single_instance()
    if lock is None:
        log.error("another rg35xxh-inputd still runs; not starting a second one")
        sys.exit(1)
    # Until the main loop installs its own handlers: SIGTERM during start-up still exits through
    # cleanup (Python's default would just die). The object exists before __init__ runs, so a
    # half-started daemon is cleaned up too.
    def early_exit(sig, _frame):
        log.info("%s during start-up: clean exit", signal.Signals(sig).name)
        sys.exit(0)
    for sig in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
        signal.signal(sig, early_exit)
    d = Daemon.__new__(Daemon)
    try:
        d.__init__()
        d.run()
    finally:
        d.cleanup()
        lock.close()


if __name__ == "__main__":
    main()
