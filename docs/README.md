# Docs

How Handtop works on the RG35XX H. One document per app or background service; general topics below.

## Getting started

| File | Contents |
|---|---|
| [flashing.md](flashing.md) | Flashing the SD card and first boot |
| [building.md](building.md) | Building the image, testing and debugging |

## Apps (Apps menu / power button)

| File | Contents |
|---|---|
| [apps/external-controller.md](apps/external-controller.md) | External Controller: the handheld as a Bluetooth (Xbox) or USB game controller, status screen |
| [apps/display.md](apps/display.md) | External display (mini HDMI) and the Display app: layouts, resolution, refresh rate |
| [apps/files.md](apps/files.md) | Files: click-to-mount for the TF2 card and USB sticks, drive toasts |
| [apps/theme.md](apps/theme.md) | Theme app: dark / light |
| [apps/power-menu.md](apps/power-menu.md) | Power button, power menu, sleep and auto-sleep, shutdown |
| [apps/recenter-sticks.md](apps/recenter-sticks.md) | Re-center sticks: stick drift and the fix |
| [apps/enable-ssh.md](apps/enable-ssh.md) | Enable SSH |
| [apps/tailscale-login.md](apps/tailscale-login.md) | Tailscale VPN and login |

## Background services

| File | Contents |
|---|---|
| [services/input-daemon.md](services/input-daemon.md) | Input daemon: button mapping, desktop / gamepad modes, mode-change feedback |
| [services/on-screen-keyboard.md](services/on-screen-keyboard.md) | On-screen keyboard (part of the input daemon) |
| [services/osd.md](services/osd.md) | Volume / brightness bar |
| [services/boot-services.md](services/boot-services.md) | Boot and system services (hardware setup, first boot, Wi-Fi import, boot logs, ...) |

## System

| File | Contents |
|---|---|
| [architecture.md](architecture.md) | Overall approach: ROCKNIX hardware layer + Debian userspace |
| [desktop.md](desktop.md) | Desktop environment (labwc, Waybar, drawer), app list, browser choice, memory |
| [hardware.md](hardware.md) | Device facts verified from the ROCKNIX device tree; Wi-Fi power save |
| [boot-method.md](boot-method.md) | How the Debian root filesystem is booted with ROCKNIX's kernel; charging while off |
| [rocknix-quirks.md](rocknix-quirks.md) | ROCKNIX H700 device scripts and what is ported |
| [video-decode.md](video-decode.md) | Hardware video decoding (Cedrus) for Moonlight |
