# Handtop changelog

## Unreleased

- **Bluetooth Xbox mode: "better compatibility" option.** Some PC Bluetooth adapters (especially cheap clone dongles) won't pair with the handheld's Bluetooth LE Xbox mode even though they work with other controllers. Turn on **Xbox: better compatibility** in the app's Bluetooth card and the handheld becomes an Xbox One S controller over classic Bluetooth instead (pair it again on the PC). Tested with an iPhone so far.
- **Battery saver for External Controller.** A switch in the app (off by default): the handheld's screen turns off 30 s after the other device connects, and the status screen draws much less. Vol+/- or Power shows the screen for 10 s; it also comes back if the connection drops. Measured: about half the CPU use in Bluetooth modes (70 % → 33 % of 4 cores in Xbox mode), plus the display and backlight off.
- **Clearer names on the PC / Switch:** the handheld now shows up as **"Handtop (Xbox)"** (Bluetooth and USB Xbox modes) or **"Handtop (Switch)"** (USB Switch mode); Bluetooth Switch mode has to be called "Pro Controller". Windows keeps showing the old "Handtop Gamepad" for an existing Bluetooth pairing until you remove and pair it again (it works either way).
- **Bluetooth LE mice and keyboards work.** Most current Bluetooth mice and keyboards (and many gamepads) use Bluetooth LE; they paired and connected but did nothing, because ROCKNIX's kernel lacks the driver BlueZ needs for them (uhid). Handtop now adds it.
- **Fixed: the handheld could freeze with the motor buzzing** when a game's vibration kept changing strength (Bluetooth, USB and gamepad mode alike). The cause was a locking bug in ROCKNIX's gamepad driver; Handtop now ships a fixed build of it. Details in `docs/kernel.md`, which also lists every kernel-level difference from ROCKNIX.
- **Switch Controller mode over Bluetooth (experimental).** Apps → External Controller → **Bluetooth: Switch**: the handheld pairs with a Switch as a Pro Controller (Controllers → Change Grip/Order the first time; afterwards it reconnects by itself). Same controls as the USB version (F = Home, F + Select = Capture), and vibration works. While it is on, Bluetooth runs as a Pro Controller: devices connected to the handheld disconnect (the app lists them and asks first), and classic Bluetooth keyboards, mice and controllers stay off until the mode ends. Tested with a PC (Ryujinx), not on a real Switch yet: please report.
- **Switch Controller mode.** Apps → External Controller → **USB cable: Switch** turns the handheld into a wired Nintendo Switch controller. It poses as HORI's licensed wired pad, so the Switch takes it with no setup: connect the right USB-C port to the dock's USB-A port (A-to-C cable), or without the dock through a USB-C OTG adapter. The printed A/B/X/Y match the Switch's; **F = Home** (hold for quick settings), **F + Select = Capture**. No vibration (that pad type has none). On a PC it is a normal gamepad that Steam and emulators like Ryujinx recognise (in Ryujinx pick Pro Controller and rebind A/B/X/Y once). Tested with Ryujinx, not on a real Switch yet: please report how it goes.
- External Controller keeps its two cards; both are split in two, each half with its own icon: **Xbox** (as before) and **Switch**. Its icons now follow the light theme too.
- **Newer screen panel (rev6) works without copying files.** RG35XX H units come with one of two screens, and the newer one showed garbled lines or stayed black until you copied its device tree over `dtb.img` by hand. The handheld now reads which screen it has from the board at every start (the same pin Anbernic's own firmware checks), uses the matching device tree and restarts once if it had to switch. A card moved to a unit with the other screen fixes itself the same way. If it ever picks wrong, write `rev6` or `regular` in `panel.txt` on the boot partition. What it did is in `logs\panel.txt`.
- The rev6 device tree now has hardware video decoding too (copying ROCKNIX's file by hand, as the v0.3.0 notes said, left it out).

## v0.3.0

- ⚠️ **Known issue:** Bluetooth is sometimes missing on the first boot after flashing (no adapter: the Bluetooth icon shows it off and External Controller → Bluetooth can't start). Restart once (Power → Restart); it works from then on.
- **BT Controller mode is now an Xbox controller.** Over Bluetooth the handheld presents itself as an Xbox Wireless Controller (Series X|S, BLE): Windows loads its own Xbox driver, XInput-only games work directly, and **game vibration now works over Bluetooth** too (played on the handheld's motor through the vibration safety gate). Tested on Windows 11. **After updating, remove "Handtop Gamepad" on the PC and pair it again once** (Windows caches the old description). For this, bluetoothd runs with the Xbox controller's device ID while the mode is on and gets its own back afterwards. The v0.2.0 generic gamepad stays available (`RG35XXH_BTPAD_PROFILE=generic`). Details in `docs/apps/external-controller.md`.
- External Controller app waits a little longer for BT mode to start (bluetoothd restarts).
- **Display app** (Apps → Display) replaces the three "Display: …" entries. It **opens by itself when a monitor is plugged in**, on the handheld (the monitor stays dark meanwhile so the pointer can't get lost on it): pick Monitor only / Extend / Mirror, or leave it for 5 s (restarted by any input) to keep the last layout. Pixel-art pictures of each layout, dark/light theme, its own app icon (monitor + HDMI cable + RG35XX H).
- **Resolution and refresh rate** in the Display app: full lists of the monitor's modes, **Test** with a 15 s "Keep this mode?" that switches back by itself, remembered per monitor. Verified: 1080p at 240 Hz works (real 570 MHz signal).
- **Extend** puts the handheld **below** the monitor (centred) instead of to its right.
- **Pointer speed follows the screen:** on a monitor the stick / D-pad pointer moves faster in proportion to its size (1080p ≈ 2.75×; `display_speed_scale`, 0 = off). The handheld's pointer no longer gets libinput acceleration, so its speed is exactly what `input.conf` says.
- D-pad pointer speed is now **half of the stick's** top speed (`dpad_speed_ratio = 0.5`, 225 px/s; it was a fixed 286 px/s) and follows `pointer_max_speed`. An older `dpad_speed` (px/s) in your own config is still understood.
- **Log out cleans up the previous session safely.** In v0.2.0 a log-out left the old session's helpers running (a second input daemon, a second Tailscale icon). Stopping them is new, and its first version froze the whole handheld during development (never released): the old input daemon, which owns the gamepad and vibration motor, was killed while the new one took over. Now there is one daemon at a time, it releases the hardware cleanly on every stop, the next session waits for it, and its on-screen keyboard runs in a separate process so a log-out can't cut it short. If a handheld ever shows only a solid red LED and won't boot, see `docs/flashing.md`.
- **"Controls restarted":** if the input daemon ever stops responding, it is restarted within about 10 s (before, every button including Power stayed dead).
- **Safety review of everything that touches hardware** (`docs/hardware-safety.md`, plus `AGENTS.md` for contributors). Fixes from it: Re-center sticks and leaving gamepad mode stop vibration before releasing it; a failed Wired Controller start no longer leaves the USB port set up; switching from BT Controller to USB cable (or shutting down) while the Bluetooth mode is on no longer hangs for 90 s; External Controller says so if the input daemon isn't running.
- **Screen off** (from a terminal, `rg35xxh-screen-off`) never auto-sleeps any more, so SSH and downloads keep running. At 20 % battery (not charging) the screen comes back on with a warning that stays until tapped and a vibration; at 5 % it shuts down cleanly.
- **Hardware video decoding in mpv and FFmpeg** (H.264, HEVC, MPEG-2, VP8 on the Cedrus VPU, zero-copy) through a V4L2 request-API FFmpeg build (PR #3). Details: `docs/video-decode.md`.
- **Click-to-mount** for the TF2 card and USB sticks in Files (no password), with "inserted" / "removed" toasts; tapping "inserted" opens Files. Eject on SD cards works.
- **BT Controller mode:** no more stick lag on Windows (shorter Bluetooth interval, reports paced); survives a Bluetooth soft block.
- **New look:**
  - Handtop logo, carved logo wallpapers (dark / light), and an animated boot screen: the logo's keyboard types while the live boot log scrolls beside it.
  - Pixel-art mouse cursor (dark-outlined, Adwaita for the rest); applies after logging out and back in.
  - Power menu: pixel-art icons, order Sleep, Restart / Log out, Shut down. Taskbar: Apps button with a 3x3 grid, red power button, even spacing.
  - Default apps renamed with pixel-art icons: Terminal, File Manager, Text Editor, Web Browser, System Monitor, Code Editor, PDF Viewer, Archive Manager (also in window title bars).
  - Wi-Fi and Bluetooth tray icons in pixel art; terminal colours softened to Handtop's palette; the BT / wired input-mode icons got a dark outline.
  - The External Controller status screen follows the theme: solid in dark, hologram in light.
- **On-screen keyboard:** laid out like a real keyboard (staggered rows, Enter and Backspace in their usual places, ↑ above ↓), light theme, a press trace on every typed key, hold A to repeat, L2 = Shift while it is open, badges for the shoulder buttons' keys. It now stays on top of the Apps screen (covering its bottom rows).
- **Volume / brightness bar** rewritten as a small native program (pixel-font level, vertical at the left edge).
- **Bluetooth taskbar icon** without blueman's tray applet (~55 MB less memory): tap for Bluetooth Manager; Bluetooth off is remembered across reboots.
- The Tailscale tray icon no longer goes missing after some boots.

## v0.2.0

- **BT Controller mode** (requested on Reddit by boldiatti): Apps → External Controller turns the handheld into a Bluetooth LE gamepad ("Handtop Gamepad") for a PC or phone; paired devices reconnect automatically; Select + Start + L1 + R1 stops it (Moonlight's quit combo; a long Start press goes to the other device). Classic-Bluetooth accessories on the handheld pause while it is on. Tested with Windows 11. See `docs/apps/external-controller.md`.
- **Status screen** while BT Controller mode is on: connection state and the PC's name, a live pixel-art drawing of the handheld's controls, reports/s and signal strength, battery, how to stop.
- **Taskbar battery icon**: 20x11 pixel art with 5 bars (one per 20 %), red bars at 0-20 %, and a charging animation with a lightning bolt (the "+" after the percentage is gone). Also on the BT Controller status screen. Light variants follow the theme.
- **Light theme** (Apps → Theme, or `rg35xxh-theme dark|light`): dark (default) or light, switched live: taskbar and its icons, wallpaper colour, app drawer (with light app icons), power menu, notifications, window title bars and GTK apps. Terminal, volume/brightness bars, on-screen keyboard and the External Controller status screen stay dark for now. New `rg35xxh-themed` starts Waybar/mako/swaybg in the current theme; window decorations moved to a labwc theme, `Handtop` (`/usr/share/themes/Handtop[-Light]`).
- App drawer: the 4th column no longer runs past the right edge of the screen.
- The mouse pointer is hidden in gamepad and BT Controller modes (it comes back when moved in desktop mode).
- **Wired Controller mode** (Apps → External Controller → USB cable): the handheld becomes a wired Xbox 360 controller for a PC (XInput, ~1000 reports/s, game vibration on the handheld's motor, charges meanwhile). Right USB-C port (OTG2/DC) only; one external connection at a time. New kernel module `usb_f_fs_xinput.ko` (build/06c-ffs-xinput.sh).
- External Controller app (was BT Controller): choose Bluetooth or USB cable. New pixel-art app icon; the Theme app's icon is redrawn the same way (both exactly 56 px, the drawer's icon size).
- **Vibration safety:** the handheld's motor driver could freeze the whole system when given never-ending vibration effects (e.g. "infinite" on a web controller tester), forcing a 10 s power-off. The input daemon now only plays timed effects (0.5 s, refreshed every 0.4 s while still wanted), rounds strength to 8 levels and updates the motor at most 10 times a second; game vibration in gamepad mode goes through the same path. Stress-tested at 100 requests/s.
- External Controller app: if the chosen service fails to start, it says so instead of switching modes and opening the status screen.
- BT Controller mode is its own input mode: the controls go only to the other device; apps on the handheld don't see a controller (unlike gamepad mode).
- **Taskbar input-mode icon** (pixel art, 23 px): desktop (mouse), gamepad, BT Controller and Wired Controller (an RG35XX H drawing with coloured X/A/B/Y, plus BT waves or a USB plug). External modes have rainbow-striped glass. On a mode change the old icon shakes like a damped spring before the new one appears, and the handheld vibrates in step with it (`haptic_strength` in the input config; 0 turns the vibration off). Light-taskbar variants: put `light` in `~/.config/rg35xxh/inputmode-icons`. Taskbar height 30 → 32 px so the icon sits exactly centred.
- Notifications now appear above the power menu and fullscreen apps. Fix: mako never read `/etc/xdg/mako/config` (it was started without `-c`), so Handtop's notification style was not applied either; it is now (a `~/.config/mako/config` still takes precedence).
- Input daemon: `SIGUSR2` switches to BT Controller mode (used by the External Controller app).
- Adds `python3-dbus`.

## v0.1.3

- **Browser: Chromium replaces Firefox.** On-device tests: Chromium with uBlock Origin Lite scrolled smoothest (4/3 vs Firefox's 2/1 on Wikipedia/Naver) at less than half the CPU, with ~200 MB more free RAM. uBlock Origin Lite is installed automatically by policy on first launch (needs internet). Details in `docs/desktop.md`.
- `/tmp` raised from 128 MB to 256 MB (it filled up during heavy browsing, which also broke `apt update`). It only uses RAM when filled.

## v0.1.2

- **DDR3 boards:** RG35XX H units with DDR3 RAM (dead on power-on with the standard image) now have their own image, `…-DDR3.img.xz`; build with `RAM_TYPE=DDR3`. Thanks @Aaronhrndz (#1). Charging while off is not confirmed on DDR3 yet.
- **On-screen keyboard:** typing follows whichever button is bound to `click_left`, so remapped layouts (e.g. B to confirm) work on the keyboard too. Thanks @Aaronhrndz (#2).
- Docs updated for both.

## v0.1.1

- Fix: Wi-Fi could stop passing traffic while still shown as connected (Realtek rtw88 driver stall with Wi-Fi power save on). Power save is now off during normal use (`/etc/NetworkManager/conf.d/50-rg35xxh-wifi-powersave.conf`); screen-off mode still turns it on and now turns it back off afterwards. Side effect: steadier Wi-Fi latency.
- Build: the Go toolchain download is pinned and SHA-256 checked, for x86_64 and arm64 build hosts.
- README: device photo.

## v0.1.0 — first public release

- ROCKNIX `20261001` hardware layer (kernel 7.2.0) + Debian 13 trixie + labwc desktop
- Input daemon: desktop mode (pointer, clicks, scroll, keys, copy/paste), gamepad mode (Xbox 360 pad), on-screen keyboard, volume/brightness with on-screen bars, power button (menu / 3 s shutdown), stick re-centring
- Moonlight with Cedrus hardware decoding (H.264/HEVC, 1080p60)
- Tailscale with tray icon and QR login
- HDMI hot-plug with monitor-only / extend / mirror modes
- Sleep (s2idle) and auto-sleep; charging while off
- `wifi.txt` import from the boot partition; boot logs on the boot partition
- Firefox ESR with low-RAM settings and uBlock Origin; zram + 2 GB swap file
- SSH off by default; Apps → Enable SSH sets your own password first
