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
- **Hardware video decode for Moonlight** (H.264/HEVC, up to 1080p60) via the Cedrus V4L2 stateless decoder — see [video-decode.md](video-decode.md). Other players (mpv, browsers) still decode on the CPU.

## Bluetooth without blueman's tray: trade-offs

Since 2026-10-26 blueman's applet and tray no longer run all the time (they took ~55 MB of the
~1 GB; Handtop's own icon + watcher take ~1 MB). What that changes:

- **Pairing is started from the handheld.** blueman's pairing agent (PIN / passkey prompts) runs
  only while Bluetooth Manager is open. Pairing from the handheld's Bluetooth Manager works as
  before; a phone or PC that starts pairing *to* the handheld while the window is closed gets no
  prompt (and may fail). External Controller mode is not affected (it has its own agent).
- **No tray menu.** blueman's right-click menu (quick connect to recent devices, turn Bluetooth
  off, send files) is gone; the same things are in Bluetooth Manager (tap the icon). Already paired
  devices still reconnect by themselves (that is BlueZ / the device, not the applet).
- **No connection pop-ups** ("connected to …") from blueman's applet while the window is closed.
- **No receiving files over Bluetooth (OBEX)** while the window is closed (blueman's transfer
  service lives in the applet). Rarely used on a handheld.
- **Remembering "Bluetooth off" is now Handtop's job.** blueman's applet used to remember the
  on / off choice; bluetoothd alone switches the adapter on at every start (`AutoEnable`, its
  default). `rg35xxh-bluetooth --watch` saves it (`~/.local/state/rg35xxh-bluetooth-power`, not
  during External Controller mode's set-up) and switches Bluetooth off again at log-in, so it is
  briefly on during boot.
- **The icon is a Waybar module, not a tray item**: it sits right after the input-mode icon,
  before Wi-Fi and Tailscale, and has no right-click menu.
- blueman's own tray icon is switched off in the gsettings defaults (`org.blueman.general
  plugin-list`: `!StatusIcon`, plus `!ShowConnected` and `!StatusNotifierItem`, which would load
  it again), so opening Bluetooth Manager does not add a second Bluetooth icon.

## Session start and log out

Auto-login on tty1 starts labwc (`/etc/profile.d/zz-rg35xxh-session.sh`); **Log out** ends labwc, getty logs in again and a fresh session starts. labwc runs `/etc/xdg/labwc/autostart` in its own process group. Wayland clients (Waybar, applets, …) end with labwc, but the helpers that are not (input daemon loop, battery icon animation, Tailscale tray) would outlive it: so each autostart first stops the previous session's process group (its id is kept in `$XDG_RUNTIME_DIR/rg35xxh-autostart.pgid`) and resets the failed-start counter that `zz-rg35xxh-session.sh` uses (3 failed starts in a row leave a shell on tty1). Found 2026-10-26: after a log-out the taskbar showed two Tailscale icons and two input daemons were running.

## Shell components: Waybar + nwg-drawer + wlogout

| Role | Tool | Notes |
|---|---|---|
| Panel | **Waybar** | Bottom taskbar, classic-desktop styling: open windows, clock, battery, tray |
| Launcher | **nwg-drawer** | Full-screen app icon grid — usable with mouse/D-pad (type-to-search launchers rejected: no keyboard) |
| Power menu | **wlogout** | Full-screen large buttons: Sleep, Restart / Log out, Shut down. Opened by Power (tap) |
| Notifications | **mako** | |

Chosen over LXQt-on-labwc (heavier) and sfwbar (smaller community) for low RAM and gamepad-friendly large targets.

### Session details (implemented)

- Boot → getty auto-login on tty1 → labwc. Logging out restarts the session; after 3 failed starts a shell is left on tty1.
- System-wide defaults in `/etc/xdg/` (labwc, waybar, mako, foot, kanshi); per-user overrides go in `~/.config/`.
- Normal windows open **maximized** (640×480 screen); dialogs keep their size.
- Panel: **Apps** (launcher; blue block with a pixel-art 3×3 app grid) · open windows · input-mode icon · Bluetooth icon · tray (Wi-Fi, Tailscale; pixel-art icons from `tools/icons`) · battery · clock · power (red pixel-art power symbol on the bar, opens the power menu). Even gaps: 8 px between status icons, 12 px around the battery / clock text. Volume and brightness show in the pop-up bar ([services/osd.md](services/osd.md)).
- Launcher: `rg35xxh-drawer` (4 columns, 56 px icons, no categories/file search). Power menu: `rg35xxh-power-menu` ([apps/power-menu.md](apps/power-menu.md)). Theme: [apps/theme.md](apps/theme.md).
- Physical keyboard: Super+D apps, Super+Enter terminal, Super+E files, Super+X power menu, Alt+F4 close, Print screenshot.
- **No xdg-desktop-portal**: it delayed Waybar startup (portal activation timeouts) and is only needed for screen sharing/Flatpak; GTK apps use their own file dialogs.
- Audio: speaker starts at 100 % on a fresh system (`/etc/wireplumber/wireplumber.conf.d/50-rg35xxh.conf`; WirePlumber default is 40 %); the codec DAC and Line Out are set to 100 % by `rg35xxh-hwinit`.
- Memory: zram swap (50 % of RAM, zstd, priority 100) plus a 2 GB swap file `/swapfile` on the SD card (priority 10, created on first boot by `rg35xxh-swapfile`). Chromium flags in `/etc/chromium.d/50-rg35xxh`; uBlock Origin Lite force-installed by policy (`/etc/chromium/policies/managed/ublock-origin-lite.json`, downloaded on first launch).
- Component logs: `~/.local/state/session/*.log`, labwc: `~/.local/state/labwc.log`.

## Core use

| Need | Decision |
|---|---|
| Remote desktop to PC | **Moonlight** (PC runs Sunshine). Hardware decoding: 1080p60 HEVC smooth on 5 GHz Wi-Fi |
| Parsec | **Not possible** — no Linux ARM64 client |
| External display | mini HDMI, per-output scaling, Display app ([apps/display.md](apps/display.md)) |
| Keyboard/mouse | USB (host port, hub OK) or Bluetooth, alongside the gamepad controls |
| On-screen keyboard | Custom, D-pad navigable, English only (see [services/on-screen-keyboard.md](services/on-screen-keyboard.md)) |
| CJK text | **Display only** (Noto CJK fonts). No input method |

## App list

Selection rule: light apps for 1 GB RAM; Qt apps preferred where equal, since moonlight-qt already loads Qt.

| Purpose | Package(s) | Why |
|---|---|---|
| Remote desktop | `moonlight-qt` (official Moonlight Cloudsmith repo, debian/trixie arm64) | Core use case |
| Browser | `chromium` + uBlock Origin Lite | Smoothest browser tested on this device (see below). Heavy browsing → use the PC via Moonlight |
| File manager | `thunar`, `udisks2`, `gvfs`, `exfatprogs`, `dosfstools`, `eject` | Light, Wayland-capable, familiar. Other drives (TF2 card, USB sticks) mount with a tap — see [apps/files.md](apps/files.md) |
| Terminal | `foot` | Lightest Wayland terminal; stable app_id `foot` for copy/paste detection |
| Text editor | `mousepad` (GUI), `micro` + `nano` (terminal) | Simple; micro supports mouse and Ctrl+C/V |
| Python | `python3`, `python3-venv`, `pipx` | System pip is blocked by Debian; use venvs |
| SSH | `openssh-client`, `openssh-server`, `tmux`, `mosh` | SSH server off by default; Apps → **Enable SSH** ([apps/enable-ssh.md](apps/enable-ssh.md)) sets your own password and turns it on. tmux/mosh survive dropped connections |
| Networking | `network-manager`, `network-manager-gnome` (nm-applet) | Wi-Fi from tray; `nmtui` fallback |
| VPN | `tailscale` (official repo pkgs.tailscale.com, debian/trixie) | Reach the device / PC from anywhere; see [apps/tailscale-login.md](apps/tailscale-login.md) |
| Bluetooth | `bluez`, `blueman` | Taskbar icon: `rg35xxh-bluetooth` (Waybar `image#bluetooth`, Handtop pixel icons: off / on / connected; `--watch` follows BlueZ over D-Bus, ~1 MB). Click: Bluetooth Manager (blueman), with blueman's applet (pairing agent) running only while it is open. Replaced blueman's always-running applet + tray (~55 MB) on 2026-10-26; trade-offs below |
| Audio | `pipewire`, `wireplumber`, `pipewire-pulse`, `pavucontrol` | |
| Clipboard | `wl-clipboard` | Required by L3/R3 copy/paste |
| Brightness / volume | `brightnessctl`, `wireplumber` (`wpctl`) | Used by F + Vol and Vol keys; the pop-up bar is Handtop's own `rg35xxh-osd`, see [services/osd.md](services/osd.md) |
| Screenshots | `grim`, `slurp` | |
| Viewers | `imv` (images), `qpdfview` (PDF), `mpv` (video, CPU decode) | |
| Archives | `xarchiver` | |
| System | `htop`, `git`, `zram-tools`, `systemd-timesyncd` | zram = compressed RAM swap |
| Fonts | `fonts-noto-core`, `fonts-noto-cjk`, `fonts-noto-color-emoji` | CJK and emoji rendering |

Locale `en_US.UTF-8`, timezone UTC (change with `sudo timedatectl set-timezone Area/City`).

Heavy web browsing is the expected weak point (1 GB RAM).

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
