# Hardware Facts — Anbernic RG35XX H

Sources: decompiled `sun50i-h700-anbernic-rg35xx-h.dtb` from ROCKNIX 20260901, linux-sunxi wiki, ROCKNIX wiki.

## Specs

| Item | Value |
|---|---|
| SoC | Allwinner H700, 4× Cortex-A53 @ 1.5 GHz (H616 family) |
| GPU | Mali-G31, open-source Panfrost driver (GL/GLES 3.1) |
| RAM | 1 GB LPDDR4 |
| Screen | 3.5" 640×480 |
| Storage | 2× microSD (no internal storage; boots from TF1) |
| Wi-Fi / BT | Realtek RTL8821CS (rtw88), Bluetooth 4.2 |
| PMIC | X-Powers AXP717 (battery, USB power, power button) |
| Video out | mini HDMI — HDMI node enabled in device tree |
| USB | 1× USB-C OTG/power, 1× USB-C host only |
| Debug | UART header (between left SD slot and speaker); kernel console `ttyS0,115200` |
| Other | Vibration motor (PWM), power LED (green), status LED (red) |
| Battery | 3700 mAh |

## Device-tree findings that affect the design

- **No video-engine node** in the ROCKNIX DTB → we add it with an overlay and build the Cedrus driver ourselves; hardware decoding works (see `video-decode.md`). Upstream DT support lands in 7.4.
- **HDMI enabled** (`hdmi@6000000` okay); ROCKNIX's HDMI patch is merged upstream in 7.2.
- **USB:** OTG controller (`dr_mode = "otg"`) plus host controllers enabled. Keyboard/hub goes on the host port, charging on the other.
- **Sleep is disabled by ROCKNIX** on H700 ("Sleep is currently broken") — see [apps/power-menu.md](apps/power-menu.md).

## Input device

All buttons and sticks are one device: **"H700 Gamepad"** (driver `rocknix-singleadc-joypad`, vendor `0x484b`, product `0x14df`). Volume keys are a separate `gpio-keys` device.

| Physical control | Linux code |
|---|---|
| D-pad up/down/left/right | `BTN_DPAD_UP/DOWN/LEFT/RIGHT` |
| A (right) | `BTN_EAST` (verified on device) |
| B (bottom) | `BTN_SOUTH` (verified on device) |
| X (top) | `BTN_WEST` (verified with evtest; the device tree labels X/Y the other way round) |
| Y (left) | `BTN_NORTH` (verified with evtest) |
| L1 / R1 | `BTN_TL` / `BTN_TR` |
| L2 / R2 (digital) | `BTN_TL2` / `BTN_TR2` |
| L3 / R3 (stick clicks) | `BTN_THUMBL` / `BTN_THUMBR` |
| Select / Start | `BTN_SELECT` / `BTN_START` |
| F (top edge, "Menu") | `BTN_MODE` |
| Left stick / right stick | `ABS_X/ABS_Y` / `ABS_RX/ABS_RY` (left stick axes inverted in DT) |
| Vol+ / Vol− (left edge) | `KEY_VOLUMEUP` / `KEY_VOLUMEDOWN` |
| Power (right edge) | Via AXP717 — **not yet verified** as an input event |
| R / Reset (right edge, under Power) | Hardware reset — not visible to Linux, cannot be mapped |

Face-button layout is Nintendo-style (A right, B bottom, X top, Y left). Kernel codes do not follow the labels for X/Y; the input daemon maps by the verified codes.

## Wi-Fi power save (v0.1.1)

- The Wi-Fi chip (RTL8821CS, `rtw88_8821cs` driver over SDIO) could stall with power save on: the kernel logged `failed to get tx report from firmware` and from then on no traffic passed, while NetworkManager still showed the link as connected. Only a reboot recovered it.
- Power save is therefore **off** during normal use: `/etc/NetworkManager/conf.d/50-rg35xxh-wifi-powersave.conf` (`wifi.powersave = 2`). NetworkManager applies it on every connect, including after resume. Check with `/usr/sbin/iw dev wlan0 get power_save`.
- Screen-off mode (`rg35xxh-lowpower`, [apps/power-menu.md](apps/power-menu.md)) still turns power save on while the screen is off and turns it off again afterwards.
- Test (2026-10-16): 41 min awake after a sleep/wake, one ping per second from the LAN — 2463/2463 answered, median 1.6 ms, no driver errors. Before the fix the stall appeared about 6 minutes after a wake.
