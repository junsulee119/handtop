# Handtop on more handhelds: plan

**Status (2026-11-18):** direction agreed with Jason (maintainer); nothing implemented yet. All work happens on the `device-support` branch. The phases below are all open; tick them off with the commits and tests that closed them.

This file is the working plan for running Handtop on handhelds other than the Anbernic RG35XX H. Profiles, evidence and test status for each model live next to it in `ports/`, so anyone can see from the repository where things stand.

## Agreed direction

1. **One branch, shared code, one profile per model.** No per-device branches or forks. Shared code stays in `build/`, `src/` and `overlay/`; what differs between models is data in a profile.
2. **One image per model**, and per variant where the bootloader needs it and the user can tell which one they have (DDR3 / DDR4 RAM, as today). Each image carries its model's device trees and profile, so U-Boot loads the right device tree without anyone choosing at boot.
3. **Variants a user can't tell apart** (the RG35XX H's regular and rev6 screen panels) are detected at boot by a check written for that model and switched on by its profile. Accurate profiles, built from official and community sources and then from community reports, are the core of this work.
4. **Hardware layer: ROCKNIX**, the same release as the RG35XX H image (currently 20261001). Targets are the models that release supports.
5. **First targets: 2–3 models**, chosen by Jason, on how easily they extend from the RG35XX H and how many people use them.
6. **"Test required" images.** New models are released once their image builds and passes the build checks, before anyone has run it on that hardware. Community testing moves each model on (see "Status and test reports").
7. **Every component follows the real screen size**: no 640×480 area centred on a bigger screen. Checked first on a virtual test platform made from the model's profile, then on hardware.
8. **On-device reporter app** (problem reports and feature suggestions to GitHub Issues, through ChatGPT Sites) ships before the first "Test required" release.
9. **A card moved to a different model is not supported** (it carries the wrong device tree). Later: a Handtop transfer app that moves a user's data from one device to another.
10. **Everything about this work is in `ports/`, in English.** An earlier Korean draft of this plan is kept locally and ignored by git.

## Layers

| Layer | Examples | Decided when |
|---|---|---|
| Global | Desktop, input logic, themes, apps, External Controller modes | Shared code, the same in every image |
| Model | Screen size and rotation, which input devices to take and how their buttons map, LEDs, sticks (0 / 1 / 2), Wi-Fi present, lid, USB port roles, which variant checks exist | Build time: the model's profile, installed into its image |
| Variant the user can tell (and the bootloader needs) | DDR3 / DDR4 | Build time: a separate image |
| Variant the user can't tell | RG35XX H regular / rev6 panel | Every boot: a check for that model, enabled by its profile |

Rules:
- Code never hardcodes a model value. It reads the profile, or asks the system for what can change while running (the actual screen size, an HDMI display).
- A check that reads hardware (a GPIO like the RG35XX H's PE6) runs only on models whose profile names it. Unknown or missing profile: change nothing and log it.
- Existing names (`rg35xxh-*` commands, `/etc/rg35xxh/`, boot-partition files such as `panel.txt`) stay. Renaming is not a goal of this work; if it is ever done, it gets its own migration.

### Where model values come from

- **The profile** is installed into the image at build time (proposed: `/etc/handtop/device.json`, plus a copy on the boot partition for reports and recovery). The exact format is decided in P2.
- **Programs** (input daemon, on-screen keyboard, apps, status screens) read the profile when they start, and take the screen size from the real output, which also covers HDMI.
- **Static configs** that can't read a file (labwc `rc.xml`, kanshi, Waybar's config) get their values either rendered at image build from the profile or rendered at session start the way the theme system already renders configs. Decided per file in P3.

## Build

- One shared Debian root filesystem per release; for each image only the bootloader (RAM type), device trees, the profile and the configs rendered from it differ.
- Measured on 2026-11-18 (v0.4.1 build): about 38 minutes for the first image, about 1.5 minutes for each further image that reuses the root filesystem. Three models with two RAM types each would take roughly 45–50 minutes.
- The per-image step must not change the shared root filesystem (it writes into that image's partition files), so images can't leak into each other.
- Each profile lists its valid combinations (RAM types, panels, device trees) explicitly. Nothing is generated as a cross product.
- **RG35XX H regression check:** the H image built from the branch must match the previous release's file for file, except for the profile and files deliberately changed. Checked with a file list and checksum diff.
- Proposed image names: `handtop-<date>-<version>-<model>.img.xz`, with `-DDR3` where needed. The RG35XX H's existing names may stay as they are; decided in P2.

## Screen sizes

Sizes to support: 640×480 (RG35XX H and others), 720×720 (CubeXX), 720×480 (RG34XX family), and rotated panels where a model needs them.

Known places that assume 640×480 or the `DSI-1` output (2026-11-18):
- configs: `overlay/etc/xdg/labwc/rc.xml`, `overlay/etc/xdg/kanshi/config`, `overlay/etc/xdg/waybar/config.jsonc`, `overlay/etc/mpv/mpv.conf`, `overlay/etc/mpv/scripts/handtop-osc.lua`;
- programs: `rg35xxh-display`, `rg35xxh-controller-screen`, `rg35xxh-drawer`, the input daemon (`daemon.py`), the Controls, Media and Theme apps;
- generators and tests: `tools/icons/gen_logo.py`, `tools/headless-test.sh`, `tools/osk-test.sh`, `tools/qemu-test.sh`, `tools/waybar-test.sh`.

Fixed pixel sizes that don't name 640×480 (the on-screen keyboard, the volume and brightness bar, the boot screen, wallpapers) need the same review. AGENTS.md's "Screen size is 640×480" rule changes in P0.

Every screen size is checked in all nine built-in themes; High contrast (larger text, thicker lines) is the hardest fit.

### Virtual test platform

Built from a profile, no hardware needed: the existing headless tools take a profile and run labwc at its screen size, open every app and status screen, and save screenshots per theme. QEMU boots the root filesystem at that size. What only hardware can show (panel, input devices, radios, power, motor) stays in the hardware test list.

## Phases

| # | Phase | Done when | Hardware |
|---|---|---|---|
| P0 | Rules and baseline | AGENTS.md says how "Test required" images relate to the tested-before-merge rule (it still applies in full to the RG35XX H and to shared code); the screen-size rule is updated; a list of what an RG35XX H must keep doing, used as the regression test | None |
| P1 | Choose targets | One evidence page per candidate in `ports/evidence/`: screen, controls, radios, RAM and panel variants, how its device tree differs from the H's, sources, open questions; plus community-use findings. Jason picks 2–3 | None |
| P2 | Profiles and build | Profile format and validation, the RG35XX H profile, profiles for the chosen models, the build loop for one image per model and variant, the regression check passes for the H | None |
| P3 | Code reads the profile | Input devices and mapping, outputs, LEDs and variant checks come from the profile (PE6 only on the H); every component follows the real screen size; the virtual test platform passes for every target in all nine themes; full on-device regression test on an RG35XX H (DDR4 and DDR3 where it matters) | RG35XX H |
| P4 | Reporter app | Report / suggest choice, auto-filled diagnostics, hiding log lines before sending, preview, offline queue with the same report ID on retry, labels and duplicate handling on the Sites side | RG35XX H |
| P5 | First "Test required" release | Images for the chosen models as a pre-release, `ports/README.md` status table, a short test checklist for testers | Community |
| P6 | Feedback and more models | Status updated from reports, profiles fixed from new data, more H700 models; then decide whether to start on RK3566 | Community |

## Candidates (H700, ROCKNIX 20261001)

Model IDs, board, panel and RAM variants are confirmed for each model before its profile is written.

| Model | Notes |
|---|---|
| RG35XX H | Current device; the regression baseline |
| RG CubeXX | 720×720 screen; device tree inherits from the RG35XX Plus's (four stick axes, right axis inverted in the device tree, motor, UART, RGB LED); a CubeXX owner offered to test on Reddit |
| RG40XX H | Joypad, UART and LED setup close to CubeXX |
| RG35XX Pro | Two sticks; check reuse of the stick input |
| RG40XX V | One stick |
| RG34XX SP | 720×480, lid |
| RG35XX Plus | No sticks |
| RG35XX SP | No sticks, lid |
| RG34XX | 720×480, no sticks |
| RG28XX | Small rotated screen, no built-in Wi-Fi |
| RG35XX 2024 | No built-in Wi-Fi, different controls |
| RG SP | Listed separately in the release and device trees; find out what it is first |

Without sticks, the right-stick scroll and L3 / R3 copy and paste need other controls; every UI must still work with the D-pad and A. Without built-in Wi-Fi, the desktop works but Bluetooth controller and streaming features are marked as not available.

Later platform: RK3566 (16 models in the same ROCKNIX release, GPT and Rockchip boot firmware, so the H700 boot layout and video engine setup don't carry over; RGB30 would reuse the square UI). Not considered: rebasing on KNULLI (its H700 support uses Allwinner's 4.9 kernel).

Sources: [ROCKNIX 20261001 release](https://github.com/ROCKNIX/distribution/releases/tag/20261001), [CubeXX device tree](https://raw.githubusercontent.com/ROCKNIX/distribution/20261001/projects/ROCKNIX/devices/H700/linux/dts/allwinner/sun50i-h700-anbernic-rgcubexx.dts), [RG40XX H device tree](https://raw.githubusercontent.com/ROCKNIX/distribution/20261001/projects/ROCKNIX/devices/H700/linux/dts/allwinner/sun50i-h700-anbernic-rg40xx-h.dts), [ROCKNIX H700 installation](https://rocknix.org/configure/h700-installation/).

### Using public sources

1. Record each model's official name, ROCKNIX release, device tree and what it inherits from, RAM and panel variants.
2. Downloaded images and extracted files go under `work/` (not tracked); record URL, version, date and SHA-256.
3. In `ports/evidence/<model>.md`, keep what a source says apart from what we conclude from it; anything unclear stays marked "not confirmed".
4. Don't mix device trees or modules built for another kernel into the image; use the ROCKNIX release's own files.
5. Check licences before shipping anything new from outside, and add it to the existing third-party notices.

## Status and test reports

| Status | Means |
|---|---|
| Test required | Built from documented sources, build checks passed; no report from real hardware yet |
| Basic confirmed | A tester confirmed boot, screen and basic input on a named image and variant |
| Features confirmed | Results recorded for the listed features on that image; untested and not-applicable features shown as such |
| Problem known | A reproduced problem on that version, variant and feature; shown next to what is already confirmed |

- Results are recorded per **image version and checksum × model × variant × feature**, with the reporter or report link and date. Results from older versions are kept but never copied onto a new version.
- Features: boot (first and later), panel and brightness, app layout; every button, stick direction and centre, pointer, scroll, on-screen keyboard, copy and paste; Wi-Fi, Bluetooth, audio and headphones; HDMI plug and unplug; video decoding per codec; log-out, restart, shut down, sleep and wake, screen off; External Controller modes (Bluetooth Xbox LE and classic, USB Xbox, USB Switch, Bluetooth Switch); vibration; battery saver.
- A short "it works" counts as a basic report and confirms nothing more.
- Build failures are listed with their cause, and that image is not released; other models' images are not held back.
- A serious problem in a released image: mark it, then pull or replace the download.
- What it takes to move a model from "Test required" to supported is set before the first release (P5).

## Reporter app

- Opens on two choices: **Report a problem** / **Suggest a feature**. Everything works with the D-pad and A, no keyboard needed.
- Problem: title and device info filled in from diagnostics (model, variant, image build, error codes); the user can add or change text but doesn't have to. A separate "recent events" view (wake from sleep, output changes, app starts) where any line or all of them can be replaced with `[REDACTED]` before sending, and restored. Typed text, clipboard, file names, network names and IP addresses are never collected.
- Suggestion: one line for the idea, optional details; model and build added.
- The final screen shows exactly what will be posted, with: "Thank you for taking the time to help Handtop. When you submit, everything below is posted as a public GitHub issue that anyone can read." and a **Submit as public issue** button.
- Online: shows the issue number and link. Offline: saved on the device and sent with the same report ID when online. Problems before the desktop starts: instructions on the boot partition.
- Sites side: size and rate limits, `bug` / `enhancement` labels, device and area labels from the report, `needs-triage` when unsure, the same report ID always gives the same issue, the GitHub credential kept as a Sites secret with the repository fixed in its config.

## Safety

The hardware-safety rules and the reliability checklist apply unchanged to every model. "Test required" only means nobody has run the image on that hardware yet; it is no exception to those rules. On models nobody has tested: no endless vibration, no writes to the power chip, no device hand-over that doesn't wait for the old owner, no hardware check the profile doesn't name.

## Open questions

- Profile format, validation, and how it relates to the user's own settings on the boot partition (P2).
- Which static configs are rendered at build and which at session start (P3).
- Controls for models without sticks; layout rules for square, wide and rotated screens; HDMI next to a non-640×480 panel (P3).
- Image names, release grouping and version names (P2 / P5).
- What "Basic confirmed", "Features confirmed" and supported each require (before P5).
- When to pull or replace a released image (before P5).
- How community reports are reviewed and the status table updated (before P5).
- Transfer app for moving to a new device (after P6).
