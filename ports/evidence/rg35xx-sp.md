# RG35XX SP

Evidence for the Handtop profile of this model (phase P1). Nothing here is built or tested yet.

## Sources

- ROCKNIX **20261001** H700 image (the one Handtop builds from, checksum in `build/config.sh`): device trees `sun50i-h700-anbernic-rg35xx-sp.dtb`, `sun50i-h700-anbernic-rg35xx-sp-v2-panel.dtb` and its panel firmware; summarised in [h700-20261001-facts.json](h700-20261001-facts.json) by `ports/tools/dt-facts.py`.
- ROCKNIX H700 installation guide ([rocknix.org](https://rocknix.org/configure/h700-installation/)).

## From the device tree

| Item | Value |
|---|---|
| `rg35xx-sp` panel | `anbernic,rg35xx-plus-panel`: 640×480, 70×53 mm |
| `rg35xx-sp-v2-panel` panel | `anbernic,rg35xx-sp-v2-panel`: 640×480, 70×53 mm |
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

- Clamshell: a lid switch (`SW_LID`, wake source) in the device tree.
- No sticks.
- Two panels: `rg35xx-plus-panel` and `rg35xx-sp-v2-panel`, both 640×480.
- Editorial pick: "the specific-use winner" in one 2026 comparison ([source](https://handheldindex.pages.dev/comparisons/best-anbernic-handheld-2026/)).
- Stock U-Boot (RG35XXSP V1.1.5): reads **PE6 without changing its pull**: high = `rg35xx-plus-panel`, low = `rg35xx-sp-v2-panel` ([stock-firmware.md](stock-firmware.md)).

## Not confirmed

- The PE6 table comes from matching the stock init sequences with ROCKNIX's panel files; a unit with the second panel should confirm the low reading.
- Lid behaviour (sleep on close) is new to Handtop.
- USB keyboards and hubs: only the OTG (charging) port is enabled, so they need it in host mode; untested in Handtop (see [h700.md](h700.md#usb)).
- RAM type per batch: not confirmed.
