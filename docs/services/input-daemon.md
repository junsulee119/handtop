# Input daemon

`rg35xxh-inputd` (`src/inputd`): the controls of the handheld. Implemented by a custom input daemon that grabs the "H700 Gamepad" exclusively and emits virtual mouse/keyboard (desktop mode) or a virtual Xbox-style controller (gamepad mode) via uinput.

- **Desktop mode is the default at boot.** Device is used for desktop control only; gamepad mode is kept for occasional use.
- Physical USB/Bluetooth keyboard and mouse always work normally alongside.
- Bindings live in a plain-text config file on the FAT boot partition (editable from Windows, no rebuild).

## Mapping

| Control | Desktop mode | Gamepad mode |
|---|---|---|
| D-pad | Mouse pointer. With on-screen keyboard open: move between keys | Passed through |
| Left stick | Mouse pointer, any direction, speed follows tilt | Left stick |
| Right stick | Scroll in any direction (vertical + horizontal) | Right stick |
| A | Left click (hold = drag). With keyboard open: type selected key (typing follows whichever button is bound to `click_left`) | Passed through |
| B | Right click | Passed through |
| X | Show/hide on-screen keyboard | Passed through |
| Y | — | Passed through |
| L1 | Esc | Passed through |
| R1 | Enter | Passed through |
| L2 | — | L2 trigger |
| R2 | Backspace | R2 trigger |
| L3 (left stick click) | Copy | Passed through |
| R3 (right stick click) | Paste | Passed through |
| Start (tap) | Switch to gamepad mode | Passed through |
| Start (hold 1 s) | — | Switch to desktop mode |
| Select + Start + L1 + R1 | — | External Controller modes only: back to desktop mode (ends the mode). Holding Start does not exit there |
| Select | — | Passed through |
| F (tap) | — | — (Switch Controller mode: Home; held 0.6 s: Home held) |
| F + Select | — | — (Switch Controller mode: Capture) |
| F + Vol+/− | Brightness | Brightness |
| Vol+/− | System volume | System volume |
| Power (tap) | Power menu | Power menu |
| Power (hold 3 s) | Vibration, then clean shutdown | Same |
| Power (hold ~8–10 s) | Hardware power cut by PMIC (not configurable) | Same |
| R (Reset) | Hardware reset (not mappable) | Same |

## Behaviour notes

- **Left stick:** dead zone against drift; power curve — slow/precise on small tilt, fast at the edge. Max 450 px/s (halved from 900 after device testing).
- **Right stick:** logarithmic curve (`log(1+9x)/log(10)`) — a small push already scrolls at a useful rate, levelling off at 8.4 notches/s at full tilt (0.7× of the original 12 after device testing).
- **D-pad pointer:** digital, half of the left stick's top speed (`dpad_speed_ratio = 0.5`, so 225 px/s with the default 450); it follows if `pointer_max_speed` is changed. The pointer has no libinput acceleration (labwc `rc.xml`), so these are real px/s. On an HDMI display both are scaled by its size (`display_speed_scale`).
- **Vol / F + Vol held:** repeats after 0.4 s, then every 0.12 s (works in desktop and gamepad mode). A pop-up bar ([osd.md](osd.md)) shows the level on the left edge of the screen, vertically, with the number on top: blue for volume, amber for brightness. Brightness steps 10% and never goes below 5%.
- **On-screen keyboard:** custom ([on-screen-keyboard.md](on-screen-keyboard.md)), part of the input daemon, so the daemon always knows whether it is open (its window runs in the daemon's display process, see below). Left stick still moves the pointer while it is open.
- **Copy/paste:** daemon checks the focused app. Terminals get Ctrl+Shift+C / Ctrl+Shift+V; other apps Ctrl+C / Ctrl+V (Ctrl+C in a terminal would kill the running program). Bash bracketed paste must stay enabled so an accidental R3 paste cannot execute a command. Hold-to-paste can be added later if accidental stick clicks are a problem.
- **Gamepad mode:** virtual controller uses standard Xbox layout **by position** (bottom button = Xbox A). F is not forwarded (would open Xbox Game Bar on Windows). Rumble from Moonlight can be forwarded to the motor.
- **External controller modes, Battery saver:** Vol, F + Vol and Power write `$XDG_RUNTIME_DIR/rg35xxh-extpad-wake` (the status screen's wake signal); Power on a dark screen (`rg35xxh-extpad-dark`) only wakes it. When the mode ends and the display is still off, the daemon runs `wlopm --on DSI-1` ([../apps/external-controller.md](../apps/external-controller.md#battery-saver)).
- **Switch Controller mode only** (`request_gamepad(f_buttons=True)`, when the service says `hello switch` or `hello switch-bt`): F gives the two buttons the handheld lacks. **F tap = Home** (pressed for 0.1 s, so the Switch sees it), **F held 0.6 s = Home held** until F is released (quick settings), **F + Select = Capture** (held as long as Select). F + Vol stays brightness: once Vol or Select is pressed with F, F's release sends nothing. Not in BT / Wired Controller mode, where Home would be Xbox Guide (Game Bar). Codes sent to the service: `BTN_MODE` (Home), `KEY_RECORD` (Capture).
- **Start in gamepad mode:** short tap is sent to the PC as Start; only a 1 s hold switches back.
- Brightness moved off F-tap to avoid colliding with the F + Vol combo.

## Implementation

- Vibration requests from other programs: creating `$XDG_RUNTIME_DIR/rg35xxh-haptic-request` makes the daemon play its standard buzz (checked every 0.1 s; used by `rg35xxh-lowbattery`). The motor keeps a single owner.
- Signals: `SIGUSR1` re-centres the sticks (Re-center sticks app), `SIGUSR2` switches to an external controller mode (External Controller app, see [../apps/external-controller.md](../apps/external-controller.md)): gamepad mapping, events sent to `/run/rg35xxh-extpad.sock` (BT, USB or Switch service, whichever runs; it introduces itself with `hello bt` / `hello usb` / `hello switch` / `hello switch-bt`) instead of the local virtual pad; vibration comes back from the Xbox BT, USB and Switch BT services. Mode flags `rg35xxh-bt-mode` (also Switch over Bluetooth) / `rg35xxh-wired-mode` (also Switch over USB).
- Mode-change feedback (`_mode_feedback` in `daemon.py`): the taskbar icon shakes and the motor wobbles with it, both driven by the daemon on one clock from one damped spring, x(t) = A·e^(−3.85 t)·sin(2π·8.33 t). Every 60 ms (half a period) the old mode's icon is shown at the next swing peak (drawing offset 2, −2, 1, −1, 1, −1 px; frame file `$XDG_RUNTIME_DIR/rg35xxh-inputmode-frame` + `SIGRTMIN+8` to Waybar), and the motor gives a 40 ms pulse whose strength follows the spring's decaying envelope (93 % → 57 %), delayed ~70 ms to match Waybar's redraw; then the new icon appears (~360 ms). The motor is an ERM on one PWM line (`rocknix-singleadc-joypad`, 1 kHz; strength = duty cycle; no braking), so the pulses blur into a decaying wobble. Scale or disable with `haptic_strength` (0–1) in `[settings]`. Shutdown and re-centre keep the long 450 ms buzz.
- Pointer hidden outside desktop mode: labwc has no "hide cursor" action, but it hides the pointer after touch input until the next real pointer motion. On entering gamepad or BT Controller mode the daemon shows a 2x2 px transparent overlay window at the top-left corner, creates a short-lived virtual touchscreen, taps once on that window (so the tap reaches nothing else; tapping the taskbar border opened tray icons), then removes both. The pointer is warped there and hidden, and shows again as soon as it is moved in desktop mode (or by a real mouse).
- Mode flags in `$XDG_RUNTIME_DIR`: `rg35xxh-gamepad-mode`, `rg35xxh-bt-mode` (read by autosleep and the taskbar input-mode icon: Waybar `image#inputmode` runs `rg35xxh-inputmode`, which prints the icon path from `/usr/local/share/rg35xxh/icons/`; refreshed with `SIGRTMIN+8`).

- Daemon `rg35xxh-inputd` runs inside the labwc session as the desktop user (restarted automatically if it exits); log: `~/.local/state/session/inputd.log`.
- Access: user is in group `input`; udev rule gives that group `/dev/uinput` and the red status LED.
- Gamepad mode presents **"Microsoft X-Box 360 pad"** (045e:028e) so SDL/Moonlight use the standard Xbox mapping. Mapping by position: bottom (B) → A, right (A) → B, left (Y) → X, top (X) → Y; L2/R2 → full-scale triggers; D-pad → hat.
- Sleep (power menu or 10 min idle): tap Power to wake; see [../apps/power-menu.md](../apps/power-menu.md).
- Power held 1–3 s and released: cancelled (no menu, no shutdown).
- Copy/paste: Ctrl+Shift+C/V when the active window is a terminal (foot, xterm, …), else Ctrl+C/V.
- On-screen keyboard: US layout, 5 rows (`~ 1–0 ⌫ / Tab q–p - / a–l ; ' \ / ⇧ z–m , . / ↑ / Ctrl Alt Space = [ ] ← ↓ → Hide`). Physical L1/R1/R2 still give Esc/Enter/Backspace while it is open.
- Config (`input.conf`): `[settings]` speeds, dead zone, scroll curve (`scroll_log_k`), Vol repeat timing, hold times; `[desktop]` button actions (`none, click_left/right/middle, key:KEY_*, copy, paste, osk_toggle, mode_gamepad, power_menu`); `[hardware]` axis inversion. The boot-partition copy overrides `/etc/rg35xxh/input.conf` completely, so it must be refreshed when defaults change.

## Stopping, restarting, one instance

The daemon owns the vibration motor, and the motor's kernel driver (`rocknix-singleadc-joypad`, ff-memless + PWM work) can lock up the **whole handheld**, not just the daemon. So how the daemon stops matters as much as what it does while running.

- **Clean exit:** `SIGTERM` / `SIGINT` / `SIGHUP` (and any error) end the main loop, then `cleanup()` in `daemon.py` releases everything itself, one step at a time: external controller closed (PC vibration levels stopped and erased), then `_release_effects()` (motor timers off, every effect on the gamepad, Handtop's, the PC's and the games', stopped and then erased; also used by the stick re-centre), virtual pad removed, ungrab and close every device, close the virtual mouse/keyboard, clear the mode flags. The log ends with `clean exit: gamepad, vibration and virtual devices released`.
- **Watchdog:** the daemon grabs every button, the power key included, so logind's "hold to power off" never sees it; a hung daemon would leave only the power chip's forced cut. The wrapper `rg35xxh-inputd` (a shell script that starts the Python daemon) watches a counter that the daemon's main loop writes to `$XDG_RUNTIME_DIR/rg35xxh-inputd.alive` every second. If it stops changing for 3 checks in a row (at least 6 s awake: a counter, not a timestamp, so sleep is not mistaken for a hang), the wrapper sends `SIGTERM`, kills the daemon after 3 s, and shows "Controls restarted"; the session starts a new one. The file exists only while the main loop runs, not during start-up or the clean exit. Tested: a daemon frozen with `SIGSTOP` was replaced after ~10 s; an auto-sleep and wake caused no restart.
- **Stopped during start-up:** `SIGTERM`/`SIGINT`/`SIGHUP` during start-up also run `cleanup()`, which copes with a half-built daemon (devices already grabbed, effects uploaded). Before the lock is taken (while Python is still loading), the default action applies: nothing is held yet.
- **One instance:** the daemon takes a lock (`$XDG_RUNTIME_DIR/rg35xxh-inputd.lock`, `flock`) before opening any device. A second daemon waits up to 10 s for the first to be gone, then refuses to start (the session's restart loop tries again 2 s later). The kernel drops the lock only when the holder's process has ended, so two daemons never hold the gamepad at the same time.
- **No display connection in the daemon:** GDK ends a process with `_exit()` the moment its Wayland display goes away (every log-out: `Gdk-Message: Error reading events from display: Broken pipe`), which would skip `cleanup()`. So everything that needs GTK, the on-screen keyboard and the pointer-hiding touch target, runs in a child process, `rg35xxh_inputd.ui` (`ui.py`), driven over its stdin/stdout (one JSON array per line). The daemon restarts it if it ends (2 s, doubling up to 60 s), and it exits by itself when its stdin closes, however the daemon ended. At a log-out the UI process dies with the display; the daemon keeps running until the next session stops it cleanly.
- **Main loop:** a plain `GLib.MainLoop` in both processes. Quitting PyGObject's `Gtk.main()` from a signal handler deadlocks (7 of 8 tries on the device); the daemon then hangs with every device still grabbed, so all input is dead.
- **At log-out** the next session's autostart sends `SIGTERM` to the previous session's process group and waits until it is gone (up to 5 s, then `SIGKILL`) before starting the new daemon; see [../desktop.md](../desktop.md#session-start-and-log-out).

### Rules for changes

The general rules and checklist are in [../hardware-safety.md](../hardware-safety.md); for this daemon in particular:

1. Anything that stops or restarts the daemon (session scripts, apps, services) sends `SIGTERM` and **waits for the process to end** before starting another one. Never start a new daemon while the old one may still be running, and never `SIGKILL` it as the first step.
2. New resources the daemon opens (devices, effects, uinput nodes, sockets) are released in `cleanup()` too, motor first.
3. No GTK, GDK or other display connection in `daemon.py`: anything on screen goes into `ui.py` behind a message. No `Gtk.main()` / `Gtk.main_quit()` anywhere; quit with `self._quit()` / `loop.quit()`.
4. Test a change to the stop or start path on the device by hand first: stop the daemon several times with `kill -TERM`, check that each stop logs the "released" line and that a new daemon starts, and only then test a real log-out. Run `sync` before any test that may freeze the device.

### Incident: freeze at log-out (2026-10-26)

A session change made each new autostart stop the previous session's process group, which includes the input daemon, with `kill -TERM`. At that time the daemon had no handler for `SIGTERM`, so it died at once and the kernel tore down its vibration effects and grabs, while the new session's daemon was already grabbing the same gamepad and uploading its own effects. Logging out froze the whole handheld: input, Wi-Fi and SSH all stopped. After a forced power-off the power chip stayed latched (solid red LED, no backlight, no boot even from a freshly flashed card) until the battery was disconnected ([../flashing.md](../flashing.md#if-something-is-wrong)). The logs were lost when the card was re-flashed, so the cause is inferred, not proven: it matches the driver's earlier lock-ups (see `MOTOR_INTERVAL` in `daemon.py`). While fixing it, two more problems were found: the deadlock in `Gtk.main()` (even a correct `SIGTERM` handler could not have made the daemon exit), and GDK ending the daemon at every log-out once the on-screen keyboard had been used (no clean exit even with the handler). The fixes are the clean exit, the lock, the waiting autostart and the separate display process above. Verified with a log-out after using the keyboard: the UI process ended with the display, the daemon logged `SIGTERM: clean exit` and `released` 1.5 s later, and only then did the new daemon start.

## Stick re-centring

`SIGUSR1` makes the daemon reopen the stick device and re-measure the centre; see [../apps/recenter-sticks.md](../apps/recenter-sticks.md).
