# Hardware Video Decoding

## Status

**Working.** The Cedrus VPU decodes H.264 and HEVC (and MPEG-2/VP8 — see the
`hwdec-codecs` note below) both in Moonlight and in the system FFmpeg and mpv.

- **Moonlight** always worked: it links its own FFmpeg with the V4L2 request-API
  patchset and picks the VPU automatically (Settings → video decoder: Automatic).
  Measured 2026-10-09: 1920×1080 60 fps HEVC at 20 Mbps streams at a steady
  59.9 fps with 0 dropped frames, ~5.9 ms per decoded frame, whole device ~37 %
  busy (software decoding at 1080p: ~55 % busy and choppy).
- **System FFmpeg / mpv** needed the same patchset. Debian trixie's FFmpeg 7.1
  ships only the mainline `drm` hwaccel, which does not work against Cedrus
  here, so `build/04c-v4l2-ffmpeg.sh` cross-builds **Kwiboo's FFmpeg**
  (`v4l2-request-n7.1.3` — the V4L2 Request API patchset, upstream PR 20847,
  i.e. the same code Moonlight embeds) and installs it over the system libs. It
  registers the `v4l2request` hwdevice and the
  `h264/hevc/av1/vp8/vp9/mpeg2video_v4l2request` hwaccels, and — since
  2026-10-17 — the same decoders again under the `drm` hwdevice
  (`build/patches/ffmpeg-v4l2request-drm.patch`). mpv derives its
  `--hwdec=v4l2request[-copy]` and `--hwdec=drm[-copy]` values from exactly
  those; the `drm` registration is what makes zero-copy playback work, with an
  unpatched mpv (see *Zero-copy* below).

Measured on the device 2026-10-17 (kernel 7.2.0, `tools/check-video-decode.sh`):

```
$ ffmpeg -hwaccel v4l2request -i <540p HEVC episode, 23:55> -f null -
[AVHWFramesContext] Using V4L2 media driver cedrus (7.2.0) for S265
[V4L2RequestContext] slice-based decoder with SLICE_PARAMS=1, ENTRY_POINT_OFFSETS=256 and SCALING_MATRIX=1 controls
frame=34405 fps=108 ... speed=4.5x          # whole episode, 0 decode errors, exit 0

$ ffmpeg -hwaccel v4l2request -i <1080p H.264> -t 5 -f null -
[AVHWFramesContext] Using V4L2 media driver cedrus (7.2.0) for S264
122 frames decoded; 0 decode errors; exit 0

$ mpv --hwdec=v4l2request-copy --frames=60 <540p HEVC>
Using hardware decoding (v4l2request-copy).
```

`--hwdec=v4l2request[-copy]` and `--hwdec=drm[-copy]` are offered for H.264,
HEVC, MPEG-2, VP8, VP9 and AV1, but mpv only tries the codecs on its hwdec
whitelist, which by default leaves MPEG-2 and VP8 on the CPU
(`[vd] Not trying to use hardware decoding: codec mpeg2video is not on
whitelist`, with any `--hwdec` spelling). `/etc/mpv/mpv.conf` therefore sets
`hwdec-codecs=h264,hevc,mpeg2video,vp8` — that option *replaces* the default
list, so the codecs that matter have to be in it — and all four formats this
kernel's Cedrus has reach the VPU. The whitelist line is worth its keep on
battery: MPEG-2 1080i drops from 88.8 % to 45.6 % CPU and VP8 720p from 92.1 % to
48.1 %, at the same fps.

VP9 and AV1 are deliberately not in the list. This kernel's Cedrus has no
decoder for them, and mpv's attempt at them does not fail cleanly: it reports
`Error while decoding frame (hardware decoding)!` for every frame before it
gives up. Leaving them out of the whitelist means they are never attempted and
decode in software right away — VP9 in FFmpeg's native decoder, AV1 in dav1d
(this build enables it: with the hardware devices advertised, the native av1
decoder picks no pixel format and renders black).

### Throughput: zero-copy vs copy

Two paths reach the VPU, and since 2026-10-17 both work. **Zero-copy**
(`--hwdec=drm`, or `--hwdec=v4l2request` with the patched mpv) hands the decoder's
dmabufs straight to the VO's DRM PRIME interop; the **copy** variants download
every frame to system memory for the VO to upload again. *Zero-copy* below has
the two patches that make the zero-copy names appear; the default configuration
has been switched to them.

Measured 2026-10-17 on the device with `--no-audio --untimed` (the reference
files are 24 fps, so ≥24 fps is real time). Absolute numbers move by tens of
percent between harnesses — audio on, a different frame count — so read the
ratios, not the digits:

| Path | 540p HEVC | 1080p HEVC | 1080p H.264 |
|---|---|---|---|
| zero-copy, `vo=gpu` `--profile=fast` | 79 fps | 51 fps | 43 fps |
| zero-copy, `vo=dmabuf-wayland` | 94 fps | 62 fps | 50 fps |
| zero-copy, `vo=gpu` (default scaler) | 79 fps | 23 fps | 18 fps |
| copy, `vo=gpu` (default scaler) | 78 fps | 18 fps | 18 fps |

The download/upload round trip halves decode throughput at 1080p (99 → 48 fps
HEVC, 51 → 24 fps H.264). At 540p the VPU is nowhere near the bottleneck and the
copy costs little — which is why the first release, whose table used
audio-enabled runs, only saw the copy path lose badly at 1080p.

At 1080p the *renderer* was the other half of the problem: with the default
(high-quality) scaler the `gpu` VO manages 23 fps at 1080p HEVC and 18 fps at
1080p H.264, regardless of zero-copy or copy, because it is spending its time in
the scaler rather than in the decoder. A bilinear scaler (`--profile=fast`)
removes that limit. Ten-second playback runs, dropped frames from
`--term-status-msg='... drop=${frame-drop-count}'`:

| 10 s playback, zero-copy (`hwdec=drm`) | dropped frames |
|---|---|
| 540p HEVC, `vo=gpu` | 0 |
| 540p HEVC episode (23:55, whole file), `vo=gpu` | 0 |
| 1080p HEVC, `vo=gpu` default scaler | 23 |
| 1080p HEVC, `vo=gpu --profile=fast` | 0 |
| 1080p HEVC, `vo=dmabuf-wayland` | 0 |
| 1080p H.264, `vo=gpu` default scaler | 35 |
| 1080p H.264, `vo=gpu --profile=fast` | 0 |
| 1080p H.264, `vo=dmabuf-wayland` | 0 |
| 1080p H.264, `vo=gpu` **copy** path (`drm-copy`), for comparison | 149 |

So `overlay/etc/mpv/mpv.conf` ships `hwdec=auto-safe` — zero-copy first, the copy
variants behind it, software last — plus `profile=fast`. `auto-safe` picks the
zero-copy method by itself (`mpv --hwdec=auto-safe -v` logs `Trying hardware
decoding via hevc-drm`) and skips it when the VO has no usable interop.
`vo=dmabuf-wayland` is faster still but renders video only — no OSD, no
subtitles — so it remains an option rather than the default. The software path is
unchanged and still the unstable one (next section).

### Versus the software path (what an image without this PR does)

Without `04c` mpv has only software decoding, so that is the honest before/after
baseline. Same harness, 120 frames, `vo=gpu --profile=fast`, measured 2026-10-21
on the device (mpv 0.40; `--hwdec=no` on the patched build — its software path is
the same decoders Debian ships):

| 120 frames, `vo=gpu --profile=fast` | software | `hwdec=drm` (zero-copy) |
|---|---|---|
| 540p HEVC | 35.9 fps, 120 % CPU | 36.7 fps, 69 % CPU |
| 1080p HEVC | 30.3 fps, 266 % CPU | 36.1 fps, 75 % CPU |
| 1080p H.264 | 29.0 fps, 271 % CPU | 35.5 fps, 76 % CPU |

CPU is `(user+sys)/wall` for the whole process. The saving is the point: roughly
3.5 CPUs at 1080p, whichever codec. The fps column saturates near 36 fps in this
harness because the `vo=gpu`/panfrost path, not the decoder, is the limit — the
gain there is headroom (audio, subtitles, the desktop, thermals), not raw decode
rate. Decode-only runs show the same from the other side: with `vo=null`
`--hwdec=drm-copy` (VPU plus a download per frame) does 94 / 32 / 23 fps against
software's 154 / 68 / 48 fps, at about a third of the CPU — which is why
zero-copy, not the VPU alone, is what turns the saving into a playback win.
`vo=null` cannot present `drm_prime` frames, so `--hwdec=drm` falls back to
software there and is not a valid way to measure the zero-copy path.

The power draw could not be compared directly: the AXP2202 fuel gauge on this
board reports the same ~423 mA with the SoC idle and with four cores pegged, so
CPU time is the only usable proxy.

### The blue video: the driver's stride, and the fix

Zero-copy (`--hwdec=drm`) used to render a **flat blue rectangle** for streams
whose width is not a multiple of 64 pixels. The picture was not a decode
failure: the decoder produced correct frames, and `MESA: panfrost: rejecting
image due to unsupported offset or stride alignment` was logged for every
frame. Panfrost refused the dmabuf import, the VO kept its clear colour, and
nothing else was drawn.

Measured 2026-10-21 on the device (`--hwdec=drm`, 24 frames each, "Mesa
errors" counted from the mpv log):

| width | Mesa rejections | picture |
|---|---|---|
| 416 (416x234 / 416x236 / 416x238) | 26-62 per frame | blue |
| 544 (544x306) | 26 | blue |
| 720 (720x404) | 26 | blue |
| 512, 640, 704, 960, 1280 | 0 | correct |

Height did not matter (1280x536 was fine, 416x240 was fine), only the width —
i.e. the NV12 stride.

**The cause was the driver, not the GPU.** Mali (this SoC has a Mali-G31,
Utgard) wants a linear surface whose stride *and* plane offsets are 64-byte
aligned, and panfrost enforces that. The Cedrus driver aligned the decoded
picture to **16** bytes (`ALIGN(width, 16)` in `cedrus_prepare_format()`),
which is a multiple of 64 only when the width is a multiple of 64 — hence
416 = 6.5x64, 544 = 8.5x64 and 720 = 11.25x64 failed while 640 = 10x64,
704 = 11x64, 960 = 15x64 and 1280 = 20x64 worked.

The VPU's output stride is programmable (`VE_PRIMARY_FB_LINE_STRIDE`), so
`build/kernel/0002-cedrus-64-byte-stride.patch` aligns the capture stride to
64 bytes and programs the register from the negotiated `bytesperline`, so the
driver and the hardware cannot disagree about the layout. The chroma plane
then starts at `stride * height`, which is 64-byte aligned too.

Measured 2026-10-22 on the device with the patched module:

| width | Mesa rejections | picture |
|---|---|---|
| 416, 544, 720, 854, 1366 | 0 | correct |

The picture was checked against the software-decoded frame: the zero-copy
screen and the software screen differ by 88 dB PSNR (the OSD clock), i.e.
they are the same picture — the VPU writes the frame with the 64-byte stride
and panfrost imports it. The 416-wide H.264 file decodes on the VPU at
16.6x real time with 0 errors, and the 1080p H.264/HEVC, 960x540 and 540p
HEVC files are unchanged.

### Zero-copy for every width

Zero-copy costs the same at every width, so nothing has to predict or check
it any more: `--hwdec=drm` renders every picture.

Measured 2026-10-21 on the device (h264, 24 fps, 20 s, `vo=gpu --profile=fast`,
CPU as % of one core):

| resolution | `drm` (zero-copy) | `drm-copy` |
|---|---|---|
| 640x360 (the panel) | 16 % CPU, 0 dropped | 28 % CPU, 0 dropped |
| 960x540 | 17 %, 0 | 45 %, 0 |
| 1280x720 | 17 %, 0 | 62 %, 0 |
| 1920x1080 | 18 %, 0 | 115 %, 19 dropped |

Zero-copy is flat (the VPU and the GPU do the work, the CPU barely moves),
while the copy path scales with the pixel count: 16 % CPU instead of the
62 % the 720p copy stream cost, and no blue frames.

The copy path stays available as a fallback (`--hwdec=drm-copy`, and
`hwdec=auto-safe` keeps it behind the zero-copy method).
### The Mesa crash on the software path (pre-existing)

`--hwdec=no` with a GPU VO segfaults intermittently, and it is *not* caused by
the patched FFmpeg. Measured 2026-10-17, 12 s of normal playback of a 540p HEVC
file, crashes per 5 runs:

| Configuration | Crashes |
|---|---|
| software + `vo=gpu` | 3 |
| software + `vo=gpu-next` | 5 |
| `v4l2request-copy` + `vo=gpu` | 0 |
| `v4l2request-copy` + `vo=gpu-next` | 0 |

The same loop crashes 1/5 with Debian's **stock** libavcodec installed, and
`gdb` puts the fault in Mesa's panfrost driver on mpv's `vo` thread
(`libgallium-25.0.7-2+deb13u1.so`), not in any `libav*`/`libsw*` library.
Software decoding produces `yuv420p` frames; the hardware copy path produces
`nv12`, which Mesa handles fine. That is why `/etc/mpv/mpv.conf` defaults to `hwdec=auto-safe`: zero-copy
`drm` first, `v4l2request-copy` only when the VO has no usable interop.

## Zero-copy

The decoder was never the problem: FFmpeg's V4L2 request-API code already
produces `AV_PIX_FMT_DRM_PRIME` dmabufs, exactly what a VO's DRM PRIME interop
consumes. The problem was the *device type the decoders were registered under* —
only `AV_HWDEVICE_TYPE_V4L2REQUEST`, while this device's only interop
(`drmprime`, reachable from `vo=gpu` through EGL and from `vo=dmabuf-wayland`)
declares `AV_HWDEVICE_TYPE_DRM`. mpv hands out interop function tables from
`hwdec_get_hwcontext_fns()` for cuda/d3d11/dxva2/vaapi/vdpau/drmprime and nothing
else, so `--hwdec=v4l2request` never received frames it could render and fell back
to software, while `--vo=dmabuf-wayland` refused them outright.

The interop is indifferent to where the dmabuf came from: `hwdec_drmprime.c` only
duplicates the frame's object fds and imports them with
`EGL_EXT_image_dma_buf_import` / `GL_EXT_EGL_image_storage`. Its own device fd is
never used on this panfrost/EGL path, so the device mpv created for the interop
does not have to be the same type as the decoder's. Two small patches make use of
that; the image ships the FFmpeg-side one.

### The patch: `build/patches/ffmpeg-v4l2request-drm.patch`

Applied by `build/04c-v4l2-ffmpeg.sh` right after the pinned Kwiboo checkout.
Three parts:

1. `libavcodec/hwconfig.h` gains `HWACCEL_DRM_V4L2REQUEST(codec)`: the same
   `ff_<codec>_v4l2request_hwaccel`, registered a second time with
   `AV_PIX_FMT_DRM_PRIME` but under `AV_HWDEVICE_TYPE_DRM`. h264dec, hevcdec,
   av1dec, vp8, vp9 and mpeg12dec each add one line beside their existing
   `HWACCEL_V4L2REQUEST(x)`.
2. `libavcodec/v4l2_request.c` (`ff_v4l2_request_init()`) notices when the device
   context the caller supplied is a `drm` device and swaps in a real
   `AV_HWDEVICE_TYPE_V4L2REQUEST` device before calling
   `ff_decode_get_hw_frames_ctx()`. mpv only ever passes the device it created for
   the interop; the decoder needs one of its own type, and it is the *device's*
   hw_type that decides what `av_hwframe_ctx_alloc()` produces.
3. `libavcodec/decode.c` (`ff_get_format()`) picks the hw config whose **device
   type matches the supplied device context** instead of simply the first config
   with a matching pixel format. Without this the first `DRM_PRIME` match — the
   `v4l2request`-typed entry — is chosen and `hwaccel_init()` rejects the DRM
   device:

   ```
   hevc: Invalid setup for format drm_prime: does not match the type of the provided device context.
   ```

   and mpv falls back (that was this patch's first version: `--hwdec=drm` decoded
   in software; the selection fix is what made it work).

Consequence: **stock Debian mpv** — no mpv rebuild anywhere in the image build —
offers `drm` and `drm-copy` in addition to `v4l2request`/`v4l2request-copy`, and
zero-copy renders:

```
$ mpv --hwdec=drm --vo=gpu -v <540p HEVC>
[vo/gpu] Loading hwdec drivers for format: 'drm_prime'
[vo/gpu] Loading hwdec driver 'drmprime'
[vo/gpu/drmprime] Using EGL dmabuf interop via GL_EXT_EGL_image_storage
[vd] Using hardware decoding (drm).
```

The system FFmpeg CLI reaches the same decoder through the same device type. The
node has to be given explicitly — the default `drm` device selection does not work
on this SoC (`Device creation failed: -14`) — and `bench` then reports the same
`cedrus` decode:

```
$ ffmpeg -hwaccel drm -hwaccel_device /dev/dri/renderD128 -i in.mp4 -f null -
```

`--hwdec=drm` also works under `--vo=dmabuf-wayland`, the fastest combination
measured (62 fps at 1080p HEVC, 50 fps at 1080p H.264, 0 dropped frames over 10 s
in both — video only).

### Why the FFmpeg side

- It is one FFmpeg patch, so *every* consumer of `AV_PIX_FMT_DRM_PRIME` gains it:
  stock mpv, the `ffmpeg` CLI, anything else a user installs. Patching mpv
  instead would fix mpv only.
- The image build stays free of a distribution-package rebuild.
- All four spellings keep working — `v4l2request`, `v4l2request-copy`, `drm`,
  `drm-copy` — so existing configurations are not invalidated and the copy path
  remains available as a fallback.

Nothing here needs a newer FFmpeg (`v4l2-request-n8.x`) or a newer mpv, and
Moonlight is unaffected: it embeds its own FFmpeg and never goes through mpv.
The `ff_get_format` change also looks like an upstream FFmpeg fix (a caller that
passes a device of a type other than the codec's first-listed configuration is
rejected today); it is kept as a local patch until that is settled upstream.


## How it works

| Piece | What | Where |
|---|---|---|
| Decoder hardware | Allwinner Cedar video engine (same as H6): MPEG-2, H.264, H.265 8/10-bit, VP8. No VP9 yet (separate upstream series), no AV1 (not in hardware). | `video-codec@1c0e000` |
| Kernel driver | Cedrus, V4L2 **stateless** (request API) → `/dev/video0`, `/dev/media0` | `sunxi-cedrus.ko` in `/usr/lib/modules/7.2.0/extra/`, loaded automatically from the DT node; our patch gives the decoded picture a 64-byte aligned stride, which is what the GPU needs to import it (see "The blue video") |
| Device tree | ROCKNIX DTB + overlay adding the video-engine node | `/boot/firmware/dtb.img` (original kept as `dtb-rocknix.img`) |
| Memory | Decoder buffers come from CMA: `cma=256M` on the kernel command line (ROCKNIX default is 32 MB). Unused CMA stays available to normal programs. 1080p streaming uses ~140 MB. | `extlinux/extlinux.conf` |
| Heap access | dma-buf heaps are `root:root 0600` in the kernel; the overlay's `72-rg35xxh-dma-heap.rules` gives group `video` access, otherwise ffmpeg logs `Unable to open any dma_heap device` and no dmabuf path can allocate. | `overlay/etc/udev/rules.d/` |
| Userspace | `build/04c-v4l2-ffmpeg.sh` installs Kwiboo's FFmpeg (`v4l2request` hwdevice + per-codec hwaccels) over the Debian libs, with the same external libraries the distro build has (gnutls for https, x264/lame/opus/vorbis/vpx encoders, libass for subtitles, dav1d for AV1); the replaced `libav*` packages are held with `apt-mark` so an upgrade cannot overwrite them. `/etc/mpv/mpv.conf` sets `hwdec=auto-safe`, which lands on zero-copy `drm`, and `hwdec-codecs=h264,hevc,mpeg2video,vp8`. Moonlight uses its own bundled FFmpeg. | `build/`, `overlay/etc/mpv/` |

Players:

- **Moonlight** — zero-copy, 1080p60 HEVC works today; nothing to install.
- **mpv / ffmpeg (system)** — hardware decode works, zero-copy by default
  (`hwdec=auto-safe` → `drm` in `/etc/mpv/mpv.conf`), copy paths as fallback
  (`v4l2request-copy`, `drm-copy`), and `ffmpeg -hwaccel v4l2request` on the CLI.
  Throughput caveats above. AV1 is software (dav1d) on purpose: no Cedrus AV1.
- Not covered: ffplay decodes in software only, VLC has no V4L2 code path at
  all, and Chromium cannot use the V4L2 stateless decoder (its Linux decoder only
  offers the GL output path, which does not accept these dmabufs).

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

1. linux 7.2 (sha256 pinned) + ROCKNIX patches from the tag in `ROCKNIX_VERSION` (now `20261001`) (`packages/linux/patches/7.2`, `mainline`, `devices/H700/patches/linux`, same order as ROCKNIX's `package.mk`) + our Cedrus patch.
2. ROCKNIX's own `.config`, extracted from `KERNEL` (`extract-ikconfig`), with `VIDEO_SUNXI_CEDRUS=m`.
3. **GCC 15** (Arm GNU Toolchain 15.2.Rel1, sha256 pinned): ROCKNIX uses GCC 15; with GCC 13 compiler-feature options (`CC_HAS_COUNTED_BY`, …) changed type definitions and 8–50 symbol versions differed.
4. Check: every symbol version the module imports must equal the one ROCKNIX's own modules import, and vermagic must match — otherwise the build stops. (Verified: all 1696 symbols imported by ROCKNIX modules match this build.)

Takes ~6 min on a 28-core x86_64 build host. **When `ROCKNIX_VERSION` changes, this step rebuilds against the new tag automatically**; the checks catch mismatches.

## Undo / fallback

On the boot partition (from Windows): rename `dtb.img` → `dtb-ve.img` and `dtb-rocknix.img` → `dtb.img`. Without the node the module never loads. Optionally remove ` cma=256M` from `extlinux/extlinux.conf`.

Without the VPU, `hwdec=auto-safe` falls back to software automatically
(`--hwdec-software-fallback` defaults to yes) — but note the pre-existing Mesa
crash on that path above; `vo=gpu-next` is worse, not better.

## Display caveat

The decoder claims SRAM C, which the 7.2 source says is toggled together with the display engine's region. No display problems were seen while streaming 1080p, but watch for glitches.
