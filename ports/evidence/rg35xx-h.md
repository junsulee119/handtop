# RG35XX H

Evidence for the Handtop profile of this model (phase P1). Nothing here is built or tested yet.

## Sources

- ROCKNIX **20261001** H700 image (the one Handtop builds from, checksum in `build/config.sh`): device trees `sun50i-h700-anbernic-rg35xx-h.dtb`, `sun50i-h700-anbernic-rg35xx-h-rev6-panel.dtb` and its panel firmware; summarised in [h700-20261001-facts.json](h700-20261001-facts.json) by `ports/tools/dt-facts.py`.
- ROCKNIX H700 installation guide ([rocknix.org](https://rocknix.org/configure/h700-installation/)).
- ROCKNIX device page ([rocknix.org](https://rocknix.org/devices/anbernic/rg35xx-h/)) (not read for this page).

## From the device tree

| Item | Value |
|---|---|
| `rg35xx-h` panel | `anbernic,rg35xx-plus-panel`: 640×480, 70×53 mm |
| `rg35xx-h-rev6-panel` panel | `anbernic,rg35xx-plus-rev6-panel`: 640×480, 70×53 mm |
| Gamepad | `rocknix-singleadc-joypad`, name "H700 Gamepad", 17 button codes (same set as the RG35XX H) |
| Stick axes | 4 (`amux-count`); inverted: absx, absy |
| Motor | PWM channel 2 |
| Other keys | Key Volume Up, Key Volume Down |
| LEDs | power, status |
| Wi-Fi / Bluetooth | RTL8821CS (SDIO Wi-Fi, UART Bluetooth) |
| HDMI | enabled |
| USB | `usb@5100000`, `usb@5101000`, `usb@5101400`, `usb@5200000`, `usb@5200400` (OTG controller plus a separate host port) |
| RTC | allwinner,sun50i-h616-rtc, nxp,pcf8563 |

## Notes

- Current Handtop device and the regression baseline ([../testing/rg35xx-h-baseline.md](../testing/rg35xx-h-baseline.md)).
- Panel variant (regular / rev6) is detected at boot from pin PE6, a method read out of the stock U-Boot ([docs/services/panel.md](../../docs/services/panel.md)).
- Ships with DDR4 or DDR3 RAM; users who get no LED at all try the DDR3 image ([docs/flashing.md](../../docs/flashing.md)).
- Stock U-Boot (RG35XXH V1.2.4): reads **PE6 with the pull-up on**; low selects the second init sequence (lcd_type 1). Same as found in 2026-10 ([stock-firmware.md](stock-firmware.md)).

## Not confirmed

- Which ROCKNIX device tree each PE6 level means is inferred (low = the second panel: rev6 / v2) and needs one unit of each panel to confirm.
- A real rev6 unit's PE6 reading (expected 0) is still unmeasured.
