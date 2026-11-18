# RG35XX Plus

Evidence for the Handtop profile of this model (phase P1). Nothing here is built or tested yet.

## Sources

- ROCKNIX **20261001** H700 image (the one Handtop builds from, checksum in `build/config.sh`): device trees `sun50i-h700-anbernic-rg35xx-plus.dtb`, `sun50i-h700-anbernic-rg35xx-plus-rev6-panel.dtb` and its panel firmware; summarised in [h700-20261001-facts.json](h700-20261001-facts.json) by `ports/tools/dt-facts.py`.
- ROCKNIX H700 installation guide ([rocknix.org](https://rocknix.org/configure/h700-installation/)).

## From the device tree

| Item | Value |
|---|---|
| `rg35xx-plus` panel | `anbernic,rg35xx-plus-panel`: 640×480, 70×53 mm |
| `rg35xx-plus-rev6-panel` panel | `anbernic,rg35xx-plus-rev6-panel`: 640×480, 70×53 mm |
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

- No sticks (`amux-count` 0): the right-stick scroll and L3 / R3 copy and paste need other controls.
- Same panels as the RG35XX H (regular and rev6), 640×480.
- Editorial pick: "the default recommendation" of one 2026 comparison ([source](https://handheldindex.pages.dev/comparisons/best-anbernic-handheld-2026/)).
- Stock U-Boot (RG35XX+-P V1.2.4): reads **PE6 with the pull-up on**, like the H: high = base, low = rev6 ([stock-firmware.md](stock-firmware.md)).

## Not confirmed

- The PE6 table comes from matching the stock init sequences with ROCKNIX's panel files; a unit with the second panel should confirm the low reading.
- USB keyboards and hubs: only the OTG (charging) port is enabled, so they need it in host mode; untested in Handtop (see [h700.md](h700.md#usb)).
- RAM type per batch: not confirmed.
