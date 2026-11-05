# Third-party kernel patches: VP9 for cedrus

Everything in this directory comes from somewhere else. Keep this file honest:
when something is lifted from an external tree, list the origin, the author and
the date it was fetched, and say what was changed.

Origin: LibreELEC.tv, `projects/Allwinner/patches/linux/`
(<https://github.com/LibreELEC/LibreELEC.tv>), master at
`f59641eb70c727cc81e33508177ac700abac81ab` (2026-11-01, the merge of PR #11969
"allwinner-features"), fetched 2026-11-02 from
`https://raw.githubusercontent.com/LibreELEC/LibreELEC.tv/master/projects/Allwinner/patches/linux/<file>`.
Found by searching for `cedrus_vp9` (<https://grep.app/search?q=cedrus_vp9>).
`0438` was added on 2026-11-05 from the same folder; every file carried here is
unchanged at master `43711f2a265b` (2026-11-05), which is the pin the weekly
upstream check uses (`LIBREELEC_CEDRUS_COMMIT`).

Author of the series: Jernej Skrabec <jernej.skrabec@gmail.com>, the current
cedrus maintainer. The patches carry his `Signed-off-by` and are labelled
`[PATCH nnn/419]` against their 7.2 rebase, which matches the ROCKNIX 7.2
kernel this image builds against. GPL-2.0, same license as the driver.

`build/06b-cedrus.sh` appends them to its `PATCHES` array after
`build/kernel/*.patch`, so editing or re-syncing one of them rebuilds the kernel
tree, and applies them with `patch --fuzz=0`: this is a snapshot of someone
else's tree, so a context line that has moved since must stop the build instead
of being applied one line off.

| file | what it does |
|---|---|
| 0410-media-cedrus-Don-t-CPU-map-source-buffers.patch | `DMA_ATTR_NO_KERNEL_MAPPING` on the output queue |
| 0411-media-cedrus-Add-VP9-decoding-support.patch | the VP9 backend (`cedrus_vp9.c`) |
| 0412-media-cedrus-Add-P010-capture-format-and-shared-10-b.patch | P010 capture + shared 10-bit handling |
| 0413-media-cedrus-Add-VP9-P010-output-support.patch | VP9 P010 output |
| 0414-media-cedrus-Add-H265-P010-output-support.patch | H.265 P010 output (without it HEVC Main10 decodes to garbage) |
| 0415-media-cedrus-Name-H616-VP9-mode-register-bits.patch | names the VP9 mode bits |
| 0417-media-cedrus-add-format-filtering-based-on-depth-and.patch | format filtering by bit depth |
| 0418-media-cedrus-filter-p010-by-depth.patch | wires the depth filter into P010, rebased, see below |
| 0421-media-cedrus-Select-V4L2_VP9-for-the-VP9-helpers.patch | `select V4L2_VP9` in Kconfig, so `v4l2-vp9.ko` is built |
| 0438-media-cedrus-10-bit-and-vp9-recon-layout.patch | 10-bit and VP9 reconstruction buffer layout (64-byte reference stride, 1 KiB-aligned P010 reconstruct surface, one 2-bit plane stride for allocation and hardware), rebased, see below |
| 0441-media-cedrus-free-MV-col-buffers-in-buf-cleanup.patch | frees the H.264/HEVC MV-col buffers when a process dies without STREAMOFF |
| 0901-cedrus-clear-padding-all-codecs.patch | **ours**: clear the 16-line capture padding rows, neutral chroma |

Ours are numbered `09xx` on purpose: LibreELEC's set grows into the `04xx`
range (their 2026-11-01 update added `0430` and `0432`, VC-1 and UAPI patches),
so a future re-sync cannot collide with our files or silently change apply
order. The patches are applied sorted by name.

The H616 video-engine devicetree node is already present (`0424` in
LibreELEC's set is not needed), and the H616 variant itself comes from
`build/kernel/0001-cedrus-add-h616-variant.patch` (Chen-Yu Tsai's upstream
series), so LibreELEC's `0406` is not carried either.

What was changed on top: only `0901` is ours; the rest are applied as published
apart from the `0418` and `0438` rebases described below. (`0900`, our VP9
reference-stride fix, and `0902`, our 2-bit plane size fix, were dropped when
`0438` came in: it does both the way the hardware expects.) Design and code of
the series are Jernej's.

### 0418, rebased

LibreELEC's `0418-media-cedrus-Filter-P010-by-depth-like-AFBC-formats.patch`
does not apply to a tree without the AFBC patches (`0416`/`0419`): its hunks
carry the AFBC code around them as context. The change itself is to drop
`cedrus_is_10bit_dst_format_supported()` and the P010 skip block that `0412`
adds, and leave the choice to the `fmt->depth` field that `0417` introduces.
`0418-media-cedrus-filter-p010-by-depth.patch` here is that change with the
hunks rebased onto this tree. The patch header says so.

### 0438, rebased

LibreELEC's `0438-media-cedrus-fix-the-10-bit-and-VP9-reconstruction-buffer-layout.patch`
is written against the AFBC tree as well (`!afbc` conditions,
`cedrus_dst_is_afbc()` as context), and its `cedrus_hw.c` hunk is already in
this tree (the primary output takes its line stride and chroma size from
`bytesperline`). `0438-media-cedrus-10-bit-and-vp9-recon-layout.patch` is the
rest with the hunks rebased: `CEDRUS_RECON_STRIDE_ALIGN` (64), a
`cedrus_dst_2bit_stride()` used for both the allocation and the VP9 / H.265
registers, the hidden reconstruction surface behind P010 at a 64-byte stride
and a 1 KiB-aligned offset, the VP9 reference stride alignment programmed as
64 bytes, and the VP9 capture stride set to 64 instead of padding the height.
Same code otherwise; the patch header says so.

### Deliberately not carried

The rest of LibreELEC's Allwinner set is either about features this image does
not use, or needs patches that are out of scope here. The ones that touch
cedrus and were considered:

| file | why not |
|---|---|
| 0437 h616: use the 256-bit DDR mode | written against their separate `sun50i_h616_cedrus_variant` (VC-1 patch 0434) and changes the engine's DDR mode; our H.264, HEVC, VP8 and VP9 (8- and 10-bit) frames are bit-exact with the 128-bit mode ROCKNIX's kernel uses, so the corruption it fixes does not show on this board (re-checked 2026-11-05 with `0438`). Revisit with a full series sync. |
| 0439/0440/0444 VP8 fixes | VP8 correctness and >2048-wide support; unrelated to VP9, worth its own change. |
| 0442/0443 H.264 SPS size check, long-term references | H.264 hardening; separate change. |
| 0445 reset the decoder when switching codecs | depends on `0437` (`ve_mode_ddr`); the failures it describes are on H3, and repeated codec switches (H.264, VP9, HEVC in one session) are clean here. |
| 0420 increase H6 clock rate | performance only. 4K VP9 decodes at the ROCKNIX clock and is bit-exact; keeping the stock clock keeps the tree closer to ROCKNIX's. |
| 0416/0419/0425 AFBC | compressed output would cut CMA use and bandwidth, but needs modifier support in the GPU stack; separate project. |
| 0400/0401/0426/0427/0435 DI300 deinterlace | a second driver and no userspace path here (mpv and VA-API do not use the V4L2 deinterlace API). |
| 0407/0408/0409 IOMMU and SRAM DT, iommu page sizes | this image runs the decoder without the IOMMU (see `docs/video-decode.md`, "Why no IOMMU"). |
| 0428/0429..0436 VC-1 and format filtering | VC-1 UAPI and backend, unrelated to VP9. |

### Device results with the full set

Measured 2026-11-02 on a DDR4 RG35XX H, 10 frames per clip through
`ffmpeg -hwaccel v4l2request` against a software decode of the same clip,
NV12 for 8-bit and P010 for 10-bit:

```
capture formats: P010, NV12, ST12, NV21, YU12, YV12
VP9 8-bit   416x234, 720p, 854x480, 1366x768, 1080p, 4K       inf
VP9 10-bit  384x216, 448x256, 512x288, 640x360, 720p,
            854x480, 1366x768                                 inf
VP9 10-bit  352x234, 416x234, 416x240, 480x234, 544x234       25.5-29.2 dB
HEVC 8-bit  1080p                                             inf
HEVC Main10 720p, 854x480                                      inf (p010le)
H.264       1080p, 854x480                                     inf
VP8 720p                                                       inf
```

Widths that are not a multiple of 64 (416, 854, 1366) were broken in the first
round: key frames decoded and every inter frame was garbage, because the backend
kept the 16-byte stride the driver used before `0002-cedrus-64-byte-stride.patch`.
Our `0900` fixed that by deriving the reference stride alignment from the
capture stride; `0438` now programs it as 64 bytes and gives the hidden 10-bit
surface the same stride.

That left 10-bit at some widths close but not exact (352, 416, 480 and 544 at
25.5-33.4 dB, 1282 and 1410 at about 56 dB) and HEVC Main10 at 1282x720 at
18 dB, because the hidden reconstruction surface behind P010 had a 16-byte
stride; and the 2-bit plane was under-allocated at widths 128k+1 to 128k+3
(found by stockmind, issue #8; our `0902` sized it from the stride until
`0438`).

With `0438` (2026-11-05, DDR4, same method, 25 clips): every clip bit-exact
(`inf`): VP9 10-bit 352x234, 384x216, 416x234, 416x240, 480x234, 544x234,
720p, 1282x720, 1410x792, 1080p; VP9 8-bit 416x234, 854x480, 1366x768,
1282x720, 1080p, 4K; HEVC Main10 854x480, 720p, 1282x720; HEVC 8-bit 1080p;
H.264 1080p, 854x480; VP8 720p; MPEG-2 720p unchanged (70.9 dB against
FFmpeg's software decoder, as before).

VP9 10-bit 4K does not start: "Cannot allocate memory" for the capture buffers,
before and after `0438`. With P010 output each buffer holds the visible P010
picture, the hidden 8-bit reconstruction and the 2-bit plane (about 40 MB at
4K), and the decoder's buffer set does not fit in `cma=256M`. 8-bit 4K fits.
