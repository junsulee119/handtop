"""The Music app (rg35xxh-music): the songs in ~/Music (and on a mounted USB stick or SD card),
folder by folder; a click plays that song and then the rest of its folder. A bar at the bottom
shows what is playing; "Now playing" has the cover, a seek bar, shuffle and repeat.
Playback stops when the window is closed. docs/apps/music.md."""
import hashlib
import os
import subprocess
import threading

from . import files, ui  # noqa: E402  (ui sets the GTK versions first)
from .player import Player  # noqa: E402
from gi.repository import Gdk, GdkPixbuf, GLib, Gtk  # noqa: E402

APP_ID = "rg35xxh-music"
COVER = 176                          # Now playing cover, px
SMALL = 40                           # folder and bar covers, px
REPEAT_ICON = {"off": "media-playlist-repeat", "all": "media-playlist-repeat",
               "one": "media-playlist-repeat-song"}
REPEAT_TIP = {"off": "Repeat: off", "all": "Repeat: all songs", "one": "Repeat: this song"}


def cover_cache():
    base = os.environ.get("XDG_CACHE_HOME") or os.path.expanduser("~/.cache")
    return os.path.join(base, "rg35xxh-music", "covers")


def embedded_cover(path):
    """The song's own picture (an attached cover), extracted once into the cache; None if it
    has none. Runs ffmpeg: call it off the main loop."""
    try:
        st = os.stat(path)
    except OSError:
        return None
    key = hashlib.md5(f"{path}\0{int(st.st_mtime)}\0{st.st_size}".encode(
        "utf-8", "surrogateescape")).hexdigest()
    out = os.path.join(cover_cache(), key + ".png")
    none = out + ".none"
    if os.path.exists(out):
        return out
    if os.path.exists(none):
        return None
    os.makedirs(cover_cache(), mode=0o700, exist_ok=True)
    tmp = out + ".tmp.png"
    try:
        subprocess.run(["nice", "-n", "10", "ffmpeg", "-nostdin", "-v", "error", "-y", "-i", path,
                        "-an", "-map", "0:v:0", "-frames:v", "1", "-vf",
                        f"scale={COVER * 2}:{COVER * 2}:force_original_aspect_ratio=decrease",
                        tmp], timeout=20, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                       check=False)
        if os.path.exists(tmp) and os.path.getsize(tmp) > 0:
            os.replace(tmp, out)
            return out
        open(none, "w").close()
    except (OSError, subprocess.TimeoutExpired):
        pass
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    return None


def pixbuf(path, size):
    try:
        return GdkPixbuf.Pixbuf.new_from_file_at_scale(path, size, size, True)
    except GLib.Error:
        return None


class Music:
    def __init__(self):
        ui.setup(APP_ID)
        self.loop = GLib.MainLoop()
        self.root = os.path.expanduser("~/Music")
        os.makedirs(self.root, exist_ok=True)
        self.player = Player(self._changed)
        self.cover_for = None                # the song whose cover is shown
        self.win = Gtk.Window(title="Music")
        self.win.set_default_size(640, 440)
        self.win.connect("destroy", self._quit)
        self.win.connect("key-press-event", self._key)
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.stack = Gtk.Stack()
        self.stack.set_transition_type(Gtk.StackTransitionType.NONE)
        self.now_btn = ui.icon_button("audio-x-generic", "What is playing", self.show_now,
                                      label="Now playing")
        self.browser = ui.Browser(self.root, files.AUDIO, "Music", self._row, self._play,
                                  extra_head=(self.now_btn,), folder_icon="folder-music")
        self.browser.folder_image = self._folder_image
        self.stack.add_named(self.browser, "library")
        self.stack.add_named(self._now_page(), "now")
        outer.pack_start(self.stack, True, True, 0)
        outer.pack_start(self._bar(), False, False, 0)
        self.win.add(outer)

    def run(self):
        self._shown_times = None
        GLib.timeout_add(500, self._tick)
        self.win.show_all()
        self.browser.refresh()
        self._changed()
        self.loop.run()

    def _quit(self, *_):
        self.player.close()
        self.loop.quit()

    def _key(self, _w, ev):
        if ev.keyval in (Gdk.KEY_Escape, Gdk.KEY_BackSpace):         # L1 / R2: back
            if self.stack.get_visible_child_name() == "now":
                self.show_library()
            else:
                self.browser.go_up()
            return True
        if ev.keyval == Gdk.KEY_space:
            self.player.toggle()
            return True
        return False

    # ---- library ---------------------------------------------------------------------------------
    def _folder_image(self, path):
        c = files.cover_file(path)
        return pixbuf(c, SMALL) if c else None

    def _row(self, folder, name):
        box = Gtk.Box(spacing=10)
        img = Gtk.Image()
        img.set_pixel_size(24)
        box.pack_start(img, False, False, 8)
        box.pack_start(ui.label(files.title_of(name)), True, True, 0)
        box.img = img
        box.path = os.path.join(folder, name)
        self._mark(box)
        return box

    def _mark(self, box):
        on = box.path == self.player.state["path"]
        box.img.set_from_icon_name("media-playback-start" if on else "audio-x-generic",
                                   Gtk.IconSize.LARGE_TOOLBAR)
        box.img.set_opacity(1.0 if on else 0.6)

    def _play(self, folder, names, index):
        self.player.play([os.path.join(folder, n) for n in names], index)

    def show_now(self):
        self.stack.set_visible_child_name("now")
        self._changed()

    def show_library(self):
        self.stack.set_visible_child_name("library")
        self._changed()

    # ---- now playing -----------------------------------------------------------------------------
    def _now_page(self):
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        head = Gtk.Box(spacing=6)
        head.get_style_context().add_class("rg-head")
        head.pack_start(ui.icon_button("go-previous", "Back to the songs (L1)", self.show_library,
                                       label="Songs"), False, False, 0)
        self.b_off = ui.icon_button("video-display", "Turn the screen off; the music goes on. "
                                    "Vol still works, any other button turns it back on.",
                                    self.screen_off, label="Screen off")
        head.pack_end(self.b_off, False, False, 0)
        page.pack_start(head, False, False, 0)
        body = Gtk.Box(spacing=16)
        body.set_margin_start(16)
        body.set_margin_end(16)
        body.set_margin_top(8)
        self.cover = Gtk.Image()
        self.cover.set_size_request(COVER, COVER)
        self.cover.get_style_context().add_class("rg-thumb")
        self.cover.set_valign(Gtk.Align.START)
        body.pack_start(self.cover, False, False, 0)
        text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.t_title = ui.label("", "rg-title", ellipsize=False)
        self.t_title.set_line_wrap(True)
        self.t_title.set_lines(3)
        self.t_artist = ui.label("")
        self.t_album = ui.label("", "rg-dim")
        self.t_pos = ui.label("", "rg-dim")
        for w in (self.t_title, self.t_artist, self.t_album, self.t_pos):
            text.pack_start(w, False, False, 0)
        body.pack_start(text, True, True, 0)
        page.pack_start(body, True, True, 0)
        # Seek bar with the times on each side.
        seek = Gtk.Box(spacing=8)
        seek.set_margin_start(12)
        seek.set_margin_end(12)
        self.l_time = ui.label("0:00", xalign=1.0)
        self.l_time.set_width_chars(5)
        self.r_time = ui.label("0:00")
        self.r_time.set_width_chars(5)
        self.scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 1, 1)
        self.scale.set_draw_value(False)
        self.scale.connect("change-value", lambda _s, _t, v: self.player.seek(v) or False)
        seek.pack_start(self.l_time, False, False, 0)
        seek.pack_start(self.scale, True, True, 0)
        seek.pack_start(self.r_time, False, False, 0)
        page.pack_start(seek, False, False, 4)
        # The buttons.
        row = Gtk.Box(spacing=12)
        row.set_halign(Gtk.Align.CENTER)
        row.set_margin_bottom(10)
        self.b_shuffle = Gtk.ToggleButton()
        self.b_shuffle.add(Gtk.Image.new_from_icon_name("media-playlist-shuffle",
                                                        Gtk.IconSize.LARGE_TOOLBAR))
        self.b_shuffle.set_tooltip_text("Shuffle")
        self.b_shuffle.get_style_context().add_class("rg-big")
        self.b_shuffle.set_relief(Gtk.ReliefStyle.NONE)
        self.b_shuffle.connect("toggled", self._shuffle)
        self.b_repeat = Gtk.ToggleButton()
        self.repeat_img = Gtk.Image()
        self.b_repeat.add(self.repeat_img)
        self.b_repeat.get_style_context().add_class("rg-big")
        self.b_repeat.set_relief(Gtk.ReliefStyle.NONE)
        self.b_repeat.connect("toggled", self._repeat)
        self.b_play = ui.icon_button("media-playback-start", "Play / pause", self.player.toggle,
                                     big=True)
        row.pack_start(self.b_shuffle, False, False, 0)
        row.pack_start(ui.icon_button("media-skip-backward", "Previous", self.player.prev,
                                      big=True), False, False, 0)
        row.pack_start(self.b_play, False, False, 0)
        row.pack_start(ui.icon_button("media-skip-forward", "Next", self.player.next, big=True),
                       False, False, 0)
        row.pack_start(self.b_repeat, False, False, 0)
        page.pack_start(row, False, False, 0)
        self._syncing = False
        return page

    def screen_off(self):
        """The screen off with the music playing (rg35xxh-screen-off --music); docs/apps/music.md."""
        if not self.player.playing:
            return
        try:
            subprocess.Popen(["rg35xxh-screen-off", "--music"], stdin=subprocess.DEVNULL,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                             start_new_session=True)
        except OSError:
            pass

    def _shuffle(self, b):
        if not self._syncing and b.get_active() != self.player.shuffled:
            self.player.toggle_shuffle()

    def _repeat(self, _b):
        if not self._syncing:
            self.player.cycle_repeat()

    # ---- the bar at the bottom -------------------------------------------------------------------
    def _bar(self):
        bar = Gtk.Box(spacing=6)
        bar.get_style_context().add_class("rg-bar")
        self.bar = bar
        self.bar_cover = Gtk.Image()
        self.bar_cover.set_size_request(SMALL, SMALL)
        open_now = Gtk.Button()
        open_now.set_relief(Gtk.ReliefStyle.NONE)
        open_now.set_tooltip_text("Now playing")
        inner = Gtk.Box(spacing=8)
        inner.pack_start(self.bar_cover, False, False, 0)
        lines = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        lines.set_valign(Gtk.Align.CENTER)
        self.bar_title = ui.label("")
        self.bar_sub = ui.label("", "rg-dim")
        lines.pack_start(self.bar_title, False, False, 0)
        lines.pack_start(self.bar_sub, False, False, 0)
        inner.pack_start(lines, True, True, 0)
        open_now.add(inner)
        open_now.connect("clicked", lambda *_: self.show_now())
        bar.pack_start(open_now, True, True, 0)
        self.bar_play = ui.icon_button("media-playback-start", "Play / pause", self.player.toggle,
                                       big=True)
        bar.pack_start(self.bar_play, False, False, 0)
        bar.pack_start(ui.icon_button("media-skip-forward", "Next", self.player.next, big=True),
                       False, False, 0)
        return bar

    # ---- updates ---------------------------------------------------------------------------------
    def _changed(self):
        st = self.player.state
        idle = st["idle-active"] or not st["path"]
        title, artist, album = self.player.title()
        on_now = self.stack.get_visible_child_name() == "now"
        self.bar.set_visible(not idle and not on_now)
        self.now_btn.set_visible(not idle)
        self.b_off.set_sensitive(self.player.playing)
        icon = "media-playback-start" if st["pause"] or idle else "media-playback-pause"
        for b in (self.b_play, self.bar_play):
            b.get_child().set_from_icon_name(icon, Gtk.IconSize.LARGE_TOOLBAR)
        if idle and on_now:
            self.show_library()
            return
        self.bar_title.set_text(title)
        self.bar_sub.set_text(" · ".join(x for x in (artist, album) if x))
        self.t_title.set_text(title)
        self.t_artist.set_text(artist)
        self.t_album.set_text(album)
        n, pos = st["playlist-count"] or 0, st["playlist-pos"]
        self.t_pos.set_text(f"Song {pos + 1} of {n}" if n > 1 and pos is not None and pos >= 0
                            else "")
        self._tick()
        self._syncing = True
        self.b_shuffle.set_active(self.player.shuffled)
        rep = self.player.repeat()
        self.b_repeat.set_active(rep != "off")
        self.repeat_img.set_from_icon_name(REPEAT_ICON[rep], Gtk.IconSize.LARGE_TOOLBAR)
        self.b_repeat.set_tooltip_text(REPEAT_TIP[rep])
        self._syncing = False
        if st["path"] != self.cover_for:
            self.cover_for = st["path"]
            self._load_cover(st["path"])
            for row in self.browser.rows.values():
                self._mark(row)

    def _tick(self):
        """The seek bar and times: twice a second while Now playing shows (and on changes)."""
        if self.stack.get_visible_child_name() != "now" or self._screen_is_off():
            return True
        dur = self.player.state["duration"] or 0
        t = self.player.time_pos() or 0
        if not self.scale.has_grab():
            self.scale.set_range(0, max(dur, 1))
            self.scale.set_value(min(t, max(dur, 1)))
        shown = (files.fmt_time(t) or "0:00", files.fmt_time(dur) or "0:00")
        if shown != self._shown_times:
            self._shown_times = shown
            self.l_time.set_text(shown[0])
            self.r_time.set_text(shown[1])
        return True

    @staticmethod
    def _screen_is_off():
        return os.path.exists(os.path.join(os.environ.get("XDG_RUNTIME_DIR", "/tmp"),
                                           "rg35xxh-screen-off"))

    def _load_cover(self, path):
        self._show_cover(None)
        if not path:
            return

        def work():
            c = files.cover_file(os.path.dirname(path)) or embedded_cover(path)
            GLib.idle_add(self._cover_ready, path, c)
        threading.Thread(target=work, daemon=True).start()

    def _cover_ready(self, path, cover):
        if path == self.cover_for:
            self._show_cover(cover)
        return False

    def _show_cover(self, cover):
        big = pixbuf(cover, COVER) if cover else None
        if big:
            self.cover.set_from_pixbuf(big)
            self.bar_cover.set_from_pixbuf(pixbuf(cover, SMALL))
        else:
            self.cover.set_from_icon_name("audio-x-generic", Gtk.IconSize.DIALOG)
            self.cover.set_pixel_size(96)
            self.bar_cover.set_from_icon_name("audio-x-generic", Gtk.IconSize.DND)
            self.bar_cover.set_pixel_size(32)


def run():
    Music().run()
