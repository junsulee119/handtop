# Music

Apps → **Music** (`rg35xxh-music`, code in `src/media/handtop_media/music.py` and `player.py`) plays the songs in `~/Music`, folder by folder. It's Handtop's own app: Python and GTK3 like Controls, with libmpv (python3-mpv) as the player, so it plays every format the system FFmpeg reads (MP3, FLAC, Ogg / Opus, AAC / M4A, WAV, …).

Why our own app (decided 2026-11-17): Rhythmbox and Lollypop are built around a library database, and their dense desktop layouts are cramped at 640×480 (Lollypop is also a heavy Python app). Debian builds Audacious with Qt, so Handtop's themes wouldn't apply to it.

## Using it

- **Songs page:** the same folder browser as Videos (`ui.Browser`): folders first, then songs, in natural order, with Up / L1 / R2 and the Places level for USB sticks and SD cards.
  - A folder with a cover picture (`cover`, `folder`, `front` or `album` + `.jpg` / `.jpeg` / `.png`, any case) shows it instead of the folder icon.
  - A click on a song plays it, then the rest of its folder. The song that is playing is marked.
- **The bar at the bottom** (while something is loaded): cover, title, artist · album, play / pause, next. A click on the title opens Now playing.
- **Now playing:**
  - The cover (176 px): the folder's cover picture, else the picture inside the song, extracted once with ffmpeg into `~/.cache/rg35xxh-music/covers/`, else a note icon.
  - Title (tags, else the file name), artist, album, "Song n of m".
  - A seek bar with the times.
  - Shuffle, previous (back to the start of the song when more than 3 s in), play / pause, next, and repeat (off → all songs → this song).
  - **Screen off** (see below). L1 goes back to the songs, and Space plays / pauses.
- Closing the window stops the music. One window per app: a second start brings it to the front.
- `~/Music` is created if it's missing.

## Keeping the handheld awake, and the screen off (Jason's decisions, 2026-11-17)

- **No auto-sleep while music plays.** While it plays (not paused), the app keeps its PID in `$XDG_RUNTIME_DIR/rg35xxh-music-playing`, and `rg35xxh-autosleep` skips sleeping while that file names a live Music process. A file left by a crash names a dead process and is ignored; the next session's autostart removes it.
- **Screen off with the music playing**, two ways:
  - the **Screen off** button on Now playing;
  - **5 minutes without input** while music plays (`MUSIC_SCREEN_OFF_MINUTES=5` in `/etc/rg35xxh/power.conf`, 0 = the screen stays on). swayidle runs `rg35xxh-music-idle`, which does nothing unless music is playing or when an HDMI monitor is connected. There's no dim warning first: the dim belongs to a coming sleep, and this isn't one.
- Both run `rg35xxh-screen-off --music`: the usual Screen off ([power-menu.md](power-menu.md)), but `rg35xxh-lowpower on-audio` leaves the audio DAC on. The backlight is off, CPU cores 1–3 are offline and the governors are at powersave as before. One core at powersave plays a 320 kbit/s MP3 or a FLAC at about 12 % of it, with no underruns over 40 s (pw-top ERR count unchanged, measured 2026-11-17).
- **While the screen is off:** Vol + / − change the volume and the screen stays off (always the volume, whatever Vol is bound to in Controls; it repeats while held). Any other button turns the screen back on, and that press is not acted on (the input daemon reads `music` on the flag's first line).
- **When the music stops with the screen still off** (the end of the queue): after 60 s (`MUSIC_STOPPED_SECONDS`), `rg35xxh-music-idle` turns the screen back on and then runs `rg35xxh-autosleep`, which sleeps unless it skips for its usual reasons (charging, HDMI, a controller mode). The screen comes on first because sleeping in the low-power state, with cores 1–3 offline, was never tested ([../hardware-safety.md](../hardware-safety.md) rule 6). Without this step the screen would stay off with nothing playing until the battery warning, because swayidle doesn't fire again without input.
- **Waking from Screen off now counts as input** for swayidle: the input daemon swallows the waking press, so after it the daemon moves the pointer one pixel and back (`_idle_nudge`). Before, a screen woken this way never auto-slept or turned off again until the next real input. This applies to the plain Screen off too.
- The low-battery levels for Screen off apply as they are: at 20 % the screen comes back on with a warning, at 5 % a clean shutdown.

**Trade-off (accepted):** the screen stays on for the first 5 minutes of music without input, and the handheld stays awake (screen off) for as long as music plays.

## Performance

- mpv reports `time-pos` many times a second. Redrawing on each report cost about 30 % of a core, so the app doesn't observe it: it reads it twice a second, only while Now playing shows and the screen is on.
- Measured while playing a FLAC (2026-11-17): 5 % of a core on the songs page and 7 % on Now playing, decoding included. About 100 MB of resident memory (GTK + libmpv).

## Tested (2026-11-17, DDR4)

- Browsing with folder covers, playing, the bar, Now playing (cover from the folder), seek, shuffle, repeat all / one, previous, next.
- The PID file appears and disappears with play / pause, and `rg35xxh-autosleep --music-playing` / `--check` agree.
- A second start focuses the first window.
- `rg35xxh-music-idle` (short stop time): flag `music`, one core online, DAC `[on]`, backlight off. The app then ended: 20 s later the screen came back on and auto-sleep ran (skipped: charging).
- Unit tests: `src/media/tests` (folder listing, covers, resume positions, the player with a fake mpv); input daemon tests for Vol in music Screen off and the wake nudge.
