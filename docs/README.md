# Docs

How Handtop works on the RG35XX H: SSH, Moonlight remote desktop, local apps,
external display over mini HDMI.

| File | Contents |
|---|---|
| [architecture.md](architecture.md) | Overall approach: ROCKNIX hardware layer + Debian userspace |
| [hardware.md](hardware.md) | Device facts verified from the ROCKNIX device tree |
| [boot-method.md](boot-method.md) | How the Debian root filesystem is booted with ROCKNIX's kernel |
| [rocknix-quirks.md](rocknix-quirks.md) | ROCKNIX H700 device scripts and what is ported |
| [desktop.md](desktop.md) | Desktop environment (labwc), apps, HDMI, Tailscale, memory |
| [input-mapping.md](input-mapping.md) | Button mapping for desktop and gamepad modes |
| [keyboard.md](keyboard.md) | On-screen keyboard: layout, controls, placement |
| [video-decode.md](video-decode.md) | Hardware video decoding (Cedrus) for Moonlight |
| [power-and-sleep.md](power-and-sleep.md) | Power button, shutdown, sleep, charging while off |
| [bt-controller.md](bt-controller.md) | BT Controller mode: the handheld as a Bluetooth LE gamepad |
| [flashing.md](flashing.md) | Flashing the SD card and first boot |
| [building.md](building.md) | Building the image, testing and debugging |
