# Boot screen

From early boot until the desktop appears, the handheld shows the Handtop boot screen instead of
console text: the logo on the left with keys lighting up on its keyboard like someone typing, and a
box on the right with the live boot log.

| Piece | What it does |
|---|---|
| `rg35xxh-bootlogo.service` | Starts as early as systemd can (`DefaultDependencies=no`, before `sysinit.target`; the root file system is mounted by the kernel already). Runs `rg35xxh-bootlogo show`. |
| `rg35xxh-bootlogo show` | Detaches the text console from the framebuffer (`/sys/class/vtconsole/vtcon*/bind`, the "frame buffer device" one) so no login text or cursor draws over the screen, writes the still logo (`bootlogo.xrgb.gz`, 2 KB) to `/dev/fb0` at once, then runs `rg35xxh-bootsplash`. |
| `rg35xxh-bootsplash` (`src/bootsplash`) | The animation and the log, drawn straight into `/dev/fb0` (XRGB8888). Keys: 3 lit keys walking across the keyboard, ~8 frames/s, only the logo rows redrawn. Log: `journalctl -b -f -o cat _PID=1` (started again every second until journald is up), one line per unit: `..` while it starts, `OK` when started / finished / mounted / reached, `FAIL` in red (stays). Descriptions, not unit names; cut with "…". Plain C, libc only: logo, layout and a pre-rendered Noto Sans Mono come from `assets.h` (`tools/icons/gen_logo.py`). Stops after 180 s at the latest. |
| `rg35xxh-bootlogo-done.service` | After `getty@tty1` (`Type=simple`, so `multi-user.target` does not wait for it): waits until labwc runs (up to 60 s), 2 s more, stops the boot screen and gives the framebuffer back to the text console, so logging out or a failed desktop start shows text again. |

Not covered: the first 1-2 s (U-Boot and the kernel) before systemd starts.

Test without a screen: `rg35xxh-bootsplash --dump out.ppm <frame> < journal-lines.txt` draws one
frame from sample log lines into a PPM file.

Build: `build/07c-bootsplash.sh` (cross-compiled against the rootfs, like the volume bar).
