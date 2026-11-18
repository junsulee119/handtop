# 2026-11-18: USB host mode on the RG35XX H's right port

Test: [../usb-otg-host.md](../usb-otg-host.md). Unit: Jason's RG35XX H, DDR4, regular panel, Handtop v0.4.1 (`handtop-20261118-v0.4.1`), battery 63 → 60 %. Read-only: watcher and snapshot scripts in `ports/testing/`, nothing written or forced.

## Readings

| Step | ID pin (raw, active low) | Kernel | Port 5 V (`usb0-vbus`, PI16) | Device seen |
|---|---|---|---|---|
| Nothing plugged | lo | device mode | off | – |
| Charger | lo | device mode, `axp20x-usb` online | off | – |
| OTG adapter + keyboard | **hi** | switched to host | **on** (PI16 driven high, AXP717 `boost` enabled) | **no** |
| USB-C hub | **hi** | switched to host | **on** | **no** |
| OTG adapter + keyboard dongle (snapshot) | hi | host | on | **no**: OHCI root port powered (`PPS`) but no connection (`CCS` clear) |
| NVMe enclosure with LED | – | – | – | no LED |

After each unplug the ID pin went back to lo and the 5 V regulator off. No kernel messages about USB at any point after boot.

## Result

- **The software side works on this SoC:** a plugged-in adapter or hub flips the ID pin, ROCKNIX's kernel routes the port to the host controllers and turns on its 5 V supply (GPIO PI16 high, the AXP717 boost on), and turns it off again on unplug or with a charger. `docs/hardware.md` assumed the ID pin never reacts on a USB-C port; it does.
- **No power reaches the plug on the RG35XX H:** a device with an LED stays dark and the host controller never sees a connection. The H's right port evidently has no 5 V path to the connector (Anbernic designed it as a charging and device port; the H has its own host port on the left).
- So the H **cannot stand in** for the one-port models' host mode. On them the same kernel path runs; whether their board feeds 5 V to the connector is a per-model check for testers (plug in a device with an LED; a keyboard should then work).

## Not done

Steps 5 (charger on the left port while hosting) and 6 (restart, charging and External Controller USB mode afterwards) do not apply: host mode never got a device.
