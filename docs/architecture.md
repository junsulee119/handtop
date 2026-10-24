# Architecture

## Decision: hybrid image

**ROCKNIX hardware layer + Debian arm64 userspace.**

| Layer | Source |
|---|---|
| Bootloader (U-Boot), kernel, device trees, kernel modules, firmware blobs | Taken unmodified from a released ROCKNIX H700 image |
| Root filesystem (system, desktop, apps) | **Debian 13 "trixie"** arm64, built by us (debootstrap) |
| Device-specific userspace quirks (audio mixer, governors, LEDs, etc.) | Ported from ROCKNIX's `/usr/lib/autostart/quirks/platforms/H700/` |
| Input daemon + on-screen keyboard | Written for this project (see [services/input-daemon.md](services/input-daemon.md)) |

### Why this approach

- ROCKNIX already has working mainline-kernel support for the H700 (display, Panfrost GPU, audio, Wi-Fi/BT, HDMI). Reusing it avoids hardware bring-up — the slowest, most trial-and-error part of a custom distro.
- Debian gives a normal package manager (`apt`). ROCKNIX itself has none: every app change would need a full image rebuild (~100 GB, hours).
- The whole image can be assembled on any Linux build host — no kernel compile and no ROCKNIX build needed.

### Rejected alternatives

- **Add-on on stock firmware (like RG35XXP-XFCE):** stuck with Anbernic's old vendor kernel; cannot fix kernel-level issues.
- **Fork and rebuild ROCKNIX:** no `apt`; heavy build on every change.
- **Distro fully from scratch:** most on-device trial and error for hardware support.

## Debian release: 13 "trixie" (stable)

- Frozen, security-supported (full support to ~2028, LTS to ~2030).
- Official moonlight-qt arm64 packages exist for trixie.
- Kernel comes from ROCKNIX, so Debian's newer-kernel/Mesa advantages of testing don't matter. If a single package needs a newer version, use `trixie-backports` rather than moving to testing (forky, due ~2027).

## Base image

- ROCKNIX release **20261001** (was 20260901 until 2026-10-09), file `ROCKNIX-H700.aarch64-20261001-DDR4.img.gz` (RG35XX H has LPDDR4 → DDR4 image). Kernel still 7.2.0. Updated for the charge-only bootloader (see `power-and-sleep.md`).
- Kernel: mainline **7.2** (ROCKNIX H700 build).
- Image layout: partition 1 = FAT32 boot (`KERNEL`, `SYSTEM` squashfs, `device_trees/`, `extlinux/extlinux.conf`); partition 2 = 32 MB Linux (grows into STORAGE).
- Boot: `extlinux.conf` loads `/KERNEL` with `FDT /dtb.img`.
- Device tree: `sun50i-h700-anbernic-rg35xx-h.dtb` (or `...-rg35xx-h-rev6-panel.dtb` for rev6 panel boards; garbled screen = wrong one). Input wiring is identical in both.

Later, our own kernel build is allowed (e.g. to add the H616/H700 video-engine patches for hardware video decode) — kernel only, not the full ROCKNIX build.
