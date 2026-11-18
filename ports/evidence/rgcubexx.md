# RG CubeXX

Evidence for the Handtop profile of this model (phase P1). Nothing here is built or tested yet.

## Sources

- ROCKNIX **20261001** H700 image (the one Handtop builds from, checksum in `build/config.sh`): device tree `sun50i-h700-anbernic-rgcubexx.dtb` and its panel firmware; summarised in [h700-20261001-facts.json](h700-20261001-facts.json) by `ports/tools/dt-facts.py`.
- ROCKNIX H700 installation guide ([rocknix.org](https://rocknix.org/configure/h700-installation/)).
- ROCKNIX device page ([rocknix.org](https://rocknix.org/devices/anbernic/rg-cubexx/)) (not read for this page).
- Anbernic: <https://anbernic.com/products/rg-cubexx>

## From the device tree

| Item | Value |
|---|---|
| `rgcubexx` panel | `anbernic,rgcubexx-panel`: 720×720, 71×71 mm |
| Gamepad | `rocknix-singleadc-joypad`, name "H700 Gamepad", 17 button codes (same set as the RG35XX H) |
| Stick axes | 4 (`amux-count`); inverted: absrx, absry, absx, absy |
| Motor | PWM channel 3 |
| Other keys | Key Volume Up, Key Volume Down |
| LEDs | power, status, kbd_backlight |
| Wi-Fi / Bluetooth | RTL8821CS (SDIO Wi-Fi, UART Bluetooth) |
| HDMI | enabled |
| USB | `usb@5100000`, `usb@5101000`, `usb@5101400` (OTG controller only) |
| RTC | allwinner,sun50i-h616-rtc, nxp,pcf8563 |

## Notes

- **720×720** square panel (`rgcubexx-panel`, 71×71 mm), panel supply 2.8 V (H: 3.3 V); needs the screen-size work of P3.
- Two sticks, right stick inverted in the device tree; RGB stick LEDs as on the RG40XX H.
- One device tree, no panel variant listed in the 20261001 image.
- A CubeXX owner offered to test (Reddit; earlier plan).
- Stock U-Boot (RGCUBEXX V1.0.7): reads **no panel pin**: one panel, matching ROCKNIX's single device tree ([stock-firmware.md](stock-firmware.md)).

## Not confirmed

- USB keyboards and hubs: only the OTG (charging) port is enabled, so they need it in host mode; untested in Handtop (see [h700.md](h700.md#usb)).
- RAM type per batch: not confirmed.
