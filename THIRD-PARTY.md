# Third-party components

The MIT license in `LICENSE` covers only this project's own files (build scripts, overlay
configuration, `src/`, `tools/`, docs). The SD card image also contains the following,
each under its own license.

## Hardware layer from ROCKNIX (`20261001`)

Taken unmodified from the official image
`ROCKNIX-H700.aarch64-20261001-DDR4.img.gz` (https://github.com/ROCKNIX/distribution/releases/tag/20261001):

| Component | License | Source |
|---|---|---|
| Linux kernel 7.2.0 (`KERNEL`), kernel modules, device trees | GPL-2.0 | ROCKNIX `20261001` tag: `projects/ROCKNIX/packages/linux` (linux 7.2 + patches), `projects/ROCKNIX/devices/H700/` |
| U-Boot (SPL + U-Boot) | GPL-2.0+ | ROCKNIX `20261001` tag, U-Boot package and H700 device files |
| Firmware blobs (Wi-Fi/Bluetooth, etc.) | Various redistributable vendor licenses | ROCKNIX `20261001` tag / linux-firmware |

`build/01-fetch-rocknix.sh` downloads that exact image (SHA-256 checked) and
`build/02-extract-rocknix.sh` extracts these parts.

## Built by this project from GPL sources

| Component | License | Source |
|---|---|---|
| `sunxi-cedrus.ko` (video decoder module) | GPL-2.0 | linux 7.2 (kernel.org) + ROCKNIX `20261001` kernel patches + `build/kernel/0001-cedrus-add-h616-variant.patch` (Chen-Yu Tsai, upstream "arm64: allwinner: h616: Support Video Engine" v3) + `build/kernel/0002-cedrus-64-byte-stride.patch` (this project) + the cedrus patches in `build/kernel/libreelec/` (Jernej Skrabec, from LibreELEC.tv master `f59641e`, 2026-11-01, `0438` added 2026-11-05 and rebased, plus one of this project's), built by `build/06b-cedrus.sh` |
| `v4l2-vp9.ko` (VP9 probability-adaptation helpers) | GPL-2.0 | linux 7.2 (kernel.org), with `CONFIG_V4L2_VP9` selected by `build/kernel/libreelec/0421-...`, built by `build/06b-cedrus.sh` |
| Video-engine device-tree overlay | GPL-2.0 / MIT (as upstream sunxi DTs) | `build/dts/rg35xxh-video-engine.dtso`, based on patch 7/7 of the same series |
| nwg-drawer v0.7.5 | MIT | https://github.com/nwg-piotr/nwg-drawer, built by `build/04b-nwg-drawer.sh` |
| FFmpeg 7.1.5 with the V4L2 request-API patchset, plus a local patch registering the decoders under the DRM device type | GPL-2.0-or-later | https://github.com/FFmpeg/FFmpeg tag `n7.1.5` (commit `3a0867c2bfda4a4d4309ca1a8cbdc6175e67f587`) + the patchset from https://github.com/Kwiboo/FFmpeg (`f46e514491172d15bd74b4abb1814cd2f05a763e..fad85d9c76611c09b561167ab405c667a0dcdeb7`, branch `v4l2-request-n7.1.3`) + `build/patches/ffmpeg-v4l2request-drm.patch`, built by `build/04c-v4l2-ffmpeg.sh` |

## Fonts in the Retro, Glass, Pocket and Signal themes

In the SD card image since v0.4.0 (`/usr/share/rg35xxh/themes/handtop-<theme>/fonts/`) and in the repo
under `src/theme/themes/handtop-<theme>/fonts/`, unmodified, with their licences in each theme's
`fonts/LICENSE.txt`; an exported copy of the theme carries them too.

| Font | License | Source |
|---|---|---|
| W95FA (Retro, `fonts/ui.otf`), by Alina Sava | SIL Open Font License 1.1 | [FontsArena](https://fontsarena.com/w95fa-by-alina-sava/) |
| Inter 4.1, variable (Glass, `fonts/ui.ttf`), by Rasmus Andersson and the Inter project | SIL Open Font License 1.1 | [rsms/inter](https://github.com/rsms/inter) |
| Space Grotesk, variable (Signal, `fonts/ui.ttf`), by Florian Karsten | SIL Open Font License 1.1 | [Space Grotesk](https://github.com/floriankarsten/space-grotesk) via Google Fonts |
| Space Mono (Signal, `fonts/mono.ttf`), by Colophon Foundry | SIL Open Font License 1.1 | [Space Mono](https://github.com/googlefonts/spacemono) via Google Fonts |
| Pixelify Sans, variable (Pocket, `fonts/ui.ttf`), by Stefie Justprince | SIL Open Font License 1.1 | [Pixelify Sans](https://github.com/eifetx/Pixelify-Sans) via Google Fonts |
| VT323 (Pocket, `fonts/mono.ttf`), by Peter Hull | SIL Open Font License 1.1 | [VT323](https://github.com/phoikoi/VT323) via Google Fonts |
| PxPlus IBM VGA 8x16 (`fonts/mono.ttf`), from The Ultimate Oldschool PC Font Pack v2.2 by VileR | CC BY-SA 4.0 | [int10h.org](https://int10h.org/oldschool-pc-fonts/) |

## Data from other projects

| What | License | Source |
|---|---|---|
| Xbox Wireless Controller (model 1914) BLE HID report descriptor, 283 bytes, in `overlay/usr/local/sbin/rg35xxh-btpad` | MIT | [Mystfit/ESP32-BLE-CompositeHID](https://github.com/Mystfit/ESP32-BLE-CompositeHID), `XboxDescriptors.h` (`XboxOneS_1914_HIDDescriptor`), read from a physical controller; matches the BLE dump in [DJm00n/ControllersInfo](https://github.com/DJm00n/ControllersInfo). How Windows picks its driver (PnP ID, product IDs): [WikDra/esp32-hid-gamepad-bridge](https://github.com/WikDra/esp32-hid-gamepad-bridge) (MIT) |
| wlr-layer-shell protocol description, `src/osd/protocol/wlr-layer-shell-unstable-v1.xml` (used to build `rg35xxh-osd`) | HPND-style (notice inside the file) | [wlroots/wlr-protocols](https://gitlab.freedesktop.org/wlroots/wlr-protocols), Copyright © 2017 Drew DeVault |

Original notice of ESP32-BLE-CompositeHID (MIT):

```
Software License Agreement (MIT License)

Copyright (c) 2021 lemmingDev - https://github.com/lemmingDev

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
```

## Packages

- **Debian 13 "trixie"** packages, unmodified from deb.debian.org; licenses in `/usr/share/doc/*/copyright` on the device. The FFmpeg libraries are the exception: `libavcodec61`, `libavdevice61`, `libavfilter10`, `libavformat61`, `libavutil59`, `libpostproc58`, `libswresample5` and `libswscale8` are replaced by the build above and held with `apt-mark`, so an upgrade cannot overwrite them.
- **Moonlight (moonlight-qt)**, GPL-3.0, from the official Moonlight repository (dl.cloudsmith.io). Source: https://github.com/moonlight-stream/moonlight-qt
- **Tailscale**, BSD-3-Clause, from the official repository (pkgs.tailscale.com). Source: https://github.com/tailscale/tailscale

## Thanks

- ROCKNIX for the H700 kernel, U-Boot and device support this project stands on.
- MrJackSpade/RG35XXP-XFCE for showing that a desktop on these devices is practical.
