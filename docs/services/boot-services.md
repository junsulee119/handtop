# Boot and system services

Small services that run at boot or in the background. All are in `overlay/` (scripts in `/usr/local/sbin`, units in `/etc/systemd/system`) and enabled by `build/09-services.sh` unless noted.

| Service | What it does |
|---|---|
| `rg35xxh-hwinit` | Hardware setup at every boot, ported from ROCKNIX's H700 quirks: CPU/GPU governors, audio DAC and Line Out levels, LEDs. See [../rocknix-quirks.md](../rocknix-quirks.md) |
| `rg35xxh-resize-root` | First boot: grows the root partition and filesystem to fill the SD card (once) |
| `rg35xxh-swapfile` | 2 GB swap file on the SD card behind zram (priority 10); created on first boot after the resize, enabled on every boot |
| `rg35xxh-ssh-keygen` | First boot: generates the SSH host keys (the image ships without them) |
| `rg35xxh-wifi-import` | Every boot: imports `wifi.txt` from the boot partition into NetworkManager, then blanks the password in the file ([../flashing.md](../flashing.md)) |
| `rg35xxh-bootlog` (+ timers) | Diagnostic log on the boot partition (`logs/boot-NNNN.txt`, last 5 kept), 60 s after boot and when the desktop session is up |
| `rg35xxh-tailscale-operator` | Makes the desktop user Tailscale operator, so the tray and `tailscale up/down` work without sudo ([../apps/tailscale-login.md](../apps/tailscale-login.md)) |
| `rg35xxh-btpad`, `rg35xxh-usbpad` | External Controller modes; started by the app only, never at boot ([../apps/external-controller.md](../apps/external-controller.md)) |
| `rg35xxh-drive-notify@`, `rg35xxh-drive-removed@` | Toasts for plugged / removed drives, started by udev ([../apps/files.md](../apps/files.md)) |
| `rg35xxh-lowpower` | Low-power state of the old "Screen off" mode (not in the power menu any more; [../apps/power-menu.md](../apps/power-menu.md)) |

Desktop-session programs (labwc autostart, as the user): the input daemon ([input-daemon.md](input-daemon.md)), the volume/brightness bar ([osd.md](osd.md)), Waybar with `rg35xxh-battery --animate` (battery icon) and `rg35xxh-inputmode` (input-mode icon), swayidle → `rg35xxh-autosleep`, `rg35xxh-lowbattery --watch` (low battery during Screen off), mako, nm-applet, `rg35xxh-bluetooth --watch` (Bluetooth icon), `tailscale systray`, kanshi → `rg35xxh-display`.
