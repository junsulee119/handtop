# Desktop

## Decision: labwc (Wayland)

A stacking window manager with a traditional taskbar look, plus small separate tools for panel, launcher and power menu, styled to behave like a classic desktop.

### Why labwc over XFCE (X11)

- **Per-output scaling** — the 640×480 handheld screen and a 1080p HDMI display can each have their own scale. X11 has one global scale. Key for the HDMI use case.
- **Lighter** — estimated ~120–200 MB idle vs ~250–350 MB for XFCE on 1 GB RAM.
- **Fuller GPU use** — every frame composited on the GPU (Panfrost); no tearing; video frames can go to the screen without CPU copies.
- Wayland is the current standard; XFCE's Wayland support is incomplete.

Trade-off accepted: more setup work (panel, launcher, power menu, settings assembled from separate tools). Old X11-only apps run through XWayland.

### Why not Sway

Sway (ROCKNIX's default) is a keyboard-driven tiling WM — unsuitable for gamepad/mouse-only use.

## Hardware acceleration

- OpenGL/GLES via Panfrost (Mesa) for the compositor and GL apps (browser rendering, Moonlight).
- **Hardware video decode for Moonlight** (H.264/HEVC, up to 1080p60) via the Cedrus V4L2 stateless decoder — see `video-decode.md`. Other players (mpv, browsers) still decode on the CPU.

## Shell components: Waybar + nwg-drawer + wlogout

| Role | Tool | Notes |
|---|---|---|
| Panel | **Waybar** | Bottom taskbar, classic-desktop styling: open windows, clock, battery, network, volume, tray |
| Launcher | **nwg-drawer** | Full-screen app icon grid — usable with mouse/D-pad (type-to-search launchers rejected: no keyboard) |
| Power menu | **wlogout** | Full-screen large buttons: Shut down / Log out / Restart / Sleep. Opened by Power (tap) |
| Notifications | **mako** | |

Chosen over LXQt-on-labwc (heavier) and sfwbar (smaller community) for low RAM and gamepad-friendly large targets.

### Session details (implemented)

- Boot → getty auto-login on tty1 → labwc. Logging out restarts the session; after 3 failed starts a shell is left on tty1.
- System-wide defaults in `/etc/xdg/` (labwc, waybar, mako, foot, kanshi); per-user overrides go in `~/.config/`.
- Normal windows open **maximized** (640×480 screen); dialogs keep their size.
- Panel: `☰ Apps` (launcher) · open windows · tray · volume · network · battery · clock · `⏻` (power menu).
- Launcher: `rg35xxh-drawer` (4 columns, 56 px icons, no categories/file search). Power menu: `rg35xxh-power-menu`.
- Physical keyboard: Super+D apps, Super+Enter terminal, Super+E files, Super+X power menu, Alt+F4 close, Print screenshot.
- **No xdg-desktop-portal**: it delayed Waybar startup (portal activation timeouts) and is only needed for screen sharing/Flatpak; GTK apps use their own file dialogs.
- Audio: speaker starts at 100 % on a fresh system (`/etc/wireplumber/wireplumber.conf.d/50-rg35xxh.conf`; WirePlumber default is 40 %); the codec DAC and Line Out are set to 100 % by `rg35xxh-hwinit`.
- Memory: zram swap (50 % of RAM, zstd, priority 100) plus a 2 GB swap file `/swapfile` on the SD card (priority 10, created on first boot by `rg35xxh-swapfile`). Chromium flags in `/etc/chromium.d/50-rg35xxh`; uBlock Origin Lite force-installed by policy (`/etc/chromium/policies/managed/ublock-origin-lite.json`, downloaded on first launch).
- Component logs: `~/.local/state/session/*.log`, labwc: `~/.local/state/labwc.log`.

### External display (mini HDMI) — verified 2026-10-08

- Works with hot-plug: a 1080p monitor came up at 1920×1080 60 Hz, scale 1; taskbar, pointer and windows all fine. No HDMI audio device (only the analog codec appears in ALSA).
- kanshi profiles: `handheld` (DSI-1 only, runs `rg35xxh-display apply`), `docked` (HDMI-A-1 + DSI-1, runs `rg35xxh-display connected`).
- **Display app** (`rg35xxh-display`, one drawer entry "Display"; replaced the three "Display: …" entries in 2026-10). On connect it opens on the **handheld** as a layer-shell overlay; while it is open only the handheld screen is on (flag `$XDG_RUNTIME_DIR/rg35xxh-display-picker`), so the pointer cannot end up on the monitor. A 5 s countdown, restarted by any pointer movement or key, then keeps the saved layout; picking a card applies at once. Unplugging closes it. Drawn with cairo (pixel-art illustrations of each layout), follows the dark/light theme; `--preview FILE` renders it to a PNG.
- Layouts (`~/.config/rg35xxh/display-mode`, also `rg35xxh-display set monitor|extend|mirror`):
  - **monitor** (default): handheld screen off (backlight off too). Pressing X turns it on as a full-screen keyboard panel — see `keyboard.md`.
  - **extend**: handheld screen **below** the monitor, centred (x = (monitor width − 640) / 2, y = monitor height): the pointer crosses off the monitor's bottom edge in its middle third.
  - **mirror**: the monitor switches to 640×480 at the same position as the handheld, so both show the same picture (the monitor scales it up).
- **Resolution / refresh rate**: lists of the monitor's modes (largest first, refresh rates per resolution; the preferred mode marked) with scroll bars. **Test** turns the monitor on in that mode, apart from the handheld (x = 4000, no shared edge), and asks "Keep this mode?" for 15 s; otherwise it switches back. Kept modes are stored per monitor (make + model + serial) in `~/.config/rg35xxh/display-modes.json`; otherwise the preferred mode. Refresh rates are passed exactly as listed (`1920x1080@239.998Hz`): wlr-randr calls a rounded value an "unknown mode". Verified 2026-10-21: 1080p 240 Hz on a Hansung TFG24F24P runs a real 570 MHz TMDS / TCON clock (60 Hz: 148.5 MHz).
- **Pointer speed per screen**: after each layout change the tool writes the enabled outputs and a speed factor (diagonal ÷ 800, the handheld's; 1080p ≈ 2.75) to `$XDG_RUNTIME_DIR/rg35xxh-pointer-layout`. The input daemon follows the pointer over that layout (its own relative motion, clamped like wlroots) and scales the stick / D-pad speed by the factor of the screen it is on (`display_speed_scale` in `input.conf`, 0 = off). It moves the pointer to the layout's top-left corner when a two-screen layout starts, so the estimate starts exact; its virtual mouse has no libinput acceleration (labwc `rc.xml`), so the estimate stays exact. Motion from other mice is not seen.

## Core use

| Need | Decision |
|---|---|
| Remote desktop to PC | **Moonlight** (PC runs Sunshine). Hardware decoding: 1080p60 HEVC smooth on 5 GHz Wi-Fi |
| Parsec | **Not possible** — no Linux ARM64 client |
| External display | mini HDMI, per-output scaling |
| Keyboard/mouse | USB (host port, hub OK) or Bluetooth, alongside the gamepad controls |
| On-screen keyboard | Custom, D-pad navigable, English only (see `input-mapping.md`) |
| CJK text | **Display only** (Noto CJK fonts). No input method |

## App list

Selection rule: light apps for 1 GB RAM; Qt apps preferred where equal, since moonlight-qt already loads Qt.

| Purpose | Package(s) | Why |
|---|---|---|
| Remote desktop | `moonlight-qt` (official Moonlight Cloudsmith repo, debian/trixie arm64) | Core use case |
| Browser | `chromium` + uBlock Origin Lite | Smoothest browser tested on this device (see below). Heavy browsing → use the PC via Moonlight |
| File manager | `thunar`, `udisks2`, `gvfs`, `exfatprogs`, `dosfstools` | Light, Wayland-capable, familiar. Other drives (the TF2 card, USB sticks) appear under **Devices** in Thunar's sidebar and mount with a tap, no password (udisks2 + polkit for the local session), at `/media/<user>/<label>`. The kernel reads exFAT, FAT, ext4, NTFS and btrfs, so e.g. a Knulli card's SHARE partition works. Plugging one in shows a toast ("SD card inserted", size in GiB and volumes; tap opens Files), pulling it out another ("SD card removed"; "removed without ejecting" with a warning if a volume was still mounted): udev starts `rg35xxh-drive-notify@<disk>.service` / `rg35xxh-drive-removed@<disk>.service`, which notify the active seat0 user (`/usr/local/sbin/rg35xxh-drive-notify`, drive info kept in `/run/rg35xxh-drives/`). The ⏏ button unmounts; for SD cards a wrapper (`/usr/local/sbin/eject`) makes the eject step succeed, since an SD slot has nothing to eject and the real `eject` fails after a good unmount ("Failed to eject"). Handtop's own boot/root partitions are hidden from the list (`/etc/udev/rules.d/72-rg35xxh-udisks.rules`, by label). Cost: ~15 MB (PSS) for udisksd + the gvfs daemons, and none until first used: udisks2 is not started at boot (`build/09-services.sh`) but D-Bus activated when Thunar or a file dialog first asks for drives (verified 2026-10-22 with a stock-firmware card in TF2) |
| Terminal | `foot` | Lightest Wayland terminal; stable app_id `foot` for copy/paste detection |
| Text editor | `mousepad` (GUI), `micro` + `nano` (terminal) | Simple; micro supports mouse and Ctrl+C/V |
| Python | `python3`, `python3-venv`, `pipx` | System pip is blocked by Debian; use venvs |
| SSH | `openssh-client`, `openssh-server`, `tmux`, `mosh` | SSH server off by default; Apps → **Enable SSH** sets your own password and turns it on. tmux/mosh survive dropped connections |
| Networking | `network-manager`, `network-manager-gnome` (nm-applet) | Wi-Fi from tray; `nmtui` fallback |
| VPN | `tailscale` (official repo pkgs.tailscale.com, debian/trixie) | Reach the device / PC from anywhere; tray icon via `tailscale systray` |
| Bluetooth | `bluez`, `blueman` | |
| Audio | `pipewire`, `wireplumber`, `pipewire-pulse`, `pavucontrol` | |
| Clipboard | `wl-clipboard` | Required by L3/R3 copy/paste |
| Brightness / volume | `brightnessctl`, `wireplumber` (`wpctl`) | Used by F + Vol and Vol keys; the pop-up bar is Handtop's own `rg35xxh-osd` (`src/osd`: plain C Wayland client, ~2 MB, built by `build/07b-osd.sh`) |
| Screenshots | `grim`, `slurp` | |
| Viewers | `imv` (images), `qpdfview` (PDF), `mpv` (video, CPU decode) | |
| Archives | `xarchiver` | |
| System | `htop`, `git`, `zram-tools`, `systemd-timesyncd` | zram = compressed RAM swap |
| Fonts | `fonts-noto-core`, `fonts-noto-cjk`, `fonts-noto-color-emoji` | CJK and emoji rendering |

Locale `en_US.UTF-8`, timezone UTC (change with `sudo timedatectl set-timezone Area/City`).

Heavy web browsing is the expected weak point (1 GB RAM).

## Tailscale (added 2026-10-09)

- Installed from Tailscale's official Debian repository; `tailscaled` runs at boot (kernel TUN + WireGuard available, so normal kernel mode, not userspace networking).
- `rg35xxh-tailscale-operator.service` makes the desktop user Tailscale **operator** (`tailscale set --operator=<user>`), so the tray and `tailscale up/down` work without sudo.
- **Log in:** Apps → **Tailscale login** (`rg35xxh-tailscale-login`) opens a terminal with `tailscale up --qr`: scan the QR code with a phone (or open the link) and approve. Login persists across reboots; nothing secret is stored on the boot partition.
- **Tray:** `tailscale systray` is started from the labwc autostart (grey when logged out).
- Defaults: no exit node, routes from other nodes not accepted, MagicDNS on (`/etc/resolv.conf` → 100.100.100.100 while connected).

## Browser choice (v0.1.3)

Tested 2026-10-17 on the device: fresh profile per browser, 20 s of scrolling on Wikipedia and on naver.com (ad-heavy), scored 1–5 by hand, CPU and free memory measured during the scroll.

| Browser | Score (wiki / naver) | CPU | Free RAM |
|---|---|---|---|
| Firefox ESR 153 + uBlock Origin (until v0.1.2) | 2 / 1 | 88 % / 90 % | ~210 MB |
| Firefox + uBlock Origin Lite | 2.5 / 1.5 | 83 % / 77 % | 196–308 MB |
| Firefox, no ad blocker | 2.9 / 2 | 64 % / 69 % | 232–300 MB |
| Epiphany (WebKitGTK) | 2.7 / 2.7 | 39 % / 60 % | 324–456 MB |
| Chromium 155, no ad blocker | 3.5 / 3 | 43 % / 37 % | 374–463 MB |
| **Chromium 155 + uBlock Origin Lite** | **4 / 3** | **38 % / 40 %** | **379–434 MB** |

Earlier rounds showed Firefox's rendering path (GPU/CPU WebRender, Wayland/X11), CPU governor, smooth scrolling and frame rate made no noticeable difference; full uBlock Origin alone took 110–270 MB in Firefox's extension process.


## Light theme (dual theme)

**Apps → Theme** (or `rg35xxh-theme dark|light`, `rg35xxh-theme --get`): dark (default) or light. The choice is one file, `~/.config/rg35xxh/theme`, read by every themed part; a switch applies live.

| Part | How it follows the theme |
|---|---|
| Waybar | `rg35xxh-themed waybar` (autostart) adds `-s /etc/xdg/waybar/style-light.css` (imports `style.css`, overrides the colours); the Theme app restarts it |
| Taskbar icons | input mode and battery scripts pick the `-light` PNGs |
| Wallpaper | `rg35xxh-themed swaybg`: `#1e2430` / `#dfe4ec` |
| Notifications | `rg35xxh-themed mako`: `/etc/xdg/mako/config` / `config-light` |
| Window title bars | labwc theme `Handtop` (`/usr/share/themes/Handtop/labwc/themerc`). Light: the Theme app links `/usr/share/themes/Handtop-Light/labwc/themerc` as `~/.local/share/themes/Handtop/labwc/themerc` (user themes win) and runs `labwc --reconfigure`. `themerc-override` only keeps the title-bar padding |
| App drawer | `rg35xxh-drawer` copies `/etc/xdg/nwg-drawer/handtop-<theme>.css` into `~/.config/nwg-drawer` (nwg-drawer's `-s` only takes a name there) |
| Handtop app icons | light: per-user copies of their `.desktop` files in `~/.local/share/applications` with the `-light` icon (marked `X-Handtop-Theme=light`, removed again for dark) |
| Power menu | `rg35xxh-power-menu`: `/etc/wlogout/style.css` / `style-light.css` (buttons stay mid-blue: wlogout's icons are light) |
| GTK apps | `gsettings` color-scheme + `gtk-application-prefer-dark-theme` in `~/.config/gtk-3.0/settings.ini`; open apps may need a restart |

Your own `~/.config/waybar/style.css` or `~/.config/mako/config` still wins over both themes.

Not themed yet (stay dark): terminal (foot), volume/brightness bar (`rg35xxh-osd`), on-screen keyboard, External Controller status screen (it already draws from `PALETTES`, so light is new palette entries). Possible later: follow the time of day.
