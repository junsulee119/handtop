"""The Videos app (rg35xxh-videos): the video files in ~/Videos (and on a mounted USB stick or
SD card) with thumbnails; a click plays that file in mpv, full screen, with the rest of the
folder as its playlist (R1 / R2 = next / previous). mpv's controls are themed by
/etc/mpv/scripts/handtop-osc.lua. docs/apps/videos.md."""
import os
import subprocess

from . import files, thumbs, ui  # noqa: E402  (ui sets the GTK versions first)
from gi.repository import Gdk, GLib, Gtk  # noqa: E402

APP_ID = "rg35xxh-videos"
TW, TH = 96, 54                         # thumbnail box (16:9)


class Videos:
    def __init__(self):
        ui.setup(APP_ID)
        self.loop = GLib.MainLoop()
        self.root = os.path.expanduser("~/Videos")
        os.makedirs(self.root, exist_ok=True)
        self.player = None
        self.thumbs = thumbs.Maker(self._thumb_done)
        self.win = Gtk.Window(title="Videos")
        self.win.set_default_size(640, 440)
        self.win.connect("destroy", lambda *_: self.loop.quit())
        self.win.connect("key-press-event", self._key)
        self.browser = ui.Browser(self.root, files.VIDEO, "Videos", self._row, self._play,
                                  folder_icon="folder-videos")
        self.win.add(self.browser)

    def run(self):
        self.win.show_all()
        self.browser.refresh()
        self.loop.run()

    def _key(self, _w, ev):
        if ev.keyval in (Gdk.KEY_Escape, Gdk.KEY_BackSpace):    # L1 / R2: up one folder
            self.browser.go_up()
            return True
        return False

    # ---- rows ------------------------------------------------------------------------------------
    def _row(self, folder, name):
        path = os.path.join(folder, name)
        box = Gtk.Box(spacing=10)
        frame = Gtk.Box()
        frame.set_size_request(TW, TH)
        frame.get_style_context().add_class("rg-thumb")
        img = Gtk.Image()
        frame.set_center_widget(img)
        box.pack_start(frame, False, False, 0)
        text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        text.set_valign(Gtk.Align.CENTER)
        text.pack_start(ui.label(files.title_of(name)), False, False, 0)
        pos = files.resume_pos(path)
        if pos:
            text.pack_start(ui.label(f"Resume at {files.fmt_time(pos)}", "rg-dim"), False, False, 0)
        box.pack_start(text, True, True, 0)
        box.img = img
        pb = thumbs.cached(path)
        if pb:
            self._set_thumb(img, pb)
        else:
            img.set_from_icon_name("video-x-generic", Gtk.IconSize.DND)
            self.thumbs.add(path)
        return box

    def _set_thumb(self, img, pb):
        w, h = pb.get_width(), pb.get_height()
        k = min(TW / w, TH / h)
        img.set_from_pixbuf(pb.scale_simple(max(1, int(w * k)), max(1, int(h * k)), 2))

    def _thumb_done(self, path, pb):
        folder, name = os.path.split(path)
        row = self.browser.rows.get(name)
        if row is not None and os.path.realpath(self.browser.path) == folder:
            self._set_thumb(row.img, pb)
        return False

    # ---- playing ---------------------------------------------------------------------------------
    def _play(self, folder, names, index):
        if self.player is not None:
            return                                   # mpv is already up (a double click)
        paths = [os.path.join(folder, n) for n in names]
        cmd = ["mpv", f"--playlist-start={index}", "--"] + paths
        try:
            self.player = subprocess.Popen(cmd, stdin=subprocess.DEVNULL,
                                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError:
            return
        GLib.child_watch_add(GLib.PRIORITY_DEFAULT, self.player.pid, self._player_done)

    def _player_done(self, _pid, _status):
        self.player = None                            # GLib has reaped it
        self.browser.refresh()                        # "Resume at ..." lines


def run():
    Videos().run()
