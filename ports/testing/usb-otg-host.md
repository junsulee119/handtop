# Test: USB host mode on the charging port (RG35XX H)

**Why:** every H700 model except the RG35XX H has only one USB port, the OTG port that also charges ([../evidence/h700.md](../evidence/h700.md#usb)). A keyboard, mouse or hub there needs that port in host mode. The H has the same OTG port (its right port) with, per the device trees, the same controller, the same ID-detect pin (PI4) and the same 5 V output switch (PI16) as the other models. This test finds out how far the H can stand in for them.

**How the kernel decides** (ROCKNIX's `0151-phy-fix-OTG-host-mode.patch`): the port is a host only while the ID-detect pin reads low. It then routes the port to the host controllers and turns on its 5 V output; when the pin goes high again it turns the output off, and it also turns it off when it sees outside power (a charger). Software asking for host mode is ignored on this SoC. So the question is simply **whether PI4 goes low when something is plugged in**. `docs/hardware.md` (2026-10-29) saw a hub on the right port never detected, which suggests it doesn't on the H; this test checks it properly and records why.

**Safety ([../../docs/hardware-safety.md](../../docs/hardware-safety.md)):** this test only **reads**: no writes to sysfs, debugfs, GPIOs or the power chip, nothing forced. Run `sync` before each plug-in. If anything stops responding, note the time, hold Power 10 s and keep the card for its journal. Forcing host mode is not part of this test; if it ever seems needed, that is a separate decision.

## What you need

- RG35XX H on Handtop v0.4.1, SSH on, Wi-Fi connected, battery above 50 %.
- A USB-C OTG adapter (USB-C plug to USB-A socket) and a USB keyboard; if you have one, a USB-C hub with its own C plug.
- The charger you normally use.

## Readings (run after every step)

Copy the read-only script to the handheld once (from the PC, in the repository folder):

```
scp ports/testing/usb-otg-readings.sh rg@192.168.200.155:/tmp/
```

Then after every step (it asks for your password; it reads only):

```
ssh -t rg@192.168.200.155 "sudo sh /tmp/usb-otg-readings.sh"
```

Write down for each step: the ID-detect pin value, the `mode` line, whether `usb0-vbus` is enabled, what `lsusb -t` shows, and the new kernel lines.

## Steps

1. **Nothing plugged in** into the right port, no charger. Readings. (Expected: ID high, mode `b_idle`, `usb0-vbus` off.)
2. **Charger** into the right port. Readings. Unplug it. Readings.
3. `sync`. **OTG adapter + keyboard** into the right port, no charger. Wait 5 s. Readings. Type on the keyboard (does anything appear?). Unplug. Readings.
4. `sync`. **USB-C hub** (if you have one) with the keyboard, the same way. Readings. Unplug. Readings.
5. **Only if step 3 or 4 switched to host mode** (`a_host`, `usb0-vbus` on, keyboard in `lsusb`):
   a. With the keyboard still on the adapter, plug the **charger into the left port**: does the H keep working, is the battery charging?
   b. Unplug the keyboard; check that mode goes back and `usb0-vbus` turns off.
   c. Restart the H; check that the right port charges as before.
6. Restart once at the end and check that the right port still charges and External Controller's USB mode still starts (the same port's device side).

## What the result means

- **ID never goes low (expected):** the H's right port has no way to tell a plugged-in device on its own, so it can't stand in for the one-port models. Their host mode is then checked on their own hardware: by testers, and by reading how the stock firmware of a one-port model drives its ID pin (`allen_usb_id_det` in its U-Boot).
- **ID goes low and the keyboard works:** the kernel path (switching, 5 V on and off, the outside-power cut) is proven on this SoC; what is left per model is only the board wiring.
- **Anything in between** (ID low but no keyboard, 5 V stays on after unplugging, a hang): stop, keep the logs, and we look at it before anything else.

Record the result in `ports/testing/reports/` (date, image, unit DDR4 / DDR3, readings per step).
