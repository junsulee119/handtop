# External Controller

**Apps → External Controller** (`rg35xxh-external-controller`): use the handheld as a game controller for a PC, phone or Nintendo Switch. **Bluetooth** (BT Controller mode, `rg35xxh-btpad`; v0.2.0, an Xbox Wireless Controller since v0.3.0), **USB cable: Xbox** (Wired Controller mode, `rg35xxh-usbpad`) or **USB cable: Switch** (Switch Controller mode, `rg35xxh-usbpad --switch`), with a status screen (`rg35xxh-controller-screen`) while it runs. The app shows two cards: Bluetooth, and USB cable (its wired icon on top) split into two halves to pick from, Xbox above (a monitor and keyboard) and Switch below (a TV and a gamepad); those two icons are generic on purpose, no brand logos (`tools/icons/gen_usb_target_icons.py`). Icons follow the Handtop theme (`-light` files).

## Bluetooth: BT Controller mode

### Use

1. On the handheld: **Apps → External Controller**. The handheld switches to BT Controller mode (the taskbar's input-mode icon shows a controller with signal waves, blue with rainbow stripes) and appears as **"Handtop Gamepad"**.
2. First time only, on the other device: Bluetooth → add device → **Handtop Gamepad** (Windows: Settings → Bluetooth & devices → Add device → Bluetooth). No PIN.
3. Play. Check it on Windows with `joy.cpl` ("Set up USB game controllers").
4. Press **Select + Start + L1 + R1** together to return to desktop mode; this also ends BT Controller mode. (Same combo as Moonlight's quit; holding Start no longer exits here, so a long Start press reaches the other device.)

BT Controller mode is separate from gamepad mode: in gamepad mode the controls drive a virtual Xbox pad *on the handheld* (for Moonlight, games); in BT Controller mode they go only to the other device, and apps on the handheld see no controller. The input-mode icon in the taskbar shows which one is on: mouse (desktop), controller (gamepad), controller with signal waves on rainbow stripes (BT Controller).

Next time, just open BT Controller again: the paired device reconnects by itself within a few seconds.

**Re-pairing:** remove "Handtop Gamepad" on the other device **and** on the handheld (Bluetooth tray → Devices), then pair again. If only one side forgets the pairing, the other refuses it.

**Updating from v0.2.0:** the handheld now presents itself as an Xbox controller, and Windows remembers the old (generic) description per pairing. Remove "Handtop Gamepad" on the PC once and pair it again. Windows may also list a second "Handtop Gamepad" with a phone icon: that is the handheld's normal Bluetooth identity; ignore or remove it.

### What the other device sees

An **Xbox Wireless Controller** (Series X|S, model 1914) over Bluetooth LE. Windows loads its own Xbox driver for it (Device Manager: "Bluetooth LE XINPUT compatible input device"), so XInput-only games work directly, and **game vibration plays on the handheld's motor** (through the same safety gate as Wired Controller mode, see "Vibration safety"). Buttons go by position, Xbox layout: the handheld's bottom button is Xbox A, the right one B, left X, top Y; Select = View, Start = Menu. Battery level is reported too.

Tested on Windows 11 (2026-10-21): driver, all controls, vibration. Android and Linux have drivers for this controller too (not tested yet).

Fallback: `RG35XXH_BTPAD_PROFILE=generic` in the service's environment (`systemctl edit rg35xxh-btpad`) gives the v0.2.0 behaviour, a generic BLE gamepad (buttons 1–10, hat, X/Y, Z/Rz, Rx/Ry for the triggers) with no vibration; re-pair after switching.

### Trade-off: classic Bluetooth pauses

While BT Controller mode is on, the handheld's Bluetooth is **BLE only**. Accessories connected *to* the handheld over **BLE** keep working; **classic Bluetooth** accessories (many keyboards and mice, older Xbox One controllers) pause and come back when the mode ends.

Why: with classic Bluetooth on, Windows also derives a classic pairing key from the BLE pairing and later reconnects over classic Bluetooth, where there is no gamepad (it connects, but no input arrives).

### How it works

- `rg35xxh-btpad` (root, `rg35xxh-btpad.service`, not started at boot) registers a GATT application with BlueZ over D-Bus: HID service 0x1812 (report map, input report with notifications, output report, HID information, control point, protocol mode) and battery service 0x180F; a BLE advertisement (gamepad appearance 0x03C4, 30–60 ms interval); and a just-works pairing agent. Newly paired devices are marked trusted.
- **Xbox identity.** Windows picks its Xbox BLE driver (`xinputhid.inf`) by the PnP ID in the Device Information service, and only for product 0x0B13 or 0x0B20–0x0B27 from vendor 0x045E. BlueZ publishes that service itself (default `1d6b:0246`, from `DeviceID` in `main.conf`), so on start btpad writes a copy of `/etc/bluetooth/main.conf` with `DeviceID = usb:045e:0b13:0509` to `/run/rg35xxh-btpad/main.conf`, adds a runtime drop-in (`/run/systemd/system/bluetooth.service.d/50-rg35xxh-btpad.conf`, `bluetoothd -f` that file) and restarts bluetoothd; on exit it removes both and restarts it again (`ExecStopPost=rg35xxh-btpad --restore` does the same after a crash). That restart is queued (`systemctl --no-block`), not waited for: during `systemctl stop rg35xxh-btpad` (a switch to Wired mode, shutdown) systemd holds it until btpad's stop has finished, and waiting deadlocked until the 90 s stop timeout killed btpad (found and fixed 2026-10-26; now a stop takes ~2.5 s). Stress test: on and off 20 times, Wi-Fi unaffected (340/340 pings, worst 13.5 ms). The unit only `Wants=` bluetooth.service, so the restart does not stop it.
- **Report map**: the real controller's descriptor, byte for byte (283 bytes; from Mystfit/ESP32-BLE-CompositeHID, MIT, identical to the BLE dump in DJm00n/ControllersInfo). Input report 1, 16 bytes: X Y Z Rz as unsigned 16 bit (centre 32768), brake/accelerator 10 bit, hat 1–8 (0 = centred), 15 button bits (A 0, B 1, X 3, Y 4, LB 6, RB 7, View 10, Menu 11, Guide 12, LS 13, RS 14), Record. Output report 3, 8 bytes, written by Windows for vibration: enable bits, magnitudes 0–100 (left trigger, right trigger, strong, weak), duration and start delay in 10 ms, loop count. btpad turns it into `rumble <big> <small>` for the input daemon (≤ 20/s) and ends it after duration × loops by itself. Windows caches the report map per pairing.
- Input: it listens on `/run/rg35xxh-extpad.sock` (Unix seqpacket, root:input 0660). In BT Controller mode the input daemon uses its gamepad mapping but sends each pad event there (one evdev event per packet, `struct "<HHi"`: type, code, value) instead of creating the local virtual Xbox pad. btpad sends 16-byte HID reports (≤ 125/s); the status screen still gets the 9-byte generic layout.
- The **External Controller** app (`rg35xxh-bt-controller`) starts the service (allowed without a password by `/etc/polkit-1/rules.d/50-rg35xxh-btpad.rules`) waits for the socket and sends `SIGUSR2` to the input daemon, which connects to it and switches to BT Controller mode (flag file `$XDG_RUNTIME_DIR/rg35xxh-bt-mode`, read by autosleep and the taskbar indicator).
- Classic Bluetooth is switched off with `btmgmt` on start and back on (with SSP) on exit. The service stops by itself when the daemon disconnects (Select + Start + L1 + R1) or never connects (60 s); if the service stops first, the daemon returns to desktop mode.
- **Latency / link speed.** Windows 11 first connects with a 45 ms connection interval: ~22 link slots per second, one report each. A moving stick produces more reports than that, so they queued up in bluetoothd and the radio and the PC got them 0.1–0.3 s late (felt above ~40 reports/s; buttons alone were fine). While the mode is on, bluetoothd's runtime config also sets `[LE] MinConnectionInterval = 6`, `MaxConnectionInterval = 12` (7.5–15 ms); as the peripheral, the kernel then asks the PC for that range after connecting. Windows rejects the request at first but switches to 15 ms on its own moments later (btmon, 2026-10-24), and the lag is gone. Reports are paced to one per 15 ms (~66/s, each with the newest state), so they cannot queue up even at the slowest interval asked for. Only with the Xbox profile (the runtime config is written for its identity).
- **rfkill.** Switching the adapter off and on (identity restart, BR/EDR off) can make the Bluetooth tray applet (blueman) soft-block the radio; powering on then fails ("Failed to set mode") and advertising is rejected. `rg35xxh-btpad` clears a Bluetooth soft block on start, after each off/on and before powering on (retried 3 times).
- Logs: `journalctl -u rg35xxh-btpad`.

Tested 2026-10-21 with Windows 11: pairing, all controls in `joy.cpl`, automatic reconnection after leaving and re-entering the mode; with the Xbox identity: Xbox driver, vibration, identity restored when the mode ends.

## Status screen

While the mode is on, the handheld's screen shows a full-screen status page (`rg35xxh-controller-screen`, opened by the External Controller app, closed when the mode ends):

- **Connection:** "Ready to pair" (with how to pair), "Waiting for <PC>" (a paired PC that is not connected yet; it reconnects by itself) or "Connected to <PC>".
- **Live input:** a pixel-art drawing of the RG35XX H, proportioned from Anbernic's product photo (large centred screen, D-pad upper left, left stick lower left, X/A/B/Y upper right with their printed colours, right stick lower right, round Select/Start above the D-pad and face buttons, power LED, L1/L2 and R1/R2 on the top edge). Pressed buttons light up, the stick caps move, and L2/R2 fill.
- **Link info** on the drawn handheld's screen: HID reports sent per second (0 while nothing changes) and the BLE signal strength (`btmgmt conn-info`; strong ≥ −70 dBm, good ≥ −85 dBm, else weak).
- **Handheld battery** (top right) and **"Select + Start + L1 + R1 to stop"**.

**Themes:** follows the Handtop theme (read when the screen opens). Dark: dark background, the handheld drawn solid like the real black one. Light: light background (`#dfe4ec`), dark text, the light taskbar icons, and the handheld as a hologram in deep-blue ink (translucent body, outlines, controls fill in when pressed). Text on the drawn handheld's screen keeps its light colours in both themes.

It takes no input (every button goes to the other device) and hides the mouse pointer. `rg35xxh-controller-screen --demo` shows it with a fixed sample state. Volume (Vol) and brightness (F + Vol) still work in this mode: the input daemon handles those keys itself in every mode, and F is never sent to the other device.

Data: `rg35xxh-btpad` publishes JSON lines on `/run/rg35xxh-extpad-status.sock` (root:input 0660): `transport`, `state` (pairing / waiting / connected), `device`, `rssi`, `rate`, `report` (the 9-byte HID report, at most ~30 updates/s). The host is the paired device that is not itself an input device (BlueZ icon not `input-*`, no HID service); the last connected one is remembered in `/var/lib/rg35xxh/btpad-last-host`.


## USB cable: Wired Controller mode

**Apps → External Controller → USB cable: Xbox.** The handheld becomes a **wired Xbox 360 controller** for a PC: Windows uses its built-in Xbox driver (no install), XInput-only games work directly, and the PC reads the controls at ~1000 reports/s. Vibration requested by the game is played on the handheld's motor. The handheld charges from the PC at the same time. Select + Start + L1 + R1 ends it, like BT Controller mode; the taskbar shows the wired icon and the status screen says "Connected to PC (USB)".

- **Right USB-C port only (OTG2/DC).** The H700 has a single USB controller that can act as a device (MUSB, `musb-hdrc.5.auto`, PHY0 with ID detection and VBUS from the charger input); the left port (OTG1) is on EHCI/OHCI, which are host-only. Software cannot change this.
- **Never automatic**: the port keeps its other uses (charging, USB devices on the handheld); the mode starts only from the app.
- **One connection at a time**: `rg35xxh-btpad.service`, `rg35xxh-usbpad.service` and `rg35xxh-switchpad.service` conflict; the app stops the others first.

How it works:
- `rg35xxh-usbpad` (root, `rg35xxh-usbpad.service`) creates a USB gadget with configfs: VID/PID 045e:028e (the Xbox 360 wired controller, so Windows binds its driver), one vendor interface (class ff/5d/01) with interrupt IN 0x81 and OUT 0x01 and the Xbox 360 class descriptor (type 0x21, 17 bytes) that tells the driver which endpoints to use. Strings say "Handtop Controller", so `joy.cpl` lists it as "Controller (Handtop Controller)" (the Xbox driver's naming; a real pad says "XBOX 360 For Windows"). Kept on purpose (Jason, 2026-10-26); Device Manager shows "Xbox 360 Controller for Windows".
- The interface is served from userspace through FunctionFS. The kernel's built-in FunctionFS rejects the 17-byte 0x21 descriptor (it only knows 0x21 as the 9-byte HID descriptor), and without it Windows loads its driver but never talks to the device. `usb_f_fs_xinput.ko` is a renamed copy of FunctionFS (filesystem `functionfs_xinput`, USB function `ffsxi`) that also accepts class descriptors on vendor-specific interfaces; it is generated from the ROCKNIX kernel's `f_fs.c` and built against the same tree by `build/06c-ffs-xinput.sh`.
- The OUT endpoint must be 0x01: that is the number the MUSB controller assigns, and the class descriptor must name the same one (0x02 left the driver silent).
- Input: the input daemon sends its gamepad events to `/run/rg35xxh-extpad.sock`, shared by both services (they introduce themselves with `hello bt` / `hello usb`); a report is sent to the PC on every change. Vibration (`00 08 00 <big> <small>` from the PC) goes back to the daemon as `rumble <big> <small>`, played at the stronger of the two on the single motor. Status for the screen: `/run/rg35xxh-extpad-status.sock` (`transport` = `usb`, `state` = `cable` | `connected`).
- Logs: `journalctl -u rg35xxh-usbpad`. On exit the gadget is removed (unbinding first wakes the threads blocked on the endpoints; leftovers of a crashed run are cleaned at the next start). A start that fails halfway (no UDC, FunctionFS refused, an endpoint not opening) removes it too: everything from the first step that touches the USB controller is inside one `try` whose `finally` tears down. Test hook: `RG35XXH_USBPAD_TEST_FAIL=1` fails right after binding.

Tested 2026-10-21 with Windows 11: "Xbox 360 Controller for Windows" in Device Manager, the player-1 light command, ~1000 reports/s.

## USB cable: Switch Controller mode

**Apps → External Controller → USB cable: Switch.** The handheld becomes a **wired Nintendo Switch controller**. It poses as HORI's licensed wired pad (Pokkén Tournament DX Pro Pad), which the Switch accepts with no handshake and no setting; on a PC it is an ordinary HID gamepad that SDL (Steam, Ryujinx and other emulators) knows by its ID. Select + Start + L1 + R1 ends it, as in the other modes; the taskbar shows the wired icon and the status screen says "Connected to Switch or PC (USB)" plus the Home / Capture hint.

**Connecting** (right USB-C port only, as for Wired Controller mode):
- **Switch in the dock:** an A-to-C cable from a USB-A port of the dock to the handheld.
- **Switch without the dock (handheld mode, Lite):** a USB-C OTG adapter (C plug to A socket) in the Switch, then the same A-to-C cable. A C-to-C cable does not work: the handheld's port lacks the USB-C resistors that make a USB-C host switch on its power (the same reason PD chargers don't charge it). The handheld then charges from the Switch's battery.
- If the Switch doesn't react, open **Controllers → Change Grip/Order** and press L + R.
- **Ryujinx (PC):** choose the pad ("Handtop Controller") as a **Pro Controller**, then rebind A, B, X and Y once in Configure: its default mapping swaps them for this pad (SDL already reports it by Nintendo labels, and Ryujinx's default swaps Xbox-style positions on top). Home and Capture arrive (`joy.cpl` buttons 13 / 14) but Ryujinx has no Home menu, so they do nothing there.

**Controls:**

| Handheld | Switch |
|---|---|
| A / B / X / Y | A / B / X / Y (the handheld's labels are printed where the Switch has them, so by label and by position agree) |
| L1 / R1, L2 / R2 | L / R, ZL / ZR (digital, as on the handheld) |
| Select / Start | − / + |
| L3 / R3, D-pad, sticks | Same |
| **F (tap)** | **Home** |
| **F (hold 0.6 s)** | Home held (quick settings), until F is released |
| **F + Select** | **Capture** (held as long as Select: hold for a video) |
| F + Vol | Brightness, as always (no Home) |

F does this only in Switch Controller mode. In the Xbox modes F stays unforwarded: Home there would be the Xbox Guide button, which opens the Game Bar on Windows.

**Not available:** vibration (the HORI pad has no motor, so the Switch sends none), motion controls (the handheld has no motion sensor), NFC / amiibo, and the player lights. All of these need the Pro Controller's own protocol (see "Options considered").

How it works:
- `rg35xxh-switchpad.service` runs `rg35xxh-usbpad --switch`. It conflicts with `rg35xxh-btpad.service` and `rg35xxh-usbpad.service` (one connection at a time) and uses the same gadget path, FunctionFS mount, sockets and teardown as Wired Controller mode, so a crash of either leaves nothing the other can't clean up.
- **Gadget:** VID/PID 0f0d:0092, bcdDevice 1.00, class at interface level; one HID interface (03/00/00) with the HID descriptor, interrupt IN 0x81 and OUT 0x01 (64 bytes, 5 ms at full speed, 1 ms at high speed). It runs at high speed: the real pad is full speed, but the MUSB controller refuses to start a gadget limited to full speed (`max_speed = full-speed` → `udc_start` −22, tested 2026-10-28). Strings: "Handtop" / "Handtop Controller".
- **Report descriptor:** HORI's, 86 bytes (as used by the open Switch fight-stick projects): 16 buttons, a 4-bit hat plus 4 padding bits, X Y Z Rz (left X/Y, right X/Y) 0–255 with centre 128, one vendor byte; an 8-byte vendor output report, read and ignored.
- **Input report**, 8 bytes: buttons as a 16-bit little-endian field (Y 0, B 1, A 2, X 3, L 4, R 5, ZL 6, ZR 7, − 8, + 9, L3 10, R3 11, Home 12, Capture 13), hat (0 = up, clockwise, 8 = centred), LX LY RX RY (Y grows downwards), vendor 0. Sent on every change and at least every 8 ms, as a real pad streams its state (the write returns when the host has read it).
- **ep0:** the HID class requests come to the service through FunctionFS (`SETUP` events): GET_DESCRIPTOR for the report and HID descriptors, GET_REPORT (current state), GET_IDLE / GET_PROTOCOL, and SET_REPORT / SET_IDLE / SET_PROTOCOL (acknowledged). Anything else is stalled. Wired Controller mode still stalls everything on ep0, as before.
- **Input daemon:** the service introduces itself with `hello switch`; the daemon then turns on F's Home / Capture ([../services/input-daemon.md](../services/input-daemon.md)) and uses the `rg35xxh-wired-mode` flag (taskbar icon, autosleep, Bluetooth tray behave as in Wired Controller mode). Home is sent as `BTN_MODE`, Capture as `KEY_RECORD`.
- Logs: `journalctl -u rg35xxh-switchpad`.

Options considered:
- **Pro Controller emulation** (057e:2009): would add vibration and the player lights. It needs Nintendo's USB handshake, replies to the Switch's subcommands and fake SPI flash contents (calibration, colours), and the user has to turn on "Pro Controller Wired Communication". Much more code to get right and keep working across firmware updates, for features the handheld mostly lacks (no motion sensor). Kept as a possible later step.
- **Bluetooth:** not done yet (next step). The Switch pairs only a Pro Controller / Joy-Con, over classic Bluetooth (BT Controller mode is BLE), with Nintendo's handshake; the open implementations (joycontrol, nxbt) are fragile across Switch firmware versions. Wired came first because it needs none of that.
- **Home on a combo instead of F:** any combo of the controls the Switch sees would take a button combination away from games. F is never sent otherwise, so it was free; the cost is that an accidental F tap opens the Home menu.

Tested 2026-10-28 on a DDR4 RG35XX H with Windows 11: enumerates as "Handtop Controller" (configured, high speed, ~110–125 reports/s, ~2 % of one core while idle); every button, the hat and both sticks in `joy.cpl` (A = 3, B = 2, X = 4, Y = 1; F tap / hold = 13, F + Select = 14); unplug and replug; Select + Start + L1 + R1; switching straight to Wired Controller mode and back; starting it twice; recovery after the service was killed (the next start removes the leftover gadget). Ryujinx: Mario Kart 8 Deluxe played fine as a Pro Controller (after rebinding A/B/X/Y once). Unit tests for F / Home / Capture. **Not tested on a real Switch** (no unit at hand); the identity and report descriptor are the ones the open Switch pad projects use on real consoles.

## Vibration safety

The motor is driven by ROCKNIX's joypad driver (`rocknix-singleadc-joypad`, memless force feedback on one PWM). Feeding it **endless effects** (replay length 0) that change rapidly froze the whole handheld three times during development (SSH dead, only a 10 s power-off helped); a web controller tester's "infinite vibration" over Wired Controller mode was enough to trigger it. So the input daemon never hands the driver an endless effect:

- External vibration (`rumble <big> <small>` from either service) is rounded to 8 strength levels, pre-uploaded as finite 0.5 s effects; while a level is wanted it is re-played every 0.4 s, so it stops by itself if anything goes wrong.
- The motor gets at most 10 updates per second, however fast the PC sends requests (the services also coalesce them to ≤20/s).
- Gamepad mode: effects uploaded by games are copied and queued through the same gate; a length-0 (endless) effect is capped to 1 s and refreshed the same way.

Tested: 1, 10 and 100 requests/s (100/s for 20 s, ~2000 requests) with the handheld staying responsive; then real "infinite" vibration from Windows.
