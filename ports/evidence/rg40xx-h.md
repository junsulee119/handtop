# RG40XX H

Evidence for the Handtop profile of this model (phase P1). Nothing here is built or tested yet.

## Sources

- ROCKNIX **20261001** H700 image (the one Handtop builds from, checksum in `build/config.sh`): device trees `sun50i-h700-anbernic-rg40xx-h.dtb`, `sun50i-h700-anbernic-rg40xx-h-v2-panel.dtb` and its panel firmware; summarised in [h700-20261001-facts.json](h700-20261001-facts.json) by `ports/tools/dt-facts.py`.
- ROCKNIX H700 installation guide ([rocknix.org](https://rocknix.org/configure/h700-installation/)).

## From the device tree

| Item | Value |
|---|---|
| `rg40xx-h` panel | `anbernic,rg40xx-panel`: 640×480, 81×61 mm |
| `rg40xx-h-v2-panel` panel | `anbernic,rg40xx-v2-panel`: 640×480, 81×61 mm |
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

- 4" 640×480 panel (`rg40xx-panel`, 81×61 mm), so the layout is the H's at a larger size.
- Two sticks; the right stick is inverted in the device tree (the H's is not).
- RGB stick LEDs (`kbd_backlight`) driven by ROCKNIX through a serial port (`serial@5001400` enabled, quirk `analog_sticks_ledcontrol`).
- Motor on PWM channel 3 (H: 2); handled by the device tree.
- Stock U-Boot (RG40XXH V1.1.0): reads **PE6 without changing its pull**; low selects the second sequence ([stock-firmware.md](stock-firmware.md)).

## Not confirmed

- Which ROCKNIX device tree each PE6 level means is inferred (low = the second panel: rev6 / v2) and needs one unit of each panel to confirm.
- RGB LEDs: leave off or support; not decided.
- USB keyboards and hubs: only the OTG (charging) port is enabled, so they need it in host mode; untested in Handtop (see [h700.md](h700.md#usb)).
- RAM type per batch: not confirmed.
