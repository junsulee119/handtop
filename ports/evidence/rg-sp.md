# RG SP

Evidence for the Handtop profile of this model (phase P1). Nothing here is built or tested yet.

## Sources

- ROCKNIX **20261001** H700 image (the one Handtop builds from, checksum in `build/config.sh`): device tree `sun50i-h700-anbernic-rg-sp.dtb` and its panel firmware; summarised in [h700-20261001-facts.json](h700-20261001-facts.json) by `ports/tools/dt-facts.py`.
- ROCKNIX H700 installation guide ([rocknix.org](https://rocknix.org/configure/h700-installation/)).
- Anbernic: <https://anbernic.com/blogs/news/anbernic-rg-sp-first-look>

## From the device tree

| Item | Value |
|---|---|
| `rg-sp` panel | `anbernic,rg34xx-sp-v2-panel`: 720×480, 71×48 mm |
| Gamepad | `rocknix-singleadc-joypad`, name "H700 Gamepad", 17 button codes (same set as the RG35XX H) |
| Stick axes | 0 (`amux-count`); inverted: absx, absy |
| Motor | PWM channel 2 |
| Other keys | Key Volume Up, Key Volume Down, Lid Switch |
| LEDs | power, status |
| Wi-Fi / Bluetooth | RTL8821CS (SDIO Wi-Fi, UART Bluetooth) |
| HDMI | enabled |
| USB | `usb@5100000`, `usb@5101000`, `usb@5101400` (OTG controller only) |
| RTC | allwinner,sun50i-h616-rtc, nxp,pcf8563 |

## Notes

- Announced July 2026: H700, 3.4" 720×480, clamshell, **no sticks** ([Anbernic](https://anbernic.com/blogs/news/anbernic-rg-sp-first-look), [Retro Handhelds](https://retrohandhelds.gg/anbernic-announces-the-rg-sp-with-almost-everything-we-need-to-know/)).
- Device tree: the RG34XX SP v2 panel (`rg34xx-sp-v2-panel`), lid switch, no stick axes.
- Stock U-Boot (RGSP V1.0.1): reads **PE6 with the pull-up on** and has two init sequences; ROCKNIX ships one device tree (the RG34XX SP v2 panel) ([stock-firmware.md](stock-firmware.md)).

## Not confirmed

- Which ROCKNIX device tree each PE6 level means is inferred (low = the second panel: rev6 / v2) and needs one unit of each panel to confirm.
- RAM, battery, ports: not stated by Anbernic at announcement.
- USB keyboards and hubs: only the OTG (charging) port is enabled (see [h700.md](h700.md#usb)).
