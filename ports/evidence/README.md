# Evidence for other models (phase P1)

What public sources say about each H700 model ROCKNIX 20261001 supports, collected on 2026-11-18 for choosing the first targets ([../PLAN.md](../PLAN.md)). Facts are kept apart from conclusions: each model page lists what its sources say, then what is not confirmed. Conclusions below are marked as such.

## Sources and method

- **Device trees and panel firmware** from ROCKNIX's 20261001 H700 image, the image Handtop already builds from (step `02` extracts them to `work/rocknix/`). `ports/tools/dt-facts.py` reads them (with `dtc`) and writes [h700-20261001-facts.json](h700-20261001-facts.json). Re-run it when the ROCKNIX release changes.
- **ROCKNIX source** at tag 20261001: H700 kernel patches and device quirks ([tree](https://github.com/ROCKNIX/distribution/tree/20261001/projects/ROCKNIX)).
- **ROCKNIX H700 installation guide** ([rocknix.org](https://rocknix.org/configure/h700-installation/)): device-tree names and its advice on panel variants.
- **Anbernic and press** for the RG SP announcement; **community and editorial picks** for usage (below).

## Models

| Model | Panel | Sticks | Lid | Radios | USB | Device-tree variants |
|---|---|---|---|---|---|---|
| [RG35XX H](rg35xx-h.md) | 640×480 | 4 axes | – | Wi-Fi + BT | OTG + host port | base, rev6-panel |
| [RG35XX Pro](rg35xx-pro.md) | 640×480 | 4 axes | – | Wi-Fi + BT | OTG only | – |
| [RG35XX Plus](rg35xx-plus.md) | 640×480 | none | – | Wi-Fi + BT | OTG only | base, rev6-panel |
| [RG35XX SP](rg35xx-sp.md) | 640×480 | none | yes | Wi-Fi + BT | OTG only | base, v2-panel |
| [RG35XX 2024](rg35xx-2024.md) | 640×480 | none | – | **none** | OTG only | base, rev6-panel |
| [RG40XX H](rg40xx-h.md) | 640×480 | 4 axes | – | Wi-Fi + BT | OTG only | base, v2-panel |
| [RG40XX V](rg40xx-v.md) | 640×480 | 4 axes | – | Wi-Fi + BT | OTG only | base, v2-panel |
| [RG CubeXX](rgcubexx.md) | 720×720 | 4 axes | – | Wi-Fi + BT | OTG only | – |
| [RG34XX](rg34xx.md) | 720×480 | none | – | Wi-Fi + BT | OTG only | – |
| [RG34XX SP](rg34xx-sp.md) | 720×480 | 4 axes | yes | Wi-Fi + BT | OTG only | base, v2-panel |
| [RG SP](rg-sp.md) | 720×480 | none | yes | Wi-Fi + BT | OTG only | – |
| [RG28XX](rg28xx.md) | 480×640 (rotated 270°) | none | – | Wi-Fi + BT | OTG only | – |

What they share, what differs, USB, panel variants and RAM type: [h700.md](h700.md). How the stock firmware picks the panel: [stock-firmware.md](stock-firmware.md).

## How many people use them

Thin so far; no sales figures found.

- **RG35XX Pro:** top community vote in the under-$50 category, and **RG34XX SP** the main pick for $50–100, in Retro Handhelds' Handheld of the Year 2025 vote (over 1,000 responses, December 2025) ([source](https://retrohandhelds.gg/the-best-handhelds-at-each-price-point-as-decided-by-you/)).
- **RG35XX Plus** ("the default recommendation") and **RG35XX SP**: one author's 2026 comparison ([source](https://handheldindex.pages.dev/comparisons/best-anbernic-handheld-2026/)).
- **RG CubeXX:** an owner offered to test Handtop (Reddit, recorded in the earlier plan).
- **RG SP:** announced July 2026, the newest model.

Better data would come from Handtop's own users: a short "which H700 do you have, and would you test?" question where Handtop is discussed (Reddit, Discord). Posting it is Jason's call.

## Effort from the RG35XX H (conclusion)

Judged from the device-tree differences only:

| Effort | Models | What is new compared with the H |
|---|---|---|
| Profile only | RG35XX Pro | Nothing in the device tree except the missing second USB port |
| One new piece | RG40XX H, RG40XX V | Panel variant (v2) with no known check; RGB stick LEDs (can stay off); RG40XX V: stick count |
| | RG35XX Plus, RG35XX SP, RG35XX 2024 | No sticks (controls for scroll and copy / paste); panel variant; SP: lid; 2024: no radios |
| Needs the screen-size work (P3) | RG CubeXX | 720×720; no panel variant |
| | RG34XX, RG34XX SP, RG SP | 720×480; no sticks (except 34XX SP); lid on the SPs; 34XX SP: panel variant |
| | RG28XX | Rotated panel; no sticks |

Every model except the H also needs USB keyboards and hubs on its charging port (host mode, untested). Every model with two panels can use the H's PE6 check ([stock-firmware.md](stock-firmware.md)).

## Targets (decided 2026-11-18, Jason)

1. **First:** RG40XX V, RG CubeXX and RG35XX SP, next to the RG35XX H. Between them they bring every new piece but rotation: 720×720, no sticks, a lid, the RG40XX family's panel check and RGB LEDs.
2. **Then every other model in the list**, most of them profile-only after the first three: RG35XX Pro (H), RG40XX H (RG40XX V), RG35XX Plus and RG35XX 2024 (RG35XX SP), RG34XX, RG34XX SP and RG SP (720×480 once the CubeXX's screen work is done), RG28XX (rotation).

## Still open after P1

- Panel variants: the stock U-Boot of every two-panel model reads PE6 ([stock-firmware.md](stock-firmware.md)); which level means which device tree still needs one unit of each panel. RG35XX 2024 stock firmware still missing.
- RAM type per model and batch.
- RG40XX V's stick count (its device tree reads four axes) and RG28XX's Wi-Fi (its device tree has it; the earlier plan said none): confirm from a spec sheet or a tester.
- USB host mode on the OTG port, on each model.
