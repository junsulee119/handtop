# RG35XX H regression list

What an RG35XX H must keep doing while shared code changes for other models. Run it when a change on the `device-support` branch touches shared code (anything outside a single model's profile and its model-only checks), and in full before the branch is merged into `main` or released. Write down the image (commit, DDR4 / DDR3) and the results in the PR.

The reference is **v0.4.1** (`93ea1bc`, 2026-11-18): everything below worked there.

## Without the device

- [ ] `tools/ci-checks.sh` passes (shell syntax, shellcheck errors, py_compile, input daemon and External Controller tests).
- [ ] **Image diff:** the RG35XX H image built from the branch has the same files, modes and contents as one built from `main` at the same base, except the model ID and files the change meant to touch. Every other difference is explained in the PR. (The diff tool is part of phase P2; until it exists, compare file lists and checksums of both root filesystems by hand.)
- [ ] Boot partition: `dtb.img` = `dtb-regular.img`, `dtb-rev6.img` and `dtb-rocknix.img` present, `extlinux.conf` unchanged, `panel.txt` / `wifi.txt` / input rescue file unchanged.
- [ ] Headless screenshots (`tools/headless-test.sh`, `tools/waybar-test.sh`, `tools/osk-test.sh`) at 640×480 match the reference in all nine themes.

## On the device (DDR4; DDR3 when boot, bootloader or memory is touched)

**Boot and screen**
- [ ] Fresh flash, first boot: desktop comes up, no failed units (`systemctl --failed`), `logs/boot-NNNN.txt` written.
- [ ] Panel check: the boot after flashing says "matches"; `panel.txt` = `rev6` switches and restarts once, back to `auto` switches back ([docs/services/panel.md](../../docs/services/panel.md)).
- [ ] Charger plugged into a switched-off unit keeps it off and charging.

**Controls**
- [ ] Every button and both sticks in desktop mode, with the default mapping ([docs/services/input-daemon.md](../../docs/services/input-daemon.md)): pointer, scroll, clicks and drag, Esc / Enter / Backspace, copy / paste, on-screen keyboard (open, type, close).
- [ ] Gamepad mode: Start tap in, Start hold out; all buttons and axes pass through (`evtest` on the virtual pad).
- [ ] Vol and F + Vol (volume and brightness bars), Power tap (power menu), Power hold 3 s (vibration, clean shutdown).
- [ ] Controls app: change a button, the trial countdown, a profile switching by itself with an app.
- [ ] Input daemon stop / start by hand 3 times (`kill -TERM`; log ends with the "released" line, a new daemon starts), then a log-out.

**Desktop and apps**
- [ ] Taskbar, app drawer, power menu and every app open and fit the screen in all nine themes (spot-check on the device; full check headless).
- [ ] Files, Videos (play, resume), Music (play, screen off with music), Image Viewer (thumbnails), Theme app (switch theme), Display app.

**Connections**
- [ ] Wi-Fi connects, SSH works after Enable SSH.
- [ ] Bluetooth: a classic mouse or keyboard, a Bluetooth LE mouse.
- [ ] Audio: speaker and headphones.
- [ ] HDMI: plug in and out; layout, on-screen keyboard and status screens on the right output.
- [ ] USB host port: keyboard or hub on the left port.

**Video**
- [ ] `tools/check-video-decode.sh` with an H.264 and an HEVC file; a video plays in Videos and in Chromium.

**External Controller** (each: start, use, end with Select + Start + L1 + R1, back to desktop)
- [ ] Bluetooth Xbox, USB Xbox 360, USB Switch, Bluetooth Switch; vibration from the PC in one of them.

**Motor**
- [ ] `tools/motor-stress.py random 300` (with `sync` first, as its warning says).

**Power**
- [ ] Sleep and wake from the power menu, auto-sleep, Screen off and back, Battery saver on and off.
- [ ] Restart and shut down from the power menu.

## Not on this list

Anything the change does not touch can be skipped for an ordinary PR, but say which sections were skipped and why. Before a release, the whole list runs.
