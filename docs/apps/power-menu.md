# Power menu and sleep

Power button, the power menu (`rg35xxh-power-menu`, wlogout: Shut down / Restart / Log out / Sleep), sleep (`rg35xxh-sleep`) and auto-sleep (`rg35xxh-autosleep`).

## Power button

| Action | Result |
|---|---|
| Tap | Power menu (shut down / restart / log out / sleep) |
| Hold 3 s | Clean shutdown (`systemctl poweroff`) with feedback, see below |
| Hold ~8–10 s | PMIC hardware power cut — last resort, not configurable, may corrupt the SD card |
| R (Reset) button | Instant hardware reset — not visible to Linux |

### Shutdown feedback (hold 3 s)

- At 3 s: one short strong **vibration**, then shutdown starts. Purpose: the user knows to let go and does not keep holding into the hardware power cut.
- Releasing before 3 s cancels.
- During shutdown: red status LED blinks and a "Shutting down…" message is shown.

The power button is the AXP717 `axp20x-pek` input device, read by the input daemon.

Power-off permission: polkit rule `/etc/polkit-1/rules.d/50-rg35xxh-power.rules` lets group `sudo` power off/reboot from any session. Without it, `systemctl poweroff` silently failed when the input daemon was not running inside the seat session (found on the device 2026-10-07).

## Sleep — verified 2026-10-09

**Light sleep (s2idle / "freeze") works.** The kernel offers only `s2idle` (`/sys/power/mem_sleep` = `[s2idle]`; the firmware has no PSCI deep suspend), so `systemctl suspend` = s2idle.

| | |
|---|---|
| Enter | Power tap → power menu → **Sleep** (`rg35xxh-sleep`), or **auto-sleep** after 10 min without input |
| Wake | **Tap Power** (`axp20x-pek` is a wake source; the wake press does not open the menu). RTC alarms also wake it. |
| Resume | Clean: display back, Wi-Fi reconnects in ~5 s, Bluetooth firmware reloads, USB devices re-enumerate (USB receivers reconnect), audio OK. |
| Battery | ~1 % per 10 min asleep (75 → 74 %, 3851 → 3835 mV over 10 min; coarse 1 % gauge steps) ≈ 5–6 %/h, ~15–20 h from full. Awake with the screen on draws ~0.41 A, roughly 2.5× more. |

**Auto-sleep** (`swayidle` in the labwc autostart → `rg35xxh-autosleep`), settings in `/etc/rg35xxh/power.conf`:

- `AUTOSLEEP_MINUTES=10` (0 = off), `AUTOSLEEP_ON_CHARGER=no`.
- Skipped while charging, in gamepad mode (controller input is invisible to the compositor; the input daemon writes `$XDG_RUNTIME_DIR/rg35xxh-gamepad-mode`), or with HDMI connected. Video/streaming apps block idle themselves (Wayland idle-inhibit).
- Log: `~/.local/state/session/autosleep.log`.

Notes:

- The input daemon now opens the built-in devices by name (`H700 Gamepad`, `gpio-keys-volume`, `axp20x-pek`). It previously picked "any device with KEY_VOLUMEUP/KEY_POWER" and grabbed a USB keyboard receiver's media keys, which vanished on resume. If a grabbed device disappears, the daemon exits and the session restarts it.
- polkit: group `sudo` may also suspend from any session.
- The old "Screen off" low-power mode (`rg35xxh-screen-off` / `rg35xxh-lowpower`) is no longer in the menu; the scripts remain.
