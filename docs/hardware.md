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
- **USB:** OTG controller (`dr_mode = "otg"`) plus host controllers enabled. Keyboard/hub goes on the host port (left, OTG1: EHCI/OHCI, host only), charging on the other. The right port (OTG2/DC, MUSB) stays a device (`mode` = `b_idle`): its role comes from an ID GPIO (`usb0_id_det-gpios`), and a USB-C plug has no ID pin, so a hub there is never seen (checked 2026-10-29: a hub with keyboard and mouse works on the left port only). Forcing it to host would fight with charging on the same port; not done.
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

## Bluetooth at boot (v0.4.0)

- **The problem:** on some boots, mostly the first one after flashing (3 of the 5 first boots seen by 2026-11-05; no later boot so far), Bluetooth was missing: no `hci0`, no Bluetooth rfkill entry, `bluetoothd` running without an adapter. A restart fixed it.
- **Diagnosed on a failing first boot (2026-11-05, `bt-firstboot.sh`):** the RTL8821CS's UART (`ttyS1`) was bound to `hci_uart_h5` and the host had sent 21456 bytes of H5 sync, the chip had answered with 2. Its GPIOs were as on a good boot (enable high, reset released, device-wake high). So not rfkill and not power: the Bluetooth half of the chip stayed mute. One unbind + bind of the driver, which runs the chip's power-on sequence again, brought `hci0` up within ~1 s with the firmware loaded. Why the chip is mute on the first try is not known yet (suspected: the Wi-Fi half starting at the same moment; it is the same chip).
- **`rg35xxh-bt-check`** (boot service from early boot, [services/boot-services.md](services/boot-services.md)):
  - **Probe:** samples the UART byte counters, the chip's GPIO lines, the driver binding and `hci0` every 0.2 s from before the driver loads (~5 s) to ~30 s, and writes the changes plus the kernel's Bluetooth / Wi-Fi (`mmc1` SDIO) lines and the first-boot jobs to `logs/bt-NNNN.txt` on the boot partition (last 5 kept). Records of good and bad boots side by side are meant to find the cause.
  - **Recovery:** if the chip is mute — the driver has been bound for 3 s, the host has sent bytes, the chip has sent at most 16, no `hci0` — it unbinds and binds the driver **once**. Fallback, also once: no `hci0` 15 s after binding and the chip silent for 3 s. On a mute boot Bluetooth is then up at ~10 s, before the desktop (~11–12 s), so nothing shows; the record says "recovered". Never more than one rebind per boot: if it does not help, the record says "NOT recovered" and a restart stays the workaround.
  - Touches only the driver's `bind` / `unbind` files: no rfkill, no power chip, no `bluetoothd` restart (it picks up the new `hci0` by itself).
  - **Tested (2026-11-05, DDR4, v0.3.8 image):** forced rebind (`--force-rebind`) 10 times in a row while the build server pinged the handheld 5 times a second over Wi-Fi: `hci0` back 0.21 s after each bind, firmware loaded each time (~1.2 s), 1076 / 1076 pings answered, no gap over 0.6 s, no rtw88 errors ([hardware-safety.md](hardware-safety.md) rule 6.3). The automatic path still needs a real mute first boot to be seen working; until then the known-issue note stays in the README and [flashing.md](flashing.md).
