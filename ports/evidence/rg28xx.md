# RG28XX

Evidence for the Handtop profile of this model (phase P1). Nothing here is built or tested yet.

## Sources

- ROCKNIX **20261001** H700 image (the one Handtop builds from, checksum in `build/config.sh`): device tree `sun50i-h700-anbernic-rg28xx.dtb` and its panel firmware; summarised in [h700-20261001-facts.json](h700-20261001-facts.json) by `ports/tools/dt-facts.py`.
- ROCKNIX H700 installation guide ([rocknix.org](https://rocknix.org/configure/h700-installation/)).
- ROCKNIX device page ([rocknix.org](https://rocknix.org/devices/anbernic/rg28xx/)) (not read for this page).

## From the device tree

| Item | Value |
|---|---|
| `rg28xx` panel | `anbernic,rg28xx-panel`: 480×640 (rotated 270°), 44×58 mm |
| Gamepad | `rocknix-singleadc-joypad`, name "H700 Gamepad", 17 button codes (same set as the RG35XX H) |
| Stick axes | 0 (`amux-count`); inverted: absx, absy |
| Motor | PWM channel 2 |
| Other keys | Key Volume Up, Key Volume Down |
| LEDs | power, status |
| Wi-Fi / Bluetooth | RTL8821CS (SDIO Wi-Fi, UART Bluetooth) |
| HDMI | enabled |
| USB | `usb@5100000`, `usb@5101000`, `usb@5101400` (OTG controller only) |
| RTC | allwinner,sun50i-h616-rtc, nxp,pcf8563 |

## Notes

- Panel is **480×640 mounted sideways**: `rotation = 270` in the device tree (`rg28xx-panel`, 44×58 mm), so the desktop sees 640×480 only if the compositor rotates it.
- No sticks.
- The device tree does list Wi-Fi and Bluetooth (RTL8821CS) like the others.
- Stock U-Boot (RG28XX V1.1.3): reads **no panel pin**: one panel ([stock-firmware.md](stock-firmware.md)).

## Not confirmed

- Whether the unit really has Wi-Fi: the earlier plan said "no built-in Wi-Fi"; the 20261001 device tree has the nodes. Check ROCKNIX's device page and hardware.
- How labwc and the boot screen handle the rotation.
- USB keyboards and hubs: only the OTG (charging) port is enabled, so they need it in host mode; untested in Handtop (see [h700.md](h700.md#usb)).
- RAM type per batch: not confirmed.
