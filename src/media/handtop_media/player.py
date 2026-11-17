"""The Music app's player: libmpv (python3-mpv) with no video and no user config, so it plays
every format the system FFmpeg reads. mpv calls back on its own thread; everything here that
the window reads is handed over to the GLib main loop (changed() via GLib.idle_add)."""
import os

from gi.repository import GLib

REPEAT = ("off", "all", "one")
FLAG = "rg35xxh-music-playing"            # $XDG_RUNTIME_DIR: rg35xxh-autosleep does not sleep
                                          # while it exists and names a live Music process


def flag_path():
    return os.path.join(os.environ.get("XDG_RUNTIME_DIR", "/tmp"), FLAG)


class Player:
    # Not time-pos: mpv reports it many times a second, and redrawing on each cost ~30 % of a
    # core (measured 2026-11-17); the window reads it with time_pos() twice a second instead.
    WATCH = ("pause", "idle-active", "playlist-pos", "playlist-count", "duration", "metadata",
             "path", "loop-file", "loop-playlist")

    def __init__(self, changed, mpv_module=None):
        if mpv_module is None:
            import mpv as mpv_module
        self.changed = changed
        self.state = {k: None for k in self.WATCH}
        self.state["shuffle"] = False
        self.state["pause"] = True
        self.state["idle-active"] = True
        self._pending = False
        self.shuffled = False
        self.m = mpv_module.MPV(video=False, config=False, terminal=False, ytdl=False,
                                input_default_bindings=False, input_vo_keyboard=False,
                                idle=True, audio_display=False, keep_open=False,
                                gapless_audio="weak")
        for name in self.WATCH:
            self.m.observe_property(name, self._observe)

    # ---- state from mpv's thread -------------------------------------------------------------
    def _observe(self, name, value):
        self.state[name] = value
        if not self._pending:
            self._pending = True
            GLib.idle_add(self._flush)

    def _flush(self):
        self._pending = False
        self._write_flag()
        self.changed()
        return False

    @property
    def playing(self):
        return not self.state["pause"] and not self.state["idle-active"]

    def _write_flag(self):
        p = flag_path()
        try:
            if self.playing:
                tmp = p + ".tmp"
                with open(tmp, "w") as f:
                    f.write(f"{os.getpid()}\n")
                os.replace(tmp, p)
            elif os.path.exists(p):
                os.unlink(p)
        except OSError:
            pass

    # ---- commands ------------------------------------------------------------------------------
    def play(self, paths, index):
        """Replace the queue with paths and start at index."""
        if not paths:
            return
        self.m.command("stop")                # clears the playlist
        for p in paths:
            self.m.command("loadfile", p, "append")
        self.shuffled = False
        self.m.command("set", "playlist-pos", str(index))
        self.m.command("set", "pause", "no")

    def toggle(self):
        if self.state["idle-active"]:
            return
        self.m.command("cycle", "pause")

    def next(self):
        self.m.command("playlist-next", "weak")

    def time_pos(self):
        if self.state["idle-active"]:
            return None
        try:
            return self.m.time_pos
        except Exception:                     # noqa: BLE001 - mpv between files
            return None

    def prev(self):
        # Like most players: back to the start of the song when more than 3 s in.
        if (self.time_pos() or 0) > 3 or (self.state["playlist-pos"] or 0) == 0:
            self.m.command("seek", "0", "absolute")
        else:
            self.m.command("playlist-prev", "weak")

    def seek(self, sec):
        if not self.state["idle-active"]:
            self.m.command("seek", str(max(0.0, sec)), "absolute")

    def repeat(self):
        if self.state["loop-file"] not in (None, False, "no"):
            return "one"
        if self.state["loop-playlist"] not in (None, False, "no"):
            return "all"
        return "off"

    def cycle_repeat(self):
        nxt = REPEAT[(REPEAT.index(self.repeat()) + 1) % len(REPEAT)]
        self.m.command("set", "loop-playlist", "inf" if nxt == "all" else "no")
        self.m.command("set", "loop-file", "inf" if nxt == "one" else "no")
        return nxt

    def toggle_shuffle(self):
        self.m.command("playlist-unshuffle" if self.shuffled else "playlist-shuffle")
        self.shuffled = not self.shuffled
        self._observe("shuffle", self.shuffled)
        return self.shuffled

    def title(self):
        """(title, artist, album) of the current song, from its tags or its file name."""
        md = self.state["metadata"] or {}
        low = {str(k).lower(): v for k, v in md.items()}
        path = self.state["path"] or ""
        name = os.path.basename(path)
        t = low.get("title") or (name.rsplit(".", 1)[0] if "." in name else name)
        return t, low.get("artist") or low.get("album_artist") or "", low.get("album") or ""

    def close(self):
        try:
            self.m.terminate()
        finally:
            try:
                os.unlink(flag_path())
            except OSError:
                pass
