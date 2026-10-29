# Hardware Video Decoding

## Status

**Working.** The Cedrus VPU decodes H.264, HEVC, MPEG-2 and VP8 in the system
FFmpeg and mpv, zero-copy by default, and in Chromium and VLC through VA-API.
Moonlight already did (it links its own patched FFmpeg).

Debian trixie's FFmpeg 7.1 ships only the mainline `drm` hwaccel, which does
not work against Cedrus here, so `build/04c-v4l2-ffmpeg.sh` cross-builds
**Kwiboo's FFmpeg** (`v4l2-request-n7.1.3` — the V4L2 Request API patchset,
the same code Moonlight embeds) and installs it over the system libs. It
registers the `v4l2request` hwdevice with the
`h264/hevc/av1/vp8/vp9/mpeg2video_v4l2request` hwaccels and, with
`build/patches/ffmpeg-v4l2request-drm.patch`, the same decoders again under the
`drm` hwdevice — which is what makes zero-copy work with a stock mpv (see
*Zero-copy*).

mpv only tries hardware for the codecs on its whitelist, which by default
leaves MPEG-2 and VP8 on the CPU, so `/etc/mpv/mpv.conf` sets
`hwdec-codecs=h264,hevc,mpeg2video,vp8` (the option replaces the default
list). All four formats this kernel's Cedrus has reach the VPU: MPEG-2 1080i
drops from 88.8 % to 45.6 % CPU and VP8 720p from 92.1 % to 48.1 %, at the same
fps. VP9 and AV1 are deliberately absent: this kernel's Cedrus has no decoder
for them and mpv's attempt at them fails per frame, so they decode in software
right away (AV1 in dav1d, which this build enables).

On the device (kernel 7.2.0, `tools/check-video-decode.sh`):

```
$ ffmpeg -hwaccel v4l2request -i <540p HEVC episode, 23:55> -f null -
[AVHWFramesContext] Using V4L2 media driver cedrus (7.2.0) for S265
frame=34405 fps=108 ... speed=4.5x          # whole episode, 0 decode errors, exit 0
```

### Throughput

Zero-copy (`--hwdec=drm`) hands the decoder's dmabufs straight to the VO's DRM
PRIME interop; the copy variants download every frame to system memory for the
VO to upload again, which halves decode throughput at 1080p. The *renderer* is
the other half of the problem: with the default (high-quality) scaler the
`gpu` VO manages 23 fps at 1080p HEVC — a bilinear scaler (`--profile=fast`)
removes that limit.

120 frames, `vo=gpu --profile=fast`, on the device (mpv 0.40; the software
column is `--hwdec=no` on the patched build, whose software path is the same
decoders Debian ships):

| 120 frames, `vo=gpu --profile=fast` | software | `hwdec=drm` (zero-copy) |
|---|---|---|
| 540p HEVC | 35.9 fps, 120 % CPU | 36.7 fps, 69 % CPU |
| 1080p HEVC | 30.3 fps, 266 % CPU | 36.1 fps, 75 % CPU |
| 1080p H.264 | 29.0 fps, 271 % CPU | 35.5 fps, 76 % CPU |

CPU is `(user+sys)/wall` for the whole process; the saving is the point —
roughly 3.5 CPUs at 1080p, whichever codec. The fps column saturates near
36 fps because the `vo=gpu`/panfrost path, not the decoder, is the limit, so
the gain is headroom (audio, subtitles, the desktop, thermals), not raw decode
rate. Ten-second playback runs of 540p/1080p HEVC and 1080p H.264 with
`vo=gpu --profile=fast` drop 0 frames; the copy path at 1080p drops 149.

`overlay/etc/mpv/mpv.conf` ships `hwdec=auto-safe` (zero-copy first, the copy
variants behind it, software last) and `profile=fast`; `vo=dmabuf-wayland` is
faster still but renders video only (no OSD, no subtitles), so it stays an
option rather than the default.

### The blue video: the driver's stride

Zero-copy rendered a **flat blue rectangle** for every stream whose width is
not a multiple of 64 pixels. The decoder produced correct frames, but panfrost
refused the dmabuf import (`rejecting image due to unsupported offset or
stride alignment`) and the VO kept its clear colour: Mali (this SoC has a
Mali-G31) only imports linear surfaces whose stride *and* plane offsets are
64-byte aligned, and the Cedrus driver aligned the decoded picture to **16**
bytes — a multiple of 64 only when the width is.

The VPU's framebuffer line stride is programmable (`VE_PRIMARY_FB_LINE_STRIDE`),
so `build/kernel/0002-cedrus-64-byte-stride.patch` aligns the capture stride
to 64 bytes and programs the register from the negotiated `bytesperline`. With
it, 416, 544, 720, 854 and 1366 wide import without a single Mesa rejection,
and the picture matches the software-decoded frame (88 dB PSNR, the difference
being the OSD clock).

### Caveat: the software path is unstable

`--hwdec=no` with a GPU VO segfaults intermittently — 3 of 5 runs of a 12 s
playback — and it is not caused by the patched FFmpeg: the same loop crashes
1/5 with Debian's stock libavcodec, and `gdb` puts the fault in Mesa's
panfrost driver. That is why `hwdec=auto-safe` puts zero-copy first.

## Zero-copy

The decoder was never the problem: FFmpeg's V4L2 request-API code already
produces `AV_PIX_FMT_DRM_PRIME` dmabufs, exactly what a VO's DRM PRIME interop
consumes. The problem was the *device type the decoders were registered under* —
only `AV_HWDEVICE_TYPE_V4L2REQUEST`, while this device's only interop
(`drmprime`, reachable from `vo=gpu` through EGL and from `vo=dmabuf-wayland`)
declares `AV_HWDEVICE_TYPE_DRM`, and mpv hands out interop function tables for
cuda/d3d11/dxva2/vaapi/vdpau/drmprime only. So `--hwdec=v4l2request` never
received frames it could render and fell back to software.

The interop is indifferent to where the dmabuf came from: `hwdec_drmprime.c`
only duplicates the frame's object fds and imports them with
`EGL_EXT_image_dma_buf_import` / `GL_EXT_EGL_image_storage`, so the device mpv
created for the interop does not have to be the same type as the decoder's.

### The patch: `build/patches/ffmpeg-v4l2request-drm.patch`

Applied by `build/04c-v4l2-ffmpeg.sh` right after the pinned Kwiboo checkout.
Three parts:

1. `libavcodec/hwconfig.h` gains `HWACCEL_DRM_V4L2REQUEST(codec)`: the same
   `ff_<codec>_v4l2request_hwaccel`, registered a second time with
   `AV_PIX_FMT_DRM_PRIME` but under `AV_HWDEVICE_TYPE_DRM`.
2. `libavcodec/v4l2_request.c` (`ff_v4l2_request_init()`) swaps in a real
   `AV_HWDEVICE_TYPE_V4L2REQUEST` device when the caller supplied a `drm` one:
   the decoder needs a device of its own type, and the device's hw_type is what
   decides what `av_hwframe_ctx_alloc()` produces.
3. `libavcodec/decode.c` (`ff_get_format()`) picks the hw config whose **device
   type matches the supplied device context** instead of the first config with
   a matching pixel format. Without this the first `DRM_PRIME` match — the
   `v4l2request`-typed entry — is chosen, `hwaccel_init()` rejects the DRM
   device (`does not match the type of the provided device context`) and mpv
   falls back.

Consequence: **stock Debian mpv** — no mpv rebuild anywhere in the image build —
offers `drm` and `drm-copy` in addition to `v4l2request`/`v4l2request-copy`, and
zero-copy renders:

```
$ mpv --hwdec=drm --vo=gpu -v <540p HEVC>
[vo/gpu/drmprime] Using EGL dmabuf interop via GL_EXT_EGL_image_storage
[vd] Using hardware decoding (drm).
```

The system FFmpeg CLI reaches the same decoder through the same device type.
The node has to be given explicitly — the default `drm` device selection does
not work on this SoC (`Device creation failed: -14`):

```
$ ffmpeg -hwaccel drm -hwaccel_device /dev/dri/renderD128 -i in.mp4 -f null -
```

`--hwdec=drm` also works under `--vo=dmabuf-wayland`, the fastest combination
measured (62 fps at 1080p HEVC, 50 fps at 1080p H.264, 0 dropped frames over
10 s in both — video only).

### Why the FFmpeg side

- One FFmpeg patch, so *every* consumer of `AV_PIX_FMT_DRM_PRIME` gains it:
  stock mpv, the `ffmpeg` CLI, anything else a user installs. Patching mpv
  instead would fix mpv only, and would need a distribution package rebuild.
- All four spellings keep working — `v4l2request`, `v4l2request-copy`, `drm`,
  `drm-copy` — so existing configurations are not invalidated and the copy path
  remains available as a fallback.

Nothing here needs a newer FFmpeg or a newer mpv, and Moonlight is unaffected:
it embeds its own FFmpeg and never goes through mpv. The `ff_get_format` change
also looks like an upstream FFmpeg fix; it is kept as a local patch until that
is settled upstream.

## VA-API: Chromium and VLC on the VPU

FFmpeg's `v4l2request` hwaccels serve mpv, ffplay and the `ffmpeg` CLI. Browsers
and VLC do not use FFmpeg's decoding API at all: they speak **VA-API**. Nothing
in Debian's VA-API stack reaches the stateless V4L2 request API, so those two
decode on the CPU until something bridges them.

`libva-v4l2_request` is that bridge — a VA-API *driver* that talks to the
kernel's V4L2 request API directly (so it is independent of the FFmpeg build
above; one can be updated without the other).

What ships:

- `build/04e-va-api.sh` → `tools/build-va-v4l2request.sh --ship` builds
  `sofus13/libva-v4l2_request`, pinned to `f54d8d2` (master, "one CAPTURE buffer
  per surface, queued with `V4L2_MEMORY_DMABUF`"), and installs
  `v4l2_request_drv_video.so` into `/usr/lib/aarch64-linux-gnu/dri/`.
- `build/patches/libva-v4l2-request-fixes.patch`, three fixes:
  1. **single-planar support** — master dropped it in `4cb4bde` because its
     author's SoCs are multiplanar; cedrus exposes `V4L2_CAP_VIDEO_M2M` only, so
     master answers `no V4L2 Request API decoder found`. (The alternative,
     converting cedrus to multiplanar, is a ~300–400 line change to a shared
     kernel interface and would have to be re-validated for every consumer.)
  2. **`vaAcquireBufferHandle()`** was a stub; VLC 3 probes its dmabuf path with
     it before accepting the GL converter and otherwise falls back to software
     without an error.
  3. **NV12/P010 exported as one plane per layer** even when the client passes
     `flags = 0`: VLC 3 rejects a composite layer, which shows as a flat green
     window.
- `LIBVA_DRIVER_NAME=v4l2_request` in `/etc/profile.d/zz-rg35xxh-session.sh`.
  libva has no usable default driver on arm64, so a client only finds this one
  when asked by name; exporting it at session start means every app launched
  from the desktop inherits it. This does change a default: Chromium's VA-API
  decoder now finds a driver, so it decodes on the VPU with no flags. mpv is
  unaffected (it uses the FFmpeg path above), and a client that wants a
  different VA driver can still override the variable for itself.

Enabling it in an app:

- **Chromium** needs nothing beyond the session variable.
- **VLC** is not installed by the image; `apt install vlc` and run it. It needs
  XWayland (`DISPLAY=:0`) because VLC 3's Wayland window modules predate stable
  xdg-shell, which labwc does not offer.

Verifying (device):

- `DEVICE=user@host tools/test-va-v4l2request.sh install|info` pushes a freshly
  built driver and checks the profiles (or run `vainfo` by hand with
  `LIBVA_DRIVER_NAME=v4l2_request` and look for the H264/HEVC VLD profiles).
- VLC logs `Using v4l2-request for hardware decoding` and
  `libva-v4l2request: decoding h264 via /dev/video0 [cedrus]`.

### Performance: hardware vs software, VLC vs mpv

The same 1080p24 H.264 file, 12 s sampled after the first 7 s, on the panel
(640×480), so only the decode and its upload differ. CPU is the process tree
over that window, one core = 100 %; the VPU is a separate block and does not
appear in it.

| player | decode | display | CPU (one core) | RAM |
|---|---|---|---|---|
| VLC `--avcodec-hw=vaapi` | **VPU (VA-API)** | dmabuf → EGL, zero-copy | **11 %** | 142 MB |
| mpv `--hwdec=drm` (shipped default) | **VPU (FFmpeg)** | dmabuf → GL, zero-copy | **18 %** | 129 MB |
| Chromium + this driver | **VPU (VA-API)** | dmabuf → GL | 154–174 % | ~1.0 GB |
| VLC `--vout=xcb_x11` | VPU, copied to RAM | VAOP → I420 | 93 % | 85 MB |
| mpv `--hwdec=v4l2request-copy` | VPU, copied to RAM | CPU download | 114 % | 144 MB |
| Chromium, no driver | CPU | — | 251–260 % | 0.9–1.1 GB |
| mpv `--hwdec=no` | CPU | — | 152 % | 186 MB |
| VLC `--avcodec-hw=none` | CPU | — | 227 % | 241 MB |

HEVC, same file size: VLC zero-copy 22 % against 207 % software; mpv zero-copy
about 75 % at 36 fps against ~266 % software.

What the label says:

- **Hardware is 8–20× cheaper in CPU, not faster.** Decode-only `ffmpeg` is
  slower on the VPU than on the CPU (27 vs 57 fps); the win is the CPU time,
  which buys real-time playback with subtitles and thermal headroom.
- **VLC is the lightest of the three** (11 %), because its GL surface does
  less than mpv's `vo=gpu`; mpv is still the better player (subtitle handling,
  OSD, no XWayland).
- **Copy paths sit in between**: 93–114 %, i.e. still half of software, and
  they need no dmabuf interop — useful to tell "the driver is fine, the import
  is not" apart from "the decode is not happening".
- **Chromium is the odd one out**: its own layout/compositing dominates, so
  the VPU removes the decode but the browser stays heavy.
- A flat green or blue picture is not a decode failure: see "The blue video"
  above — the decoder is engaged while it happens, which is why "hwdec is on"
  is not a test.

Limits: Cedrus has no VP9 or AV1, so sites that serve those (YouTube among
them) stay software; Firefox does not engage its VA-API decoder on this device.

## How it works

| Piece | What | Where |
|---|---|---|
| Decoder hardware | Allwinner Cedar video engine (same as H6): MPEG-2, H.264, H.265 8/10-bit, VP8. No VP9 yet (separate upstream series), no AV1 (not in hardware). | `video-codec@1c0e000` |
| Kernel driver | Cedrus, V4L2 **stateless** (request API) → `/dev/video0`, `/dev/media0` | `sunxi-cedrus.ko` in `/usr/lib/modules/7.2.0/extra/`, loaded automatically from the DT node; our patch gives the decoded picture a 64-byte aligned stride, which is what the GPU needs to import it (see "The blue video") |
| Device tree | ROCKNIX DTB + overlay adding the video-engine node, for both screen panels | `/boot/firmware/dtb-regular.img` / `dtb-rev6.img`, the matching one copied to `dtb.img` at boot ([services/panel.md](services/panel.md)); original kept as `dtb-rocknix.img` |
| Memory | Decoder buffers come from CMA: `cma=256M` on the kernel command line (ROCKNIX default is 32 MB). Unused CMA stays available to normal programs. 1080p streaming uses ~140 MB. | `extlinux/extlinux.conf` |
| Heap access | dma-buf heaps are `root:root 0600` in the kernel; the overlay's `72-rg35xxh-dma-heap.rules` gives group `video` access, otherwise ffmpeg logs `Unable to open any dma_heap device` and no dmabuf path can allocate. | `overlay/etc/udev/rules.d/` |
| Userspace | `build/04c-v4l2-ffmpeg.sh` installs Kwiboo's FFmpeg (`v4l2request` hwdevice + per-codec hwaccels) over the Debian libs, with the same external libraries the distro build has (gnutls for https, x264/lame/opus/vorbis/vpx encoders, libass for subtitles, dav1d for AV1); the replaced `libav*` packages are held with `apt-mark` so an upgrade cannot overwrite them. `/etc/mpv/mpv.conf` sets `hwdec=auto-safe`, which lands on zero-copy `drm`, and `hwdec-codecs=h264,hevc,mpeg2video,vp8`. Moonlight uses its own bundled FFmpeg. | `build/`, `overlay/etc/mpv/` |

Players:

- **Moonlight** — zero-copy, 1080p60 HEVC works today; nothing to install.
- **mpv / ffmpeg (system)** — hardware decode works, zero-copy by default
  (`hwdec=auto-safe` → `drm` in `/etc/mpv/mpv.conf`), copy paths as fallback
  (`v4l2request-copy`, `drm-copy`), and `ffmpeg -hwaccel v4l2request` on the CLI.
  Throughput caveats above. AV1 is software (dav1d) on purpose: no Cedrus AV1.
- **Chromium and VLC** — through VA-API, not FFmpeg (see *VA-API* above).
  Chromium needs no flags; VLC is not installed by the image and needs XWayland.
- Not covered: ffplay decodes in software only, and Firefox does not engage its
  VA-API decoder on this device.

## Source

Upstream series "[PATCH v3 0/7] arm64: allwinner: h616: Support Video Engine" (Chen-Yu Tsai, 2026-07-12; reviewed by Jernej Škrabec, DT acked by Rob Herring; DT patches applied to `sunxi/dt-for-7.4` on 2026-10-05). We use:

- **Patch 4/7** (driver, 4 lines): H616 compatible → existing H6 variant. `build/kernel/0001-cedrus-add-h616-variant.patch`.
- **Patch 7/7** (DT node): as an overlay, `build/dts/rg35xxh-video-engine.dtso`, **without the `iommus` property** (see below).

On top of those, one patch of our own on the driver:
`build/kernel/0002-cedrus-64-byte-stride.patch` — the capture stride is
aligned to 64 bytes instead of 16, and the VPU's framebuffer line stride
register is programmed from the negotiated `bytesperline`. Without it the
GPU cannot import the decoded picture (see "The blue video").

Review notes: all phandles/IDs the node uses exist in 7.2 (`ve_sram`, `sram_c`, `iommu`, `CLK_BUS_VE`/`CLK_VE`/`CLK_MBUS_VE`, `RST_BUS_VE`); `sunxi_sram` already supports `sun50i-h616-ve-sram`; the request API is always built in 7.2.

For the userspace side, the FFmpeg tree is [Kwiboo/FFmpeg](https://github.com/Kwiboo/FFmpeg) branch `v4l2-request-n7.1.3` (pinned by commit in `build/04c-v4l2-ffmpeg.sh`); it is rebased on FFmpeg n7.1.3 and reports the same `libavutil 59.39.100` / `libavcodec 61.19.101` soname ABI as Debian's ffmpeg 7.1.5, so no other package is rebuilt. It is the only tree that has `libavutil/hwcontext_v4l2request.c`.

## Why no IOMMU

With `iommus = <&iommu 3>, <&iommu 2>` (as upstream) the decoder probed, but enabling the IOMMU made the **display engine** (IOMMU master 0, not described as an IOMMU client in the ROCKNIX DT) page-fault at 60 Hz and the screen stayed black. Without `iommus` the decoder uses physically contiguous CMA memory instead; no faults, display normal.

## Building the module (`build/06b-cedrus.sh`)

The ROCKNIX kernel has everything Cedrus needs built in; only the driver is off. Instead of replacing the kernel, the module is built for it:

1. linux 7.2 (sha256 pinned) + ROCKNIX patches from the tag in `ROCKNIX_VERSION` (now `20261001`) (`packages/linux/patches/7.2`, `mainline`, `devices/H700/patches/linux`, same order as ROCKNIX's `package.mk`) + our Cedrus patches.
2. ROCKNIX's own `.config`, extracted from `KERNEL` (`extract-ikconfig`), with `VIDEO_SUNXI_CEDRUS=m`.
3. **GCC 15** (Arm GNU Toolchain 15.2.Rel1, sha256 pinned): ROCKNIX uses GCC 15; with GCC 13 compiler-feature options (`CC_HAS_COUNTED_BY`, …) changed type definitions and 8–50 symbol versions differed.
4. Check: every symbol version the module imports must equal the one ROCKNIX's own modules import, and vermagic must match — otherwise the build stops. (Verified: all 1696 symbols imported by ROCKNIX modules match this build.)

Takes ~6 min on a 28-core x86_64 build host. **When `ROCKNIX_VERSION` changes, this step rebuilds against the new tag automatically**; the checks catch mismatches.

## Undo / fallback

On the boot partition (from Windows): rename `dtb.img` → `dtb-ve.img` and `dtb-rocknix.img` → `dtb.img`. Without the node the module never loads. The panel check leaves a `dtb.img` it doesn't recognise alone, so this sticks; `dtb-rocknix.img` is the regular-panel DTB (on a rev6 unit, copy `device_trees\sun50i-h700-anbernic-rg35xx-h-rev6-panel.dtb` instead). Optionally remove ` cma=256M` from `extlinux/extlinux.conf`.

Without the VPU, `hwdec=auto-safe` falls back to software automatically
(`--hwdec-software-fallback` defaults to yes) — but note the pre-existing Mesa
crash on that path above; `vo=gpu-next` is worse, not better.

## Display caveat

The decoder claims SRAM C, which the 7.2 source says is toggled together with the display engine's region. No display problems were seen while streaming 1080p, but watch for glitches.
