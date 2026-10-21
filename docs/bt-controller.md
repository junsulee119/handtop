# BT Controller mode

Use the handheld as a **Bluetooth gamepad** for a PC or phone (v0.2.0; shows up as an Xbox Wireless Controller since the next release).

## Use

1. On the handheld: **Apps → External Controller**. The handheld switches to BT Controller mode (the taskbar's input-mode icon shows a controller with signal waves, blue with rainbow stripes) and appears as **"Handtop Gamepad"**.
2. First time only, on the other device: Bluetooth → add device → **Handtop Gamepad** (Windows: Settings → Bluetooth & devices → Add device → Bluetooth). No PIN.
3. Play. Check it on Windows with `joy.cpl` ("Set up USB game controllers").
4. Press **Select + Start + L1 + R1** together to return to desktop mode; this also ends BT Controller mode. (Same combo as Moonlight's quit; holding Start no longer exits here, so a long Start press reaches the other device.)

BT Controller mode is separate from gamepad mode: in gamepad mode the controls drive a virtual Xbox pad *on the handheld* (for Moonlight, games); in BT Controller mode they go only to the other device, and apps on the handheld see no controller. The input-mode icon in the taskbar shows which one is on: mouse (desktop), controller (gamepad), controller with signal waves on rainbow stripes (BT Controller).

Next time, just open BT Controller again: the paired device reconnects by itself within a few seconds.

**Re-pairing:** remove "Handtop Gamepad" on the other device **and** on the handheld (Bluetooth tray → Devices), then pair again. If only one side forgets the pairing, the other refuses it.

**Updating from v0.2.0:** the handheld now presents itself as an Xbox controller, and Windows remembers the old (generic) description per pairing. Remove "Handtop Gamepad" on the PC once and pair it again. Windows may also list a second "Handtop Gamepad" with a phone icon: that is the handheld's normal Bluetooth identity; ignore or remove it.

## What the other device sees

An **Xbox Wireless Controller** (Series X|S, model 1914) over Bluetooth LE. Windows loads its own Xbox driver for it (Device Manager: "Bluetooth LE XINPUT compatible input device"), so XInput-only games work directly, and **game vibration plays on the handheld's motor** (through the same safety gate as Wired Controller mode, see "Vibration safety"). Buttons go by position, Xbox layout: the handheld's bottom button is Xbox A, the right one B, left X, top Y; Select = View, Start = Menu. Battery level is reported too.

Tested on Windows 11 (2026-10-21): driver, all controls, vibration. Android and Linux have drivers for this controller too (not tested yet).

Fallback: `RG35XXH_BTPAD_PROFILE=generic` in the service's environment (`systemctl edit rg35xxh-btpad`) gives the v0.2.0 behaviour, a generic BLE gamepad (buttons 1–10, hat, X/Y, Z/Rz, Rx/Ry for the triggers) with no vibration; re-pair after switching.

## Trade-off: classic Bluetooth pauses

While BT Controller mode is on, the handheld's Bluetooth is **BLE only**. Accessories connected *to* the handheld over **BLE** keep working; **classic Bluetooth** accessories (many keyboards and mice, older Xbox One controllers) pause and come back when the mode ends.

Why: with classic Bluetooth on, Windows also derives a classic pairing key from the BLE pairing and later reconnects over classic Bluetooth, where there is no gamepad (it connects, but no input arrives).

## How it works

- `rg35xxh-btpad` (root, `rg35xxh-btpad.service`, not started at boot) registers a GATT application with BlueZ over D-Bus: HID service 0x1812 (report map, input report with notifications, output report, HID information, control point, protocol mode) and battery service 0x180F; a BLE advertisement (gamepad appearance 0x03C4, 30–60 ms interval); and a just-works pairing agent. Newly paired devices are marked trusted.
- **Xbox identity.** Windows picks its Xbox BLE driver (`xinputhid.inf`) by the PnP ID in the Device Information service, and only for product 0x0B13 or 0x0B20–0x0B27 from vendor 0x045E. BlueZ publishes that service itself (default `1d6b:0246`, from `DeviceID` in `main.conf`), so on start btpad writes a copy of `/etc/bluetooth/main.conf` with `DeviceID = usb:045e:0b13:0509` to `/run/rg35xxh-btpad/main.conf`, adds a runtime drop-in (`/run/systemd/system/bluetooth.service.d/50-rg35xxh-btpad.conf`, `bluetoothd -f` that file) and restarts bluetoothd; on exit it removes both and restarts it again (`ExecStopPost=rg35xxh-btpad --restore` does the same after a crash). The unit only `Wants=` bluetooth.service, so the restart does not stop it.
- **Report map**: the real controller's descriptor, byte for byte (283 bytes; from Mystfit/ESP32-BLE-CompositeHID, MIT, identical to the BLE dump in DJm00n/ControllersInfo). Input report 1, 16 bytes: X Y Z Rz as unsigned 16 bit (centre 32768), brake/accelerator 10 bit, hat 1–8 (0 = centred), 15 button bits (A 0, B 1, X 3, Y 4, LB 6, RB 7, View 10, Menu 11, Guide 12, LS 13, RS 14), Record. Output report 3, 8 bytes, written by Windows for vibration: enable bits, magnitudes 0–100 (left trigger, right trigger, strong, weak), duration and start delay in 10 ms, loop count. btpad turns it into `rumble <big> <small>` for the input daemon (≤ 20/s) and ends it after duration × loops by itself. Windows caches the report map per pairing.
- Input: it listens on `/run/rg35xxh-extpad.sock` (Unix seqpacket, root:input 0660). In BT Controller mode the input daemon uses its gamepad mapping but sends each pad event there (one evdev event per packet, `struct "<HHi"`: type, code, value) instead of creating the local virtual Xbox pad. btpad sends 16-byte HID reports (≤ 125/s); the status screen still gets the 9-byte generic layout.
- The **External Controller** app (`rg35xxh-bt-controller`) starts the service (allowed without a password by `/etc/polkit-1/rules.d/50-rg35xxh-btpad.rules`) waits for the socket and sends `SIGUSR2` to the input daemon, which connects to it and switches to BT Controller mode (flag file `$XDG_RUNTIME_DIR/rg35xxh-bt-mode`, read by autosleep and the taskbar indicator).
- Classic Bluetooth is switched off with `btmgmt` on start and back on (with SSP) on exit. The service stops by itself when the daemon disconnects (Select + Start + L1 + R1) or never connects (60 s); if the service stops first, the daemon returns to desktop mode.
- Logs: `journalctl -u rg35xxh-btpad`.

Tested 2026-10-21 with Windows 11: pairing, all controls in `joy.cpl`, automatic reconnection after leaving and re-entering the mode; with the Xbox identity: Xbox driver, vibration, identity restored when the mode ends.

## Status screen

While the mode is on, the handheld's screen shows a full-screen status page (`rg35xxh-controller-screen`, opened by the External Controller app, closed when the mode ends):

- **Connection:** "Ready to pair" (with how to pair), "Waiting for <PC>" (a paired PC that is not connected yet; it reconnects by itself) or "Connected to <PC>".
- **Live input:** a pixel-art drawing of the RG35XX H, proportioned from Anbernic's product photo (large centred screen, D-pad upper left, left stick lower left, X/A/B/Y upper right with their printed colours, right stick lower right, round Select/Start above the D-pad and face buttons, power LED, L1/L2 and R1/R2 on the top edge). Pressed buttons light up, the stick caps move, and L2/R2 fill.
- **Link info** on the drawn handheld's screen: HID reports sent per second (0 while nothing changes) and the BLE signal strength (`btmgmt conn-info`; strong ≥ −70 dBm, good ≥ −85 dBm, else weak).
- **Handheld battery** (top right) and **"Select + Start + L1 + R1 to stop"**.

It takes no input (every button goes to the other device) and hides the mouse pointer. `rg35xxh-controller-screen --demo` shows it with a fixed sample state. Volume (Vol) and brightness (F + Vol) still work in this mode: the input daemon handles those keys itself in every mode, and F is never sent to the other device.

Data: `rg35xxh-btpad` publishes JSON lines on `/run/rg35xxh-extpad-status.sock` (root:input 0660): `transport`, `state` (pairing / waiting / connected), `device`, `rssi`, `rate`, `report` (the 9-byte HID report, at most ~30 updates/s). The host is the paired device that is not itself an input device (BlueZ icon not `input-*`, no HID service); the last connected one is remembered in `/var/lib/rg35xxh/btpad-last-host`.

Planned: dim the backlight after a while (no button can wake it, since they all go to the other device; it would brighten again on a connection change).

## Wired Controller mode (USB cable)

**Apps → External Controller → USB cable.** The handheld becomes a **wired Xbox 360 controller** for a PC: Windows uses its built-in Xbox driver (no install), XInput-only games work directly, and the PC reads the controls at ~1000 reports/s. Vibration requested by the game is played on the handheld's motor. The handheld charges from the PC at the same time. Select + Start + L1 + R1 ends it, like BT Controller mode; the taskbar shows the wired icon and the status screen says "Connected to PC (USB)".

- **Right USB-C port only (OTG2/DC).** The H700 has a single USB controller that can act as a device (MUSB, `musb-hdrc.5.auto`, PHY0 with ID detection and VBUS from the charger input); the left port (OTG1) is on EHCI/OHCI, which are host-only. Software cannot change this.
- **Never automatic**: the port keeps its other uses (charging, USB devices on the handheld); the mode starts only from the app.
- **One connection at a time**: `rg35xxh-btpad.service` and `rg35xxh-usbpad.service` conflict; the app stops the other one first.

How it works:
- `rg35xxh-usbpad` (root, `rg35xxh-usbpad.service`) creates a USB gadget with configfs: VID/PID 045e:028e (the Xbox 360 wired controller, so Windows binds its driver), one vendor interface (class ff/5d/01) with interrupt IN 0x81 and OUT 0x01 and the Xbox 360 class descriptor (type 0x21, 17 bytes) that tells the driver which endpoints to use. Strings say "Handtop Controller".
- The interface is served from userspace through FunctionFS. The kernel's built-in FunctionFS rejects the 17-byte 0x21 descriptor (it only knows 0x21 as the 9-byte HID descriptor), and without it Windows loads its driver but never talks to the device. `usb_f_fs_xinput.ko` is a renamed copy of FunctionFS (filesystem `functionfs_xinput`, USB function `ffsxi`) that also accepts class descriptors on vendor-specific interfaces; it is generated from the ROCKNIX kernel's `f_fs.c` and built against the same tree by `build/06c-ffs-xinput.sh`.
- The OUT endpoint must be 0x01: that is the number the MUSB controller assigns, and the class descriptor must name the same one (0x02 left the driver silent).
- Input: the input daemon sends its gamepad events to `/run/rg35xxh-extpad.sock`, shared by both services (they introduce themselves with `hello bt` / `hello usb`); a report is sent to the PC on every change. Vibration (`00 08 00 <big> <small>` from the PC) goes back to the daemon as `rumble <big> <small>`, played at the stronger of the two on the single motor. Status for the screen: `/run/rg35xxh-extpad-status.sock` (`transport` = `usb`, `state` = `cable` | `connected`).
- Logs: `journalctl -u rg35xxh-usbpad`. On exit the gadget is removed (unbinding first wakes the threads blocked on the endpoints; leftovers of a crashed run are cleaned at the next start).

Tested 2026-10-21 with Windows 11: "Xbox 360 Controller for Windows" in Device Manager, the player-1 light command, ~1000 reports/s.

## Vibration safety

The motor is driven by ROCKNIX's joypad driver (`rocknix-singleadc-joypad`, memless force feedback on one PWM). Feeding it **endless effects** (replay length 0) that change rapidly froze the whole handheld three times during development (SSH dead, only a 10 s power-off helped); a web controller tester's "infinite vibration" over Wired Controller mode was enough to trigger it. So the input daemon never hands the driver an endless effect:

- External vibration (`rumble <big> <small>` from either service) is rounded to 8 strength levels, pre-uploaded as finite 0.5 s effects; while a level is wanted it is re-played every 0.4 s, so it stops by itself if anything goes wrong.
- The motor gets at most 10 updates per second, however fast the PC sends requests (the services also coalesce them to ≤20/s).
- Gamepad mode: effects uploaded by games are copied and queued through the same gate; a length-0 (endless) effect is capped to 1 s and refreshed the same way.

Tested: 1, 10 and 100 requests/s (100/s for 20 s, ~2000 requests) with the handheld staying responsive; then real "infinite" vibration from Windows.

## Planned

- Test the Xbox identity on Android, Linux, macOS/iOS.
