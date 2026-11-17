"""GTK pieces both media apps use: one window per app, the theme's look, and the folder browser.
Colours come from the GTK theme the current Handtop theme renders (gtk.css), like the Controls
app; sizes are for 640x480 and the D-pad pointer (rows at least 48 px tall, A = click)."""
import fcntl
import os
import subprocess
import sys

import gi
gi.require_version("Gdk", "3.0")
gi.require_version("Gtk", "3.0")
from gi.repository import Gdk, GLib, Gtk, Pango  # noqa: E402

from . import files  # noqa: E402

CSS = b"""
.rg-row { padding: 4px 8px; min-height: 48px; }
.rg-head { padding: 4px 6px; }
.rg-head-title { font-weight: bold; }
.rg-dim { opacity: 0.7; }
.rg-empty { padding: 24px; }
.rg-big { min-width: 56px; min-height: 48px; }
.rg-thumb { background-color: alpha(@theme_fg_color, 0.08); }
.rg-title { font-size: 130%; font-weight: bold; }
.rg-bar { border-top: 1px solid alpha(@theme_fg_color, 0.25); padding: 4px 6px; }
"""


def single_instance(app_id):
    """Keep one window per app: a second start brings the first one to the front and ends. The
    lock is held for the life of the process (the returned file must stay referenced)."""
    path = os.path.join(os.environ.get("XDG_RUNTIME_DIR", "/tmp"), f"{app_id}.lock")
    lock = open(path, "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        subprocess.run(["wlrctl", "toplevel", "focus", f"app_id:{app_id}"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        sys.exit(0)
    return lock


def setup(app_id):
    GLib.set_prgname(app_id)                  # Wayland app_id = the .desktop id: taskbar icon
    prov = Gtk.CssProvider()
    prov.load_from_data(CSS)
    Gtk.StyleContext.add_provider_for_screen(Gdk.Screen.get_default(), prov,
                                             Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)


def icon_button(icon, tip, cb, big=False, label=None):
    b = Gtk.Button()
    img = Gtk.Image.new_from_icon_name(icon, Gtk.IconSize.LARGE_TOOLBAR if big
                                       else Gtk.IconSize.BUTTON)
    if label:
        box = Gtk.Box(spacing=6)
        box.pack_start(img, False, False, 0)
        box.pack_start(Gtk.Label(label=label), False, False, 0)
        b.add(box)
    else:
        b.add(img)
    b.set_tooltip_text(tip)
    b.set_relief(Gtk.ReliefStyle.NONE)
    if big:
        b.get_style_context().add_class("rg-big")
    b.connect("clicked", lambda *_: cb())
    return b


def label(text, cls=None, xalign=0.0, ellipsize=True):
    lb = Gtk.Label(label=text, xalign=xalign)
    if ellipsize:
        lb.set_ellipsize(Pango.EllipsizeMode.END)
    if cls:
        for c in cls.split():
            lb.get_style_context().add_class(c)
    return lb


class Browser(Gtk.Box):
    """A folder list: a header (Up, the folder's name) over big rows, folders first.

    root    the app's folder (~/Videos, ~/Music); Up stops there, except that it then shows the
            places (the folder and any mounted USB stick or SD card) when a drive is mounted
    kinds   the file extensions shown
    make_file_row(folder, name) -> Gtk.Widget for a file
    on_file(folder, names, index)  a file was clicked; names = the folder's files in order
    extra_head  widgets packed at the end of the header (the Music app's Now playing button)
    """

    PLACES = "\0places"

    def __init__(self, root, kinds, root_name, make_file_row, on_file, extra_head=(),
                 folder_icon="folder"):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.root, self.kinds, self.root_name = root, kinds, root_name
        self.make_file_row, self.on_file = make_file_row, on_file
        self.folder_icon = folder_icon
        self.path = root
        self.files = []
        head = Gtk.Box(spacing=6)
        head.get_style_context().add_class("rg-head")
        self.up = icon_button("go-up", "Up one folder (L1)", self.go_up, label="Up")
        head.pack_start(self.up, False, False, 0)
        self.title = label("", "rg-head-title")
        head.pack_start(self.title, True, True, 0)
        for w in extra_head:
            head.pack_end(w, False, False, 0)
        self.pack_start(head, False, False, 0)
        self.scroll = Gtk.ScrolledWindow()
        self.scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.list = Gtk.ListBox()
        self.list.set_selection_mode(Gtk.SelectionMode.NONE)
        self.list.connect("row-activated", self._activated)
        self.scroll.add(self.list)
        self.pack_start(self.scroll, True, True, 0)
        self.empty = label("", "rg-empty rg-dim", xalign=0.5, ellipsize=False)
        self.empty.set_line_wrap(True)
        self.pack_start(self.empty, False, False, 0)
        self.rows = {}                  # file name -> its row widget (for thumbnails)
        self.folder_image = None        # folder path -> pixbuf (an album cover) or None

    # ---- navigation ------------------------------------------------------------------------------
    def at_top(self):
        if self.path == self.PLACES:
            return True
        if files.under(self.path, self.root) and os.path.realpath(self.path) == \
                os.path.realpath(self.root):
            return not files.drives()
        return False

    def go_up(self):
        if self.path == self.PLACES:
            return False
        real = os.path.realpath(self.path)
        if real == os.path.realpath(self.root) or os.path.dirname(real) == real or \
                any(real == os.path.realpath(p) for _, p in files.drives()):
            if not files.drives():
                return False
            self.open(self.PLACES)
            return True
        self.open(os.path.dirname(real))
        return True

    def open(self, path):
        self.path = path
        self.refresh()

    def refresh(self):
        for row in self.list.get_children():
            self.list.remove(row)
        self.rows = {}
        if self.path == self.PLACES:
            self.title.set_text("Places")
            entries = [(self.root_name, self.root, "folder")] + \
                      [(n, p, "drive-removable-media") for n, p in files.drives()]
            for name, p, icon in entries:
                self._add(self._folder_row(name, icon), ("dir", p))
            self.files = []
        else:
            if not os.path.isdir(self.path):        # a drive pulled out, a folder deleted
                self.path = self.root
            folders, names = files.listing(self.path, self.kinds)
            real = os.path.realpath(self.path)
            self.title.set_text(self.root_name if real == os.path.realpath(self.root)
                                else os.path.basename(real) or real)
            for n in folders:
                p = os.path.join(real, n)
                self._add(self._folder_row(n, self.folder_icon, p), ("dir", p))
            self.files = names
            for i, n in enumerate(names):
                w = self.make_file_row(real, n)
                self.rows[n] = w
                self._add(w, ("file", i))
            if not folders and not names:
                self.empty.set_text("Nothing here yet. Copy files into this folder with the "
                                    "File Manager, a USB stick or over the network.")
        self.empty.set_visible(not self.list.get_children())
        self.list.set_visible(bool(self.list.get_children()))
        self.up.set_sensitive(not self.at_top())
        self.list.show_all()
        self.scroll.get_vadjustment().set_value(0)

    def _folder_row(self, name, icon, path=None):
        box = Gtk.Box(spacing=10)
        pb = self.folder_image(path) if path and self.folder_image else None
        img = Gtk.Image.new_from_pixbuf(pb) if pb else \
            Gtk.Image.new_from_icon_name(icon, Gtk.IconSize.DND)
        img.set_size_request(40, 40)
        box.pack_start(img, False, False, 0)
        box.pack_start(label(name), True, True, 0)
        return box

    def _add(self, child, what):
        row = Gtk.ListBoxRow()
        row.get_style_context().add_class("rg-row")
        row.what = what
        row.add(child)
        self.list.add(row)

    def _activated(self, _lb, row):
        kind, v = row.what
        if kind == "dir":
            self.open(v)
        else:
            self.on_file(os.path.realpath(self.path), list(self.files), v)
