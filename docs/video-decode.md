# Hardware Video Decoding

**Status (2026-10-09): working for Moonlight.** 1920×1080 60 fps HEVC at 20 Mbps streams at a steady 59.9 fps with 0 dropped frames, ~5.9 ms per decoded frame, whole device ~37 % busy (software decoding at 1080p was ~55 % busy and choppy). 720p HEVC: ~3.8 ms per frame, ~24 % busy.

## How it works

| Piece | What | Where |
|---|---|---|
| Decoder hardware | Allwinner Cedar video engine (same as H6): MPEG-2, H.264, H.265 8/10-bit, VP8. No VP9 yet (separate upstream series), no AV1 (not in hardware). | `video-codec@1c0e000` |
| Kernel driver | Cedrus, V4L2 **stateless** (request API) → `/dev/video0`, `/dev/media0` | `sunxi-cedrus.ko` in `/usr/lib/modules/7.2.0/extra/`, loaded automatically from the DT node |
| Device tree | ROCKNIX DTB + overlay adding the video-engine node | `/boot/firmware/dtb.img` (original kept as `dtb-rocknix.img`) |
| Memory | Decoder buffers come from CMA: `cma=256M` on the kernel command line (ROCKNIX default is 32 MB). Unused CMA stays available to normal programs. 1080p streaming uses ~140 MB. | `extlinux/extlinux.conf` |
| Userspace | **Moonlight** ships its own FFmpeg with the `v4l2request` hwaccel (`h264_v4l2request`, `hevc_v4l2request`) and picks it automatically (Settings → video decoder: Automatic). | nothing to install |

Not covered: Debian's FFmpeg (mpv, ffplay) has no v4l2request support; browsers (Chromium) cannot use the V4L2 stateless decoder.

## Source

Upstream series "[PATCH v3 0/7] arm64: allwinner: h616: Support Video Engine" (Chen-Yu Tsai, 2026-07-12; reviewed by Jernej Škrabec, DT acked by Rob Herring; DT patches applied to `sunxi/dt-for-7.4` on 2026-10-05). We use:

- **Patch 4/7** (driver, 4 lines): H616 compatible → existing H6 variant. `build/kernel/0001-cedrus-add-h616-variant.patch`.
- **Patch 7/7** (DT node): as an overlay, `build/dts/rg35xxh-video-engine.dtso`, **without the `iommus` property** (see below).

Review notes: all phandles/IDs the node uses exist in 7.2 (`ve_sram`, `sram_c`, `iommu`, `CLK_BUS_VE`/`CLK_VE`/`CLK_MBUS_VE`, `RST_BUS_VE`); `sunxi_sram` already supports `sun50i-h616-ve-sram`; the request API is always built in 7.2.

## Why no IOMMU

With `iommus = <&iommu 3>, <&iommu 2>` (as upstream) the decoder probed, but enabling the IOMMU made the **display engine** (IOMMU master 0, not described as an IOMMU client in the ROCKNIX DT) page-fault at 60 Hz and the screen stayed black. Without `iommus` the decoder uses physically contiguous CMA memory instead; no faults, display normal.

## Building the module (`build/06b-cedrus.sh`)

The ROCKNIX kernel has everything Cedrus needs built in; only the driver is off. Instead of replacing the kernel, the module is built for it:

1. linux 7.2 (sha256 pinned) + ROCKNIX patches from the tag in `ROCKNIX_VERSION` (now `20261001`) (`packages/linux/patches/7.2`, `mainline`, `devices/H700/patches/linux`, same order as ROCKNIX's `package.mk`) + our Cedrus patch.
2. ROCKNIX's own `.config`, extracted from `KERNEL` (`extract-ikconfig`), with `VIDEO_SUNXI_CEDRUS=m`.
3. **GCC 15** (Arm GNU Toolchain 15.2.Rel1, sha256 pinned): ROCKNIX uses GCC 15; with GCC 13 compiler-feature options (`CC_HAS_COUNTED_BY`, …) changed type definitions and 8–50 symbol versions differed.
4. Check: every symbol version the module imports must equal the one ROCKNIX's own modules import, and vermagic must match — otherwise the build stops. (Verified: all 1696 symbols imported by ROCKNIX modules match this build.)

Takes ~6 min on a 28-core x86_64 build host. **When `ROCKNIX_VERSION` changes, this step rebuilds against the new tag automatically**; the checks catch mismatches.

## Undo / fallback

On the boot partition (from Windows): rename `dtb.img` → `dtb-ve.img` and `dtb-rocknix.img` → `dtb.img`. Without the node the module never loads. Optionally remove ` cma=256M` from `extlinux/extlinux.conf`.

## Display caveat

The decoder claims SRAM C, which the 7.2 source says is toggled together with the display engine's region. No display problems were seen while streaming 1080p, but watch for glitches.
