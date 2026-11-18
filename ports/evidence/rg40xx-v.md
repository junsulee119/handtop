# RG40XX V

Evidence for the Handtop profile of this model (phase P1). Nothing here is built or tested yet.

## Sources

- ROCKNIX **20261001** H700 image (the one Handtop builds from, checksum in `build/config.sh`): device trees `sun50i-h700-anbernic-rg40xx-v.dtb`, `sun50i-h700-anbernic-rg40xx-v-v2-panel.dtb` and its panel firmware; summarised in [h700-20261001-facts.json](h700-20261001-facts.json) by `ports/tools/dt-facts.py`.
- ROCKNIX H700 installation guide ([rocknix.org](https://rocknix.org/configure/h700-installation/)).

## From the device tree

| Item | Value |
|---|---|
| `rg40xx-v` panel | `anbernic,rg40xx-panel`: 640×480, 81×61 mm |
| `rg40xx-v-v2-panel` panel | `anbernic,rg40xx-v2-panel`: 640×480, 81×61 mm |
| Gamepad | `rocknix-singleadc-joypad`, name "H700 Gamepad", 17 button codes (same set as the RG35XX H) |
| Stick axes | 4 (`amux-count`); inverted: absx, absy |
| Motor | PWM channel 3 |
| Other keys | Key Volume Up, Key Volume Down |
| LEDs | power, status, kbd_backlight |
| Wi-Fi / Bluetooth | RTL8821CS (SDIO Wi-Fi, UART Bluetooth) |
| HDMI | enabled |
| USB | `usb@5100000`, `usb@5101000`, `usb@5101400` (OTG controller only) |
| RTC | allwinner,sun50i-h616-rtc, nxp,pcf8563 |

## Notes

- Same as the RG40XX H in the device tree (panel, LEDs, motor channel) except that the right stick is not inverted.
- The device tree declares four stick axes (`amux-count` 4).
- Stock U-Boot (RG40XXV V1.1.1.0): reads **PE6 without changing its pull**: high = `rg40xx-panel`, low = `rg40xx-v2-panel` ([stock-firmware.md](stock-firmware.md)).

## Not confirmed

- The PE6 table comes from matching the stock init sequences with ROCKNIX's panel files; a unit with the second panel should confirm the low reading.
- Number of physical sticks: not confirmed from an official source here; the device tree reads four axes either way, so the profile needs a spec sheet or a tester before it says how many.
- USB keyboards and hubs: only the OTG (charging) port is enabled, so they need it in host mode; untested in Handtop (see [h700.md](h700.md#usb)).
- RAM type per batch: not confirmed.
