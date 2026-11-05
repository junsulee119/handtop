# Power menu and sleep

Power button, the power menu (`rg35xxh-power-menu`, wlogout: Sleep / Restart / Shut down / Battery saver / Log out), sleep (`rg35xxh-sleep`), auto-sleep (`rg35xxh-autosleep`), low battery (`rg35xxh-lowbattery`) and Battery saver (`rg35xxh-battery-saver`).

## Power button

| Action | Result |
|---|---|
| Tap | Power menu: Sleep, Restart, Shut down / Battery saver, Log out (3 + 2 grid since v0.3.8, was 2×2; the button under the pointer is highlighted. GTK puts keyboard focus on Sleep when the menu opens and the D-pad moves the pointer, not that focus, so focus is only a thin outline, drawn after a USB keyboard's arrow or Tab key; until v0.3.6 it was styled like hover and Sleep stayed lit next to the hovered button). Pixel-art icons, one colour per action (blue moon, amber arrow, grey door, red power symbol, green leaf; white on the highlighted button in the dark theme), `tools/icons/gen_power_icons.py` |
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
- Skipped while charging, in gamepad mode (controller input is invisible to the compositor; the input daemon writes `$XDG_RUNTIME_DIR/rg35xxh-gamepad-mode`), with HDMI connected, or in Screen off (see below). Video/streaming apps block idle themselves (Wayland idle-inhibit).
- **Dims first:** `AUTOSLEEP_DIM_SECONDS=10` (0 = off) before auto-sleep the screen dims to 30 % of its brightness (not below the 5 % floor of the brightness keys) as a warning; any input restores it, and so does waking from the sleep (`rg35xxh-dim`, swayidle `resume` / `after-resume`). It dims only when `rg35xxh-autosleep --check` says a sleep would follow, so never while charging, in gamepad or controller modes, with HDMI or in Screen off. A brightness change made while dimmed is kept (restore only if the value is still the dimmed one). The state is in `~/.local/state/session/dim`, so a log-out or crash while dimmed is undone by the next session's autostart. Known edge: if the charger or HDMI is connected during those 10 s without any input, the sleep is skipped and the screen stays dimmed until the next input. Idea from 2026-10-26, added in v0.3.7.
- Log: `~/.local/state/session/autosleep.log` (also the dim / restore lines).

**Low battery** (`rg35xxh-lowbattery --watch` in the labwc autostart, checks every 30 s, only when not charging), settings in `/etc/rg35xxh/power.conf`:

- `LOW_BATTERY_WARN_PCT=10`: a notification that stays until tapped, plus three of the input daemon's standard buzzes (the shutdown countdown and the Screen off warnings buzz three times too). Once per discharge; charging, or the level rising above it, re-arms it.
- `LOW_BATTERY_SHUTDOWN_PCT=5`: a notification and three buzzes, then a clean shutdown after a 3-minute countdown shown live in the notification (long enough to save work or find the charger; awake with the screen on it costs under 1 % of battery). Plugging in the charger during the countdown cancels it ("Charging: shutdown cancelled"). 0 turns either level off.
- Why: running flat cuts the power mid-write, which can leave the SD card's filesystem damaged. Why 5 % and not lower: the battery gauge near empty is unverified (it reads in coarse steps and `current_now` is a fixed value), so a lower level risks hitting the hardware cut-off before the shutdown finishes. Same level as Screen off's shutdown.
- Screen off keeps its own levels (below). While asleep nothing checks; the next check runs on wake. In a controller mode with Battery saver on, the screen is off, so only the buzz and the shutdown show.
- A typo in one of the levels falls back to that level's default (logged), so the watcher keeps running.
- Log: `~/.local/state/session/lowbattery.log`.

## Battery saver

One switch (`rg35xxh-battery-saver on|off|toggle|--get`), off by default, remembered across reboots (`~/.config/rg35xxh/battery-saver`). Two places to switch it:

- **Power menu:** the "Battery saver: On / Off" button (green leaf). `rg35xxh-power-menu` writes the layout to `$XDG_RUNTIME_DIR/rg35xxh-power-menu.layout` at every opening so the label shows the state; the button toggles and the menu closes like after any other button. Works over fullscreen apps, where the taskbar is hidden.
- **Taskbar:** tap the battery icon or the percentage (Waybar `on-click`). While the saver is on the battery's shell is green (`battery-…-saver[-light].png`, `tools/icons/gen_battery.py`) and the tooltip says so.

What it does:

- **CPU top speed capped at 1.008 GHz** (top 1.416 GHz): `rg35xxh-cpucap on|off` (root, `/etc/sudoers.d/rg35xxh-cpucap` allows exactly those two), which writes only `policy0/scaling_max_freq` and keeps the previous value in `/run/rg35xxh-cpucap`. One policy covers all four cores. No governor change (Screen off's `rg35xxh-lowpower` owns that; the two combine: in Screen off the powersave governor runs the lowest speed anyway), no voltages, nothing on the power chip.
- **Brightness halved** when it turns on, never below the 5 % floor of the brightness keys; F + Vol can still change it. Off puts the old level back unless it was changed meanwhile (same rule as the dim before auto-sleep). Half and not 30 %: 30 % is the dim before auto-sleep, and the saver turning on should not look like "about to sleep".
- **Session start** (`rg35xxh-battery-saver --apply`, labwc autostart): saver on → cap again; saver off → lift a cap a crashed or logged-out session left behind ([../hardware-safety.md](../hardware-safety.md) rule 6.2). A reboot always starts uncapped (`/run`).
- Not changed: Wi-Fi power save stays off ([../hardware.md](../hardware.md): with power save on the Wi-Fi chip could stall until a reboot), and controller / gamepad modes keep the cap if it is on (turn the saver off for heavy games or Moonlight if needed).
- **Gain unmeasured.** The battery's `current_now` reads a fixed ~394 mA, so there is no quick way to measure. Idle on the desktop the CPU already spends ~87 % of the time at 480 MHz and ~9 % at 1.416 GHz (30 s sample, 2026-11-05), so the cap mostly slows bursts (page loads, app starts); most of the gain is expected from the dimmer screen. A drain test (same workload, saver on / off in turns) would settle it.
- Tried and rejected: a full-width "Battery saver" strip above the four buttons, drawn by a separate Python GTK layer-shell window. Loading GTK in Python takes ~1 s on the H700, so the strip appeared a second after the menu; keeping it running hidden would cost ~28 MB of RAM. As two layer-shell surfaces the later-mapped one also wins, so the strip could end up hidden behind wlogout. A wlogout button opens with the menu at no cost.
- Log: `~/.local/state/session/battery-saver.log` (also the cap helper's lines).

Notes:

- The input daemon now opens the built-in devices by name (`H700 Gamepad`, `gpio-keys-volume`, `axp20x-pek`). It previously picked "any device with KEY_VOLUMEUP/KEY_POWER" and grabbed a USB keyboard receiver's media keys, which vanished on resume. If a grabbed device disappears, the daemon exits and the session restarts it.
- polkit: group `sudo` may also suspend from any session.
- The old "Screen off" low-power mode (`rg35xxh-screen-off` / `rg35xxh-lowpower`) is no longer in the menu; the scripts remain (from a terminal: `rg35xxh-screen-off`; any button turns the screen back on). Kept safe for that use and for a possible return to the menu (Jason's decision, 2026-10-26):
  - **No auto-sleep in Screen off.** Screen off exists to keep things running (Wi-Fi stays on so SSH and downloads survive); sleep would cut them. It also takes CPU cores 1–3 offline, and sleeping in that state was never tested (hardware review 2026-10-26, [../hardware-safety.md](../hardware-safety.md) rule 6).
  - **Low battery instead** (`rg35xxh-lowbattery --watch`, labwc autostart, checks every 30 s, not charging; in Screen off these levels replace the normal-use ones above): at **20 %** the screen comes back on, a notification stays until tapped and the handheld vibrates (once per discharge: going back to Screen off below 20 % does not warn again); at **5 %**, still in Screen off, a notification and a clean shutdown. Thresholds: `SCREEN_OFF_WARN_PCT`, `SCREEN_OFF_SHUTDOWN_PCT` in `power.conf`. The vibration is requested from the input daemon (`$XDG_RUNTIME_DIR/rg35xxh-haptic-request`), which owns the motor. Log: `~/.local/state/session/lowbattery.log`.
  - Trade-off (accepted): left in Screen off, the battery drains until the 20 % warning.
  - **Log-out or crash in Screen off:** the low-power state (`/run/rg35xxh-lowpower`) is system-wide and outlives the session; the screen-off flag is in `$XDG_RUNTIME_DIR`. The next session's autostart removes the flag and runs `rg35xxh-lowpower off` before it starts the input daemon (only when the state exists; nothing happens otherwise), so it never starts with the backlight off, cores 1–3 offline or the audio off (codebase audit 2026-10-30, M12; [../hardware-safety.md](../hardware-safety.md) rule 6.2). Log: `~/.local/state/session/lowpower.log`. Tested on the device (DDR4, 2026-11-02): Screen off on (1 core online, backlight off), labwc stopped; the new session came up with cores 0–3, backlight and DAC on, no state or flag left, and the old input daemon exited cleanly before the new one started.
