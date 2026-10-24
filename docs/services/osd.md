# Volume / brightness bar

`rg35xxh-osd` (`src/osd`): the pop-up bar for volume (Vol) and brightness (F + Vol).

- A vertical bar at the left edge of the screen, vertically centred, with the level as a number on top (3x5 pixel font at 2x). Blue for volume, amber for brightness. Shown for 1.2 s after each change, on the focused screen, above everything, without taking input; while hidden there is no surface at all.
- Input: the input daemon writes a level (0-100) and a newline to `$XDG_RUNTIME_DIR/wob-volume.sock` or `wob-brightness.sock` (FIFOs; the names are kept from wob, which it replaced).
- A plain C Wayland client (wl_shm + wlr-layer-shell, no toolkit): ~1.5 MB of memory (a Python/GTK version took ~45 MB; wob itself only draws horizontal bars and no text).
- Started by the labwc autostart. Built for the image by `build/07b-osd.sh` (cross-compiled against the rootfs, `src/osd/Makefile`; needs `wayland-scanner` on the host). The wlr-layer-shell protocol description is vendored in `src/osd/protocol/` (see `THIRD-PARTY.md`).
- Not themed yet (stays dark).
