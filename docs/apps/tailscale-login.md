# Tailscale login

Tailscale VPN (added 2026-10-09) and the **Tailscale login** app (`rg35xxh-tailscale-login`).

## How it works

- Installed from Tailscale's official Debian repository; `tailscaled` runs at boot (kernel TUN + WireGuard available, so normal kernel mode, not userspace networking).
- `rg35xxh-tailscale-operator.service` makes the desktop user Tailscale **operator** (`tailscale set --operator=<user>`), so the tray and `tailscale up/down` work without sudo.
- **Log in:** Apps → **Tailscale login** (`rg35xxh-tailscale-login`) opens a terminal with `tailscale up --qr`: scan the QR code with a phone (or open the link) and approve. Login persists across reboots; nothing secret is stored on the boot partition.
- **Tray:** `tailscale systray` is started from the labwc autostart (grey when logged out).
- Defaults: no exit node, routes from other nodes not accepted, MagicDNS on (`/etc/resolv.conf` → 100.100.100.100 while connected).


App icon: Tailscale's own tray icon (connected state), read from `tailscale systray` over D-Bus; see `tools/icons/README.md`.
