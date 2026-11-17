# Videos and the video player

Apps → **Videos** (`rg35xxh-videos`, code in `src/media/handtop_media/videos.py`) lists the videos in `~/Videos` and plays them in **mpv**, full screen, with Handtop's look on mpv's own controls. Opening a video from the File Manager uses the same mpv set-up.

## Why mpv (decided 2026-11-17)

mpv is the only player on the zero-copy VPU path ([../video-decode.md](../video-decode.md)): 11–18 % of one core at 1080p. Rejected:

- **Celluloid** (a GTK front end for mpv): it uses GTK4 and libadwaita, which ignore Handtop's GTK3 themes. Its libmpv render path loses dmabuf-wayland, which costs about twice the CPU (21 % against 11 % measured on `vo=gpu`). Its controls are small desktop ones.
- **Parole**: it plays through GStreamer, which has no VPU path here.

## The Videos app

- The list shows folders first, then video files, in natural order (Track 2 before Track 10). Hidden files are left out. Each video has a 96×54 thumbnail and a **Resume at m:ss** line when mpv has a saved position for it.
- Thumbnails go into the shared freedesktop cache (`~/.cache/thumbnails/normal`, with `Thumb::URI` / `Thumb::MTime`), so the File Manager and the app share them. They're made one at a time in a background thread with the ffmpeg CLI (a frame 10 s in, or the first frame of a shorter file), at `nice 10`, with a 20 s limit per file.
- **Up** (or L1 / R2) goes up one folder. It stops at `~/Videos`, except that a mounted USB stick or SD card (`/media/<user>/…`) adds a **Places** level above it.
- A click plays that file with the rest of the folder as the playlist (`mpv --playlist-start=N -- <files>`). R1 / R2 in mpv go to the next and previous file. When mpv closes, the list is refreshed for the resume lines.
- One window per app: a second start brings the first one to the front (`wlrctl toplevel focus app_id:rg35xxh-videos`) and ends.
- `~/Videos` is created if it's missing.

## mpv's set-up (`overlay/etc/mpv/`)

- **`mpv.conf`**:
  - `fs=yes`: videos open full screen.
  - `save-position-on-quit=yes`: each closed file resumes where it was left. The position goes to `~/.local/state/mpv/watch_later/`, a few hundred bytes per file; a file played to the end starts from the beginning.
  - The rest is the hardware decoding set-up (video-decode.md).
- **`scripts/handtop-osc.lua`**: mpv's built-in on-screen controller (OSC), in the theme's colours and font. It reads `theme.env` (`PALETTE_BG`, `PALETTE_FG`, `PALETTE_ACCENT_FG`, `FONT_UI`), never a theme file, with Handtop dark's values when nothing is rendered.
  - It uses the **box** layout at 1.5× (`vidscale=no`, `scalefullscreen=1.5`): the box fills the screen's width with about 30 px buttons, easy to hit with the D-pad pointer. At 1× the box is about 360 px wide with 16 px buttons.
  - On the first file it shows a 4-second hint: "A: play / pause · L1: close · Right stick: seek · R1 / R2: next / previous".
  - It only sets options that aren't set already, and a user's `~/.config/mpv/script-opts/osc.conf` still wins.
  - Tried: the bottom bar, larger with `scalefullscreen`. It stayed small at this width, so the box layout was used instead.
- **`scripts/handtop-seek.lua`**: the right-stick seek (below). Each step also shows the controls (`script-message-to osc osc-show`), as moving the pointer does, so the seek bar shows where the stick is going (Jason, 2026-11-17); they hide again after 2.5 s.
- **`input.conf`**, for the buttons as the input daemon sends them in desktop mode:

| Button | Sends | In mpv |
|---|---|---|
| A | left click | on the controls: that control; on the picture: play / pause. A double click does **not** leave full screen (no other way back on the handheld) |
| B | right click | play / pause (mpv's default); on the track buttons of the controls: the track list |
| L1 | Esc | close (position remembered) |
| R1 / R2 | Enter / Backspace | next / previous file in the playlist |
| Right stick | scroll wheel | seek, up / right forward, down / left back: faster the further it is pushed, by a share of the video's length (1.19 % per wheel step), **at most 10 % of the video a second** (`scripts/handtop-seek.lua`, Jason 2026-11-17). At the default scroll speed (8.4 steps a second at full tilt) full tilt is exactly that 10 %; a higher scroll speed in Controls can't go past it (a token bucket that refills at 10 % a second and holds one step). The steps add up to an absolute, exact target: relative seeks sent while one is still running were merged by mpv and lost steps (7 % a second instead of 10), and a 1 % keyframe seek snaps back to the same keyframe. Was 10 s per step: too sensitive on short videos |
| D-pad, left stick | pointer | shows the controls |

A user's `~/.config/mpv/input.conf` is read after this one and wins.

Auto-sleep: mpv blocks idle while it plays (Wayland idle-inhibit), so a playing video never sleeps. A paused one sleeps after the usual 10 minutes.

## Tested (2026-11-17, DDR4)

- Box controls in Handtop dark's colours over a 720p H.264 file, decoded on the VPU (`Using hardware decoding (drm)`, `VO: [dmabuf-wayland]`).
- Right-stick seek on a 60 s clip through mpv's IPC: 9 steps at the default full-tilt rate moved 6.4 s in 1.08 s (9.9 % a second); 30 steps a second for 1 s moved 6.7 s (capped); 3 slow steps back moved 2.1 s.
- The other bindings, through mpv's IPC (`keypress`): ENTER → playlist 1, BS → 0, ESC quits and writes the watch-later file.
- The app: thumbnails made and cached, folder navigation, a click starts mpv with the folder as the playlist, "Resume at 0:02" after closing.
