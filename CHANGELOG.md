# Handtop changelog

## v0.2.0

- **BT Controller mode** (requested on Reddit by boldiatti): Apps → External Controller turns the handheld into a Bluetooth LE gamepad ("Handtop Gamepad") for a PC or phone; paired devices reconnect automatically; Select + Start + L1 + R1 stops it (Moonlight's quit combo; a long Start press goes to the other device). Classic-Bluetooth accessories on the handheld pause while it is on. Tested with Windows 11. See `docs/bt-controller.md`.
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
