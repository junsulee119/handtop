# Stock firmware: how each model picks its screen panel

Read-only analysis of Anbernic's stock card images, 2026-11-18, with `ports/tools/stock-panel-check.py` (the method used for the RG35XX H in 2026-10, [docs/services/panel.md](../../docs/services/panel.md#where-pe6-comes-from)). Only the first 64 MiB of each image were extracted (boot0 and the U-Boot package at 16400 KiB); the images themselves are not in the repository.

## Images read

| Model | Stock image |
|---|---|
| RG35XX H | `RG35XXH-V1.2.4-EN16GB-260522` |
| RG35XX Pro | `RG35XXPRO-V1.0.5-EN16GB-260522` |
| RG35XX Plus | `RG35XX+-P-V1.2.4-EN16GB-260522` |
| RG35XX SP | `RG35XXSP-V1.1.5-EN16GB-260522` |
| RG40XX H | `RG40XXH-V1.1.0-EN16GB-260521` |
| RG40XX V | `RG40XXV-V1.1.1.0-EN16GB-260521` |
| RG CubeXX | `RGCUBEXX-V1.0.7-EN16GB-260525` |
| RG34XX | `RG34XX-V1.0.6-EN16GB-260526` |
| RG34XX SP | `RG34XXSP-V1.0.6-EN16GB-260526` |
| RG SP | `RGSP-V1.0.1-EN16GB-260624` |
| RG28XX | `RG28XX-V1.1.3-EN16GB-260526` |
| RG35XX 2024 | **missing.** `35XX双-20231014-EN4GB` was checked: its U-Boot is "for owl board", i.e. the original RG35XX (Actions SoC, not H700) |

## Result

Every image has the same U-Boot function, `lcd_panel_uboot_fj035fhd05_v1_init` (at u-boot offset `0x262e4` in all of them). Where a model has two panels, it reads **PE6**, sets `lcd_type = 1` when PE6 is **low**, and runs one of two panel init sequences (`cmp lcd_type, #1`).

| Model | Pin | Pull-up set by U-Boot | ROCKNIX device trees |
|---|---|---|---|
| RG35XX H | PE6 | yes | base, rev6-panel |
| RG35XX Pro | PE6 | yes | base only |
| RG35XX Plus | PE6 | yes | base, rev6-panel |
| RG34XX | PE6 | yes | base only |
| RG34XX SP | PE6 | yes | base, v2-panel |
| RG SP | PE6 | yes | v2 panel only |
| RG35XX SP | PE6 | **no** (reads the pin as the board leaves it) | base, v2-panel |
| RG40XX H | PE6 | **no** | base, v2-panel |
| RG40XX V | PE6 | **no** | base, v2-panel |
| RG CubeXX | none: one panel | | one |
| RG28XX | none: one panel | | one |

## What it means (conclusions)

- **One check for all two-panel models.** Handtop's `rg35xxh-panel` already reads PE6 the H's way; the same check, enabled per model by its profile, covers every model above. For the RG35XX SP and RG40XX family the check should read the pin without turning the pull-up on, as their stock U-Boot does.
- **Which device tree each level means is inferred, not measured:** PE6 low (`lcd_type` 1) = the second panel (rev6 / v2). On the H only the high reading has been measured (regular panel). Each family needs one unit with the second panel to confirm; until then `panel.txt` stays the override.
- **ROCKNIX may be missing panel variants:** the stock U-Boot of the RG35XX Pro, RG34XX and RG SP has two init sequences, but ROCKNIX ships one device tree for each. Units with the other panel would show a garbled screen with every ROCKNIX-based image. For the Pro the fix would be a rev6 variant made like the H's (the H's two device trees differ only in the panel); for the RG34XX and RG SP it needs the second panel's init sequence, which would have to come from the stock firmware.
- **A second USB port on the RG35XX Pro:** only the H's and the Pro's stock U-Boot contain code for a second USB port (`allen_usb2_vbus_en`, `allen_usb2_pwr_en`, `allen_usb2_id_det`). ROCKNIX's Pro device tree disables the second host controller. If the Pro has that port, enabling it would give the Pro the H's separate host port. Check on the hardware or a spec sheet.
