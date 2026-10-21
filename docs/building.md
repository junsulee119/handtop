# Building the Image

## Build host

- Debian or Ubuntu, x86_64 or arm64, root (or sudo).
- About 20 GB free disk, internet access (HTTPS to deb.debian.org, security.debian.org,
  dl.cloudsmith.io, pkgs.tailscale.com, github.com, go.dev, cdn.kernel.org, developer.arm.com).
- On x86_64 the arm64 root filesystem is built under qemu-user emulation; an arm64 host is faster.
- Go for nwg-drawer: `00-host-deps.sh` downloads the Go release pinned in `build/config.sh` (SHA-256 checked) into `work/tools/go`, on x86_64 and arm64 hosts. To use your own Go ≥ 1.25 instead, set `GO_TOOLCHAIN`.
- Windows cannot build the image (no Linux filesystems or ARM package scripts).

## Steps

```sh
sudo bash build/build-rootfs.sh     # 00 host deps … 09 services: downloads ROCKNIX, builds the Debian rootfs
sudo bash build/10-image.sh         # assembles work/out/handtop-<date>-<version>.img.xz + .sha256
```

`build-rootfs.sh` runs the numbered scripts in order; each step can be re-run on its own
(`04` recovers from an interrupted dpkg run). Everything is written below `work/`.

| Step | What |
|---|---|
| `00-host-deps.sh` | Build-host packages, ARM64 emulation |
| `01-fetch-rocknix.sh` / `02-extract-rocknix.sh` | Download the ROCKNIX image (SHA-256 checked), extract U-Boot, kernel, DTBs, modules, firmware |
| `03-debootstrap.sh` | Debian 13 trixie arm64 base |
| `04-install-packages.sh` | Package lists in `build/packages/`, Moonlight and Tailscale repositories |
| `04b-nwg-drawer.sh` | Cross-compiles nwg-drawer (not packaged in Debian) |
| `04c-v4l2-ffmpeg.sh` | Cross-builds FFmpeg with the V4L2 request-API hwaccels (Cedrus VPU) and installs it over Debian's libs |
| `05-configure-base.sh` | Overlay files, hostname, user, locale, timezone, fstab |
| `06-hardware.sh` / `06b-cedrus.sh` | ROCKNIX modules/firmware, H700 quirks; builds the video decoder module (see `video-decode.md`) |
| `07-desktop.sh` / `08-input.sh` / `09-services.sh` | Auto-login session, input daemon, system services |
| `10-image.sh` | Partitions built as files (no loop devices) and written into the `.img`, then compressed |

Settings (user name, default password, timezone, versions, CMA size) are in `build/config.sh`.

If the build host is behind a TLS-inspecting proxy, set `BUILD_EXTRA_CA` to its CA file; it is
trusted only during the build and removed from the rootfs afterwards.

## Safety rules in the scripts

- All paths are absolute (from the script location, never `~`) and the scripts stop if `WORK` or
  `ROOTFS` is empty or outside the project (`build/lib/safety.sh`).
- Files are deleted only through `safe_rm`, and only inside `work/`.
- No `rm` inside chroot commands (bind mounts reach the host); `in_chroot` rejects them.

## Testing without the device

- `tools/qemu-test.sh` — boots the built rootfs in QEMU (arm64 `virt`, 640×480, Debian kernel)
  and checks first-boot services and the desktop.
- `tools/headless-test.sh`, `tools/waybar-test.sh`, `tools/osk-test.sh` — run labwc / Waybar /
  the on-screen keyboard headless inside the rootfs and save screenshots to `work/screens/`.
- `tools/test-wifi-import.sh` — tests `wifi.txt` parsing (BOM, CRLF, spaces).
- Input daemon unit tests: `python3 src/inputd/tests/test_core.py`.

## Debugging on the device

- `logs/boot-NNNN.txt` on the boot partition: written 60 s and 3 min after each boot (failed units,
  network, input devices, displays, battery, memory, session logs, kernel warnings); newest 5 kept.
- Persistent journal: `journalctl -b -1` after a reboot.
- Session logs: `~/.local/state/session/` (labwc, Waybar, input daemon).
- Input daemon key logging: `touch $XDG_RUNTIME_DIR/rg35xxh-inputd.debug` and restart the session.
- Kernel serial console on the UART header, `ttyS0` at 115200 baud.
