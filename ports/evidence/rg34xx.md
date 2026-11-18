# RG34XX

Evidence for the Handtop profile of this model (phase P1). Nothing here is built or tested yet.

## Sources

- ROCKNIX **20261001** H700 image (the one Handtop builds from, checksum in `build/config.sh`): device tree `sun50i-h700-anbernic-rg34xx.dtb` and its panel firmware; summarised in [h700-20261001-facts.json](h700-20261001-facts.json) by `ports/tools/dt-facts.py`.
- ROCKNIX H700 installation guide ([rocknix.org](https://rocknix.org/configure/h700-installation/)).
- ROCKNIX device page ([rocknix.org](https://rocknix.org/devices/anbernic/rg34xx/)) (not read for this page).

## From the device tree

| Item | Value |
|---|---|
| `rg34xx` panel | `anbernic,rg34xx-panel`: 720×480, 71×48 mm |
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

- **720×480** panel (`rg34xx-panel`, 71×48 mm, 3:2).
- No sticks.
- Stock U-Boot (RG34XX V1.0.6): reads **PE6 with the pull-up on**: high = `rg34xx-panel`, low = `rg34xx-sp-panel`. ROCKNIX ships only the first as an RG34XX device tree; Handtop can make the second by changing the panel `compatible` ([stock-firmware.md](stock-firmware.md)).

## Not confirmed

- The PE6 table comes from matching the stock init sequences with ROCKNIX's panel files; a unit with the second panel should confirm the low reading.
- USB keyboards and hubs: only the OTG (charging) port is enabled, so they need it in host mode; untested in Handtop (see [h700.md](h700.md#usb)).
- RAM type per batch: not confirmed.
