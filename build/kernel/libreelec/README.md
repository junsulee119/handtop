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
| 0441-media-cedrus-free-MV-col-buffers-in-buf-cleanup.patch | frees the H.264/HEVC MV-col buffers when a process dies without STREAMOFF |
| 0900-cedrus-vp9-stride-align.patch | **ours**: derive `SCALE1_STRIDE_ALIGN` from the capture stride |
| 0901-cedrus-clear-padding-all-codecs.patch | **ours**: clear the 16-line capture padding rows, neutral chroma |
| 0902-cedrus-2bit-plane-size.patch | **ours**: size the 10-bit low-2-bit plane from the stride the engine programs (it under-allocated at widths 128k+1 to 128k+3); drop it with `0438` |

Our three are numbered `09xx` on purpose: LibreELEC's set grows into the `04xx`
range (their 2026-11-01 update added `0430` and `0432`, VC-1 and UAPI patches),
so a future re-sync cannot collide with our files or silently change apply
order. The patches are applied sorted by name.

The H616 video-engine devicetree node is already present (`0424` in
LibreELEC's set is not needed), and the H616 variant itself comes from
`build/kernel/0001-cedrus-add-h616-variant.patch` (Chen-Yu Tsai's upstream
series), so LibreELEC's `0406` is not carried either.

What was changed on top: only `0900`, `0901` and `0902` are ours; the rest are applied
as published apart from the `0418` rebase described below. Design and code of
the series are Jernej's.

### 0418, rebased

LibreELEC's `0418-media-cedrus-Filter-P010-by-depth-like-AFBC-formats.patch`
does not apply to a tree without the AFBC patches (`0416`/`0419`): its hunks
carry the AFBC code around them as context. The change itself is to drop
`cedrus_is_10bit_dst_format_supported()` and the P010 skip block that `0412`
adds, and leave the choice to the `fmt->depth` field that `0417` introduces.
`0418-media-cedrus-filter-p010-by-depth.patch` here is that change with the
hunks rebased onto this tree. The patch header says so.

### Deliberately not carried

The rest of LibreELEC's Allwinner set is either about features this image does
not use, or needs patches that are out of scope here. The ones that touch
cedrus and were considered:

| file | why not |
|---|---|
| 0437 h616: use the 256-bit DDR mode | written against their separate `sun50i_h616_cedrus_variant` (VC-1 patch 0434) and changes the engine's DDR mode; our H.264, VP8 and VP9 inter frames are bit-exact with the 128-bit mode ROCKNIX's kernel uses, so the corruption it fixes does not show on this board. Revisit with a full series sync. |
| 0438 fix the 10-bit and VP9 reconstruction buffer layout | supersedes our `0900` with a different mechanism (fix the reconstruct stride itself at 64 bytes) and also fixes the low-2-bit plane stride for widths not a multiple of 4. It is written against the AFBC tree (`!afbc`, `cedrus_dst_*` helpers) and drops the 1 KiB height padding that `0411`/`0412` add here, so it needs a rebase like `0418`; see the device results for what is left without it. |
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
`0900` fixes that; all widths now match software bit for bit.

10-bit widths that sit 32 bytes past a 64-byte multiple (352, 416, 480, 544) are
the remaining mismatch. This is what LibreELEC's `0438` addresses with the
low-2-bit plane stride and the 1 KiB-aligned P010 reconstruct surface; 8-bit at
the same widths is exact.
10-bit at 1282x720 and 1410x792 (2 pixels past a 128 multiple) is also close
but not exact: 53.9 and 55.2 dB (2026-11-03, DDR4, with `0902`; `0902` only
changes the allocation size, not where anything is written).

`0902`: the buffer reserved `ALIGN(width / 4, 32)` bytes per row for the 10-bit
low-2-bit plane, while VP9 programs `ALIGN(bytesperline / 4, 32)` of the
reconstruction surface (64-byte aligned capture stride, or `ALIGN(width, 16)`
behind P010). At widths 128k+1 to 128k+3 that is 32 bytes more per row, so the
engine wrote up to 32 x 1.5 x height bytes past the buffer, into CMA (no IOMMU).
Found by stockmind (issue #8). Tested: 20 full decodes each of 10-bit
1282x720 and 1410x792, no failure, H.264 / HEVC fine afterwards. LibreELEC's
`0438` fixes the same allocation as part of its layout rework.
