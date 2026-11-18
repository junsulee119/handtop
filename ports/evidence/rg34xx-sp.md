# RG34XX SP

Evidence for the Handtop profile of this model (phase P1). Nothing here is built or tested yet.

## Sources

- ROCKNIX **20261001** H700 image (the one Handtop builds from, checksum in `build/config.sh`): device trees `sun50i-h700-anbernic-rg34xx-sp.dtb`, `sun50i-h700-anbernic-rg34xx-sp-v2-panel.dtb` and its panel firmware; summarised in [h700-20261001-facts.json](h700-20261001-facts.json) by `ports/tools/dt-facts.py`.
- ROCKNIX H700 installation guide ([rocknix.org](https://rocknix.org/configure/h700-installation/)).

## From the device tree

| Item | Value |
|---|---|
| `rg34xx-sp` panel | `anbernic,rg34xx-sp-panel`: 720×480, 71×48 mm |
| `rg34xx-sp-v2-panel` panel | `anbernic,rg34xx-sp-v2-panel`: 720×480, 71×48 mm |
| Gamepad | `rocknix-singleadc-joypad`, name "H700 Gamepad", 17 button codes (same set as the RG35XX H) |
| Stick axes | 4 (`amux-count`); inverted: absrx, absry, absx, absy |
| Motor | PWM channel 2 |
| Other keys | Key Volume Up, Key Volume Down, Lid Switch |
| LEDs | power, status |
| Wi-Fi / Bluetooth | RTL8821CS (SDIO Wi-Fi, UART Bluetooth) |
| HDMI | enabled |
| USB | `usb@5100000`, `usb@5101000`, `usb@5101400` (OTG controller only) |
| RTC | allwinner,sun50i-h616-rtc, nxp,pcf8563 |

## Notes

- **720×480** panel; two panel files (`rg34xx-sp-panel`, `rg34xx-sp-v2-panel`).
- Clamshell with lid switch.
- Two sticks, both inverted in the device tree.
- Community: main pick of the $50–100 category in the same Retro Handhelds vote (December 2025) ([source](https://retrohandhelds.gg/the-best-handhelds-at-each-price-point-as-decided-by-you/)).
- Stock U-Boot (RG34XXSP V1.0.6): reads **PE6 with the pull-up on**; low selects the second sequence ([stock-firmware.md](stock-firmware.md)).

## Not confirmed

- Which ROCKNIX device tree each PE6 level means is inferred (low = the second panel: rev6 / v2) and needs one unit of each panel to confirm.
- USB keyboards and hubs: only the OTG (charging) port is enabled, so they need it in host mode; untested in Handtop (see [h700.md](h700.md#usb)).
- RAM type per batch: not confirmed.
