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
| RG35XX 2024 | **none published** (Jason, 2026-11-18); assumed covered by the RG35XX Plus image until a 2024 owner says otherwise. `35XX双-20231014-EN4GB` was checked: its U-Boot is "for owl board", the original RG35XX (Actions SoC, not H700) |

## Result

Every image has the same U-Boot function, `lcd_panel_uboot_fj035fhd05_v1_init` (at u-boot offset `0x262e4` in all of them). Where a model has two panels, it reads **PE6**, sets `lcd_type = 1` when PE6 is **low**, and runs one of two panel init sequences (`cmp lcd_type, #1`). Each init sequence is a list of command and data writes with constant arguments, so the tool extracts both and compares them with ROCKNIX's panel firmware files (`--panels`); a score near 1.00 means the same command list.

| Model | Pull-up set by U-Boot | PE6 **high** (lcd_type 0): closest ROCKNIX panel | PE6 **low** (lcd_type 1): closest ROCKNIX panel | ROCKNIX device trees |
|---|---|---|---|---|
| RG35XX H | yes | `rg35xx-plus-panel` (0.99) | `rg35xx-plus-rev6-panel` (0.87) | base, rev6-panel |
| RG35XX Pro | yes | `rg35xx-plus-panel` (0.99) | `rg35xx-plus-rev6-panel` (0.87) | base only |
| RG35XX Plus | yes | `rg35xx-plus-panel` (0.99) | `rg35xx-plus-rev6-panel` (0.87) | base, rev6-panel |
| RG35XX SP | **no** | `rg35xx-plus-panel` (0.99) | `rg35xx-sp-v2-panel` (0.99) | base, v2-panel |
| RG40XX H | **no** | `rg40xx-panel` (0.97) | `rg40xx-v2-panel` (0.99) | base, v2-panel |
| RG40XX V | **no** | `rg40xx-panel` (0.97) | `rg40xx-v2-panel` (0.99) | base, v2-panel |
| RG34XX | yes | `rg34xx-panel` (0.96) | `rg34xx-sp-panel` (0.99) | base only |
| RG34XX SP | yes | `rg34xx-sp-v2-panel` (0.99) | `rg34xx-sp-panel` (0.99) | base, v2-panel |
| RG SP | yes | `rg34xx-sp-v2-panel` (0.99) | `rg34xx-sp-panel` (0.99) | v2 panel only |
| RG CubeXX | none: one panel | | | one |
| RG28XX | none: one panel | | | one |

The RG35XX H row agrees with the one measurement so far (a regular-panel H reads PE6 high). The rev6 match is lower (0.87) because ROCKNIX's rev6 file differs in some values; it is still far closer than any other file.

## What it means (conclusions)

- **One check for all two-panel models.** Handtop's `rg35xxh-panel` already reads PE6 the H's way; the same check, enabled per model by its profile with that model's high / low table, covers every model above. For the RG35XX SP and RG40XX family it should read the pin without turning the pull-up on, as their stock U-Boot does.
- **The RG34XX SP is the other way round:** PE6 high means its v2 panel, low its original panel. The profile carries the table, so the check never assumes "low = second file".
- **The panels ROCKNIX lacks already exist in ROCKNIX:** the second panel of the RG35XX Pro is the rev6 panel, and the second panel of the RG34XX and the RG SP is the RG34XX SP's original panel (`rg34xx-sp-panel`). ROCKNIX ships the firmware for both, only not a device tree for those combinations. Handtop can make them at image build the way the RG35XX H's two device trees differ: the same tree with the panel's `compatible` changed. No init sequence needs to be taken from the stock firmware.
- **Still unmeasured:** a unit of each family with its second panel, to confirm the low reading; until then `panel.txt` stays the override.
- **A second USB port on the RG35XX Pro:** only the H's and the Pro's stock U-Boot contain code for a second USB port (`allen_usb2_vbus_en`, `allen_usb2_pwr_en`, `allen_usb2_id_det`). ROCKNIX's Pro device tree disables the second host controller. If the Pro has that port, enabling it would give the Pro the H's separate host port. Check on the hardware or a spec sheet.
