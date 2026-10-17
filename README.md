# Handtop

A full Debian desktop for the **Anbernic RG35XX H**. It turns the handheld into a pocket
Linux computer: SSH, Moonlight remote desktop, Tailscale, a web browser, a terminal,
an external monitor over mini HDMI, and everything else Debian's arm64 archive offers.

<p align="center">
  <img src="media/handheld.webp" width="560" alt="RG35XX H running Handtop: Firefox on the labwc desktop with the Waybar taskbar">
</p>

- **Hardware layer:** kernel, U-Boot, device trees and firmware from [ROCKNIX](https://github.com/ROCKNIX/distribution) `20261001` (kernel 7.2)
- **Userspace:** Debian 13 "trixie" (arm64)
- **Desktop:** labwc (Wayland) + Waybar + nwg-drawer + wlogout, 640×480 on the built-in screen
- **Controls:** a custom input daemon turns the gamepad into mouse + keyboard, with an on-screen keyboard

Status: **v0.1.1**, developed and tested on the RG35XX H.

## Features

- Desktop mode by default: stick / D-pad pointer, A/B clicks, right-stick scrolling, L1/R1/R2 = Esc/Enter/Backspace, L3/R3 = copy/paste
- On-screen keyboard (X), navigable with the D-pad
- Gamepad mode (tap Start) presents an Xbox 360 pad, e.g. for Moonlight; hold Start 1 s to go back
- **Moonlight** with **hardware video decoding** (H.264/HEVC up to 1080p60) via the Cedrus decoder
- **Tailscale** with tray icon and a QR-code login launcher
- **HDMI**: hot-plug, monitor-only / extend / mirror modes, keyboard panel on the handheld when the monitor is the only screen
- Sleep (s2idle) from the power menu or after 10 min idle; Power tap wakes
- Charges while switched off (power button boots)
- Wi-Fi set up from Windows/macOS by editing `wifi.txt` on the boot partition
- Chromium with uBlock Origin Lite (installed automatically on first launch when online); zram + 2 GB swap file
- Boot logs written to the FAT partition, readable from any PC

Full control map: [docs/input-mapping.md](docs/input-mapping.md).

## Install

You need a microSD card (16 GB or larger) and balenaEtcher or Rufus.

1. Download `handtop-<date>-v0.1.2.img.xz` and its `.sha256` from the Releases page. If that image does nothing at all on power-on (no LED), your unit has DDR3 RAM: use the `-DDR3` image instead.
2. Flash the `.img.xz` directly (no need to unpack). If Windows offers to format the card afterwards, choose **Cancel**.
3. Optional: on the `RG35XXHBOOT` drive, fill in `wifi.txt` (SSID, password, country).
4. Put the card in the **TF1** (left) slot and power on. The first boot takes longer (the system grows to fill the card).

**Login:** user `rg`, password `rg35xxh` (used for sudo). **SSH is off by default**:
open Apps → **Enable SSH**, which makes you choose your own password first.

Screen garbled or black? Your unit may have the newer panel: copy
`device_trees\sun50i-h700-anbernic-rg35xx-h-rev6-panel.dtb` over `dtb.img` on the boot partition.
Details: [docs/flashing.md](docs/flashing.md).

## External display

Plug a monitor into the mini HDMI port at any time (hot-plug). Choose what happens from the Apps menu:

- **Monitor only:** the desktop moves to the monitor; the handheld screen becomes a full-size on-screen keyboard
- **Extend:** the monitor and the handheld screen form one desktop
- **Mirror:** both show the same picture

Resolution: **tested at 1920×1080 60 Hz**. The HDMI driver allows pixel clocks up to 594 MHz, so higher modes (e.g. 1440p60, 1080p120, up to 4K60 on paper) may work but are untested, and the desktop gets slower at high resolutions. The monitor's preferred mode is used automatically; to change it (in a terminal):

```sh
wlr-randr                                        # list modes
wlr-randr --output HDMI-A-1 --mode 1920x1080@60  # pick one
wlr-randr --output HDMI-A-1 --scale 2            # bigger UI on 4K screens
```

There is no HDMI audio.

## Good to know

- The device has 1 GB RAM; for heavy websites and video, Moonlight to a PC works best.
- Hardware video decoding (H.264/HEVC) is used by Moonlight; other players decode on the CPU.
- For streaming, 5 GHz Wi-Fi gives the smoothest result.
- Bluetooth devices pair from the tray (Blueman); USB keyboards and mice work through the host port.
- If a stick drifts, Apps → **Re-center sticks** recalibrates it.
- Sleep uses about 5–6 % battery per hour.

## Build it yourself

See [docs/building.md](docs/building.md). In short, on a Debian/Ubuntu host:

```sh
sudo bash build/build-rootfs.sh
sudo bash build/10-image.sh        # → work/out/handtop-<date>-<version>.img.xz
```

## Repository layout

- `build/` — numbered build scripts, package lists, kernel patch and device-tree overlay
- `overlay/` — files copied into the root filesystem
- `src/inputd/` — input daemon and on-screen keyboard (Python), with unit tests
- `boot-files/` — files placed on the FAT boot partition
- `tools/` — test helpers (QEMU boot test, headless desktop screenshots, Wi-Fi import test)
- `docs/` — how everything works and why

## Credits and license

Built on the work of the ROCKNIX, Debian, labwc, Waybar, nwg-drawer, wlogout, Moonlight and
Tailscale projects, and the upstream Linux H616 video-engine patches. Inspired by
[MrJackSpade/RG35XXP-XFCE](https://github.com/MrJackSpade/RG35XXP-XFCE).
See [THIRD-PARTY.md](THIRD-PARTY.md).

This project's own scripts, configuration and code are under the [MIT License](LICENSE).
Third-party components keep their own licenses.
