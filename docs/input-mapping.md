# Input Mapping

Implemented by a custom input daemon that grabs the "H700 Gamepad" exclusively and emits virtual mouse/keyboard (desktop mode) or a virtual Xbox-style controller (gamepad mode) via uinput.

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
| Select | — | Passed through |
| F (tap) | — | — |
| F + Vol+/− | Brightness | Brightness |
| Vol+/− | System volume | System volume |
| Power (tap) | Power menu | Power menu |
| Power (hold 3 s) | Vibration, then clean shutdown | Same |
| Power (hold ~8–10 s) | Hardware power cut by PMIC (not configurable) | Same |
| R (Reset) | Hardware reset (not mappable) | Same |

## Behaviour notes

- **Left stick:** dead zone against drift; power curve — slow/precise on small tilt, fast at the edge. Max 450 px/s (halved from 900 after device testing).
- **Right stick:** logarithmic curve (`log(1+9x)/log(10)`) — a small push already scrolls at a useful rate, levelling off at 8.4 notches/s at full tilt (0.7× of the original 12 after device testing).
- **D-pad pointer:** digital, fixed speed 286 px/s (raised 1.3× from 220 after device testing).
- **Vol / F + Vol held:** repeats after 0.4 s, then every 0.12 s (works in desktop and gamepad mode). A pop-up bar (wob) shows the level: blue for volume, amber for brightness. Brightness steps 10% and never goes below 5%.
- **On-screen keyboard:** custom, part of the input daemon, so the daemon always knows whether it is open. Left stick still moves the pointer while it is open.
- **Copy/paste:** daemon checks the focused app. Terminals get Ctrl+Shift+C / Ctrl+Shift+V; other apps Ctrl+C / Ctrl+V (Ctrl+C in a terminal would kill the running program). Bash bracketed paste must stay enabled so an accidental R3 paste cannot execute a command. Hold-to-paste can be added later if accidental stick clicks are a problem.
- **Gamepad mode:** virtual controller uses standard Xbox layout **by position** (bottom button = Xbox A). F is not forwarded (would open Xbox Game Bar on Windows). Rumble from Moonlight can be forwarded to the motor.
- **Start in gamepad mode:** short tap is sent to the PC as Start; only a 1 s hold switches back.
- Brightness moved off F-tap to avoid colliding with the F + Vol combo.

## Implementation

- Daemon `rg35xxh-inputd` runs inside the labwc session as the desktop user (restarted automatically if it exits); log: `~/.local/state/session/inputd.log`.
- Access: user is in group `input`; udev rule gives that group `/dev/uinput` and the red status LED.
- Gamepad mode presents **"Microsoft X-Box 360 pad"** (045e:028e) so SDL/Moonlight use the standard Xbox mapping. Mapping by position: bottom (B) → A, right (A) → B, left (Y) → X, top (X) → Y; L2/R2 → full-scale triggers; D-pad → hat.
- Sleep (power menu or 10 min idle): tap Power to wake; see `power-and-sleep.md`.
- Power held 1–3 s and released: cancelled (no menu, no shutdown).
- Copy/paste: Ctrl+Shift+C/V when the active window is a terminal (foot, xterm, …), else Ctrl+C/V.
- On-screen keyboard: US layout, 5 rows (`~ 1–0 ⌫ / Tab q–p - / a–l ; ' \ / ⇧ z–m , . / ↑ / Ctrl Alt Space = [ ] ← ↓ → Hide`); can also be clicked with the pointer. Physical L1/R1/R2 still give Esc/Enter/Backspace while it is open.
- Config (`input.conf`): `[settings]` speeds, dead zone, scroll curve (`scroll_log_k`), Vol repeat timing, hold times; `[desktop]` button actions (`none, click_left/right/middle, key:KEY_*, copy, paste, osk_toggle, mode_gamepad, power_menu`); `[hardware]` axis inversion. The boot-partition copy overrides `/etc/rg35xxh/input.conf` completely, so it must be refreshed when defaults change.

## Stick drift and re-centring (2026-10-16)

- **Cause:** the stick driver (`rocknix-singleadc-joypad`, from ROCKNIX) measures each axis' centre **once**, from a **single ADC reading**, when the device is first opened (`joypad_open()` → `adc->cal = adc->value`), and reports every later reading minus that value. If that one reading is off (bad first conversion right after the analog multiplexer switches, or the stick touched at that moment), the axis stays offset until the device is reopened. Seen once after flashing 20261001: left X centre ~1290/1800 off → cursor drifted left; a hands-off restart fixed it. The driver is unchanged between ROCKNIX 20260901 and 20261001 (one-line build fix only).
- **Fix: Apps → Re-center sticks** (`rg35xxh-recenter-sticks`). Shows "hands off" for 3 s, then sends `SIGUSR1` to the input daemon, which closes and reopens the stick device (it is the only user, so the driver measures the centre again), samples the axes for 0.5 s, applies a software correction to any axis still off-centre (> 8 % of travel, steady), buzzes and shows a notification. Log: `re-centre:` lines in `~/.local/state/session/inputd.log`.
- Verified on the device: holding the stick during the countdown created a drift; a hands-off run removed it.
