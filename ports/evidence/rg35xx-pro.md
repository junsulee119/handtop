# RG35XX Pro

Evidence for the Handtop profile of this model (phase P1). Nothing here is built or tested yet.

## Sources

- ROCKNIX **20261001** H700 image (the one Handtop builds from, checksum in `build/config.sh`): device tree `sun50i-h700-anbernic-rg35xx-pro.dtb` and its panel firmware; summarised in [h700-20261001-facts.json](h700-20261001-facts.json) by `ports/tools/dt-facts.py`.
- ROCKNIX H700 installation guide ([rocknix.org](https://rocknix.org/configure/h700-installation/)).

## From the device tree

| Item | Value |
|---|---|
| `rg35xx-pro` panel | `anbernic,rg35xx-plus-panel`: 640×480, 70×53 mm |
| Gamepad | `rocknix-singleadc-joypad`, name "H700 Gamepad", 17 button codes (same set as the RG35XX H) |
| Stick axes | 4 (`amux-count`); inverted: absx, absy |
| Motor | PWM channel 2 |
| Other keys | Key Volume Up, Key Volume Down |
| LEDs | power, status |
| Wi-Fi / Bluetooth | RTL8821CS (SDIO Wi-Fi, UART Bluetooth) |
| HDMI | enabled |
| USB | `usb@5100000`, `usb@5101000`, `usb@5101400` (OTG controller only) |
| RTC | allwinner,sun50i-h616-rtc, nxp,pcf8563 |

## Notes

- Device tree: the RG35XX H's, except that the H's second USB host controller (`usb@5200000`, `usb@5200400`) and its VBUS regulators are disabled; same panel firmware (`rg35xx-plus-panel`, 640×480), same two sticks, same axis inversion, same motor channel.
- Stock U-Boot of the Pro and the H, and of no other model, contains code for a **second USB port** (`allen_usb2_vbus_en`, `allen_usb2_pwr_en`, `allen_usb2_id_det`), but ROCKNIX's Pro device tree disables the second host controller. The Pro may have a host port like the H's left one that ROCKNIX does not switch on; check on the hardware.
- Community: the top vote in the under-$50 category of Retro Handhelds' community vote (over 1,000 responses, December 2025) ([source](https://retrohandhelds.gg/the-best-handhelds-at-each-price-point-as-decided-by-you/)).
- Stock U-Boot (RG35XXPRO V1.0.5): reads **PE6 with the pull-up on**, like the H: high = `rg35xx-plus-panel`, low = `rg35xx-plus-rev6-panel`. ROCKNIX ships only the first as a Pro device tree; Handtop can make the rev6 one by changing the panel `compatible` ([stock-firmware.md](stock-firmware.md)).

## Not confirmed

- The PE6 table comes from matching the stock init sequences with ROCKNIX's panel files; a unit with the second panel should confirm the low reading.
- USB: only the OTG controller is enabled, so a USB keyboard or hub must go through the charging port in host mode (see [h700.md](h700.md#usb)). Physical port count not confirmed.
- RAM type (DDR3 / DDR4) per batch: not confirmed.
