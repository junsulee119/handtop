# Toasts for USB and Bluetooth devices, the charger and the monitor (v0.3.9)

A short notification when something is plugged in or pulled out, so it is clear the handheld saw it.

| Event | Toast | Shown for |
|---|---|---|
| USB device plugged in | `<Type> connected` + its name, e.g. "Keyboard and mouse connected · Logitech USB Receiver" | 5 s |
| USB device pulled out | `<Type> disconnected` + its name | 4 s |
| Charger plugged in / out | "Charging" / "Charger unplugged" + "Battery NN%" (each replaces the last one) | 4 s |
| Battery full while charging | "Fully charged" + "Battery NN%. You can unplug the charger." (once per charge) | 6 s |
| Bluetooth device connected / disconnected | `<its name> connected` / `<its name> disconnected` | 4 s |
| Monitor unplugged | "Monitor disconnected · back to the handheld screen" | 4 s |

Plugging in a monitor has no toast: the Display picker opening is the feedback. USB drives and SD cards keep their own toasts ([../apps/files.md](../apps/files.md)); a device that is only storage gets none here, so a stick never shows two.

## USB devices and the charger

- **Rules:** `/etc/udev/rules.d/73-rg35xxh-device-notify.rules`. udev only starts `rg35xxh-device-notify@<what>.service` (`usb-add:<name>`, `usb-remove:<name>`, `charger`); the oneshot runs `/usr/local/sbin/rg35xxh-device-notify` and notifies the active seat0 user, as the drive toasts do. Nobody logged in: no toast.
- **Type:** from the device's interfaces, after `udevadm settle` (drivers and input devices appear after the device). In this order: controller (an input device udev marks as joystick), camera (class 0e; before audio, a webcam has a microphone), audio (01), keyboard and mouse (a wireless receiver), keyboard, touchpad, mouse, Wi-Fi adapter (a network interface with `wireless`), network adapter (any other network interface), Bluetooth adapter (e0), phone or camera (06, MTP/PTP), printer (07), hub (09), other input device (03), else "USB device". Only storage (08): skipped. Root hubs (vendor 1d6b) are the controllers themselves: skipped.
- **Name:** the device's own `manufacturer` + `product` strings (the manufacturer left out when the product already starts with it); without them the USB ID database's names; else `USB ID vvvv:pppp`. Cut to 60 characters.
- **No driver:** when none of its interfaces has a driver bound, the toast adds "No driver for it in Handtop." (for example a Wi-Fi dongle whose chip ROCKNIX's kernel has no module for).
- **Hubs:** one toast per device, as chosen: a hub with a keyboard and a mouse shows three. Unplugging the hub shows one per device too.
- **Removal:** what was shown is recorded at add in `/run/rg35xxh-usb/<name>`, since the device's strings are gone once it is. A device back within 1 s (a cable that bounces) counts as not removed. Devices present at boot are recorded too (before the desktop, so no toast), so pulling them out later still says which one went.
- **Charger:** `axp20x-usb` `online`, read twice 0.5 s apart (still changing: the next event decides). The last state is in `/run/rg35xxh-charger` with the toast's ID; the first reading after boot (udev's `add`) is only recorded. Only sysfs is read; nothing is written to the power chip. The low-battery countdown has its own "Charging · Shutdown cancelled" toast; both can show.

## Fully charged

In the low-battery watcher (`rg35xxh-lowbattery --watch`, every 30 s, so up to 30 s late): while charging, when the battery's `status` is `Full` or `capacity` is 100. Once per charge (`$XDG_RUNTIME_DIR/rg35xxh-lowbattery-full`, removed when the charger is unplugged). Already full when the watcher starts (logged in on the charger): recorded, no toast. No extra process ([../apps/power-menu.md](../apps/power-menu.md)).

## Bluetooth devices

In `rg35xxh-bluetooth --watch`, which already follows BlueZ's signals for the taskbar icon (no extra process): a `Connected` change on a device (`org.bluez.Device1`, `/org/bluez/hci*/dev_*`) starts a background check 1.5 s later, which shows the toast only if the device is still in that state, so a device that drops and comes straight back (some BLE mice and keyboards when idle) shows nothing. The name is the device's BlueZ alias ("Bluetooth device" if it was already removed). Skipped while Bluetooth Manager is open (blueman's applet shows its own toasts) and during an External Controller Bluetooth mode (`$XDG_RUNTIME_DIR/rg35xxh-bt-mode`; its status screen shows the host).

## Monitor unplugged

`rg35xxh-display connected` (kanshi, docked profile) leaves `$XDG_RUNTIME_DIR/rg35xxh-docked` holding labwc's PID; `rg35xxh-display apply` from the handheld-only profile clears it and, if it was from this session, shows the toast 0.5 s after the layout change ([../apps/display.md](../apps/display.md)). A flag left from an earlier session (logged out while docked) does not count.

## Testing

Offline (2026-11-06), the script with a fake sysfs, udevadm, loginctl and runuser: wireless receiver → keyboard and mouse, controller, driverless dongle with no strings (`USB ID 0bda:8179` + no driver), USB stick (no toast), hub, webcam with microphone (camera), root hub (skipped), removal, a bounce (nothing), bad names (nothing); charger: first reading only recorded, plug, same state again (nothing), unplug (replaces the last toast), no battery reading (title only).

On the device (2026-11-06, v0.3.8 + these files): a Bluetooth device connecting and disconnecting with Bluetooth Manager closed, charger in and out, a wireless receiver (CX 2.4G Wireless Receiver → "Keyboard and mouse") in and out, HDMI unplugged, and a sleep with the receiver plugged in (no burst of toasts on wake). The charger sent no events while idle (20 s of `udevadm monitor`).
