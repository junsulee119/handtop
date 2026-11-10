"""The Theme app's window (rg35xxh-theme with no arguments). 640x480, every control reachable
with the D-pad / pointer and A; Escape (B) goes back from a sub-screen.

  Main       the installed themes (built-in first, then "Yours") on the left, with Import and
             Export icon buttons above them; the selected theme's preview, name and description
             on the right with Apply, Duplicate and Delete (your themes only)
  Duplicate  name, accent, background, icon set, pointer size, text size, live preview
  Import     .handtop-theme files in ~, ~/Themes, ~/Downloads and mounted drives; refused files
             list every problem (nothing changes)
  Export     to ~/Themes or a mounted drive
Applying is rg35xxh-theme's apply(); everything else is the handtop_theme package."""
import os
import subprocess

import cairo
import gi
gi.require_version("Gdk", "3.0")
gi.require_version("Gtk", "3.0")
from gi.repository import Gdk, GLib, Gtk  # noqa: E402

from . import customize as Z  # noqa: E402
from . import package, preview  # noqa: E402
from . import theme as T  # noqa: E402

ICONS = "/usr/local/share/rg35xxh/icons"
ORDER = ("handtop-dark", "handtop-light", "handtop-debian", "handtop-high-contrast", "handtop-grayscale")
PW, PH = 352, 264          # main preview
SW, SH = 208, 156          # Duplicate's live preview
CSS = b"""
.rg-swatch { min-width: 24px; min-height: 24px; padding: 0; border-radius: 6px; background-image: none;
             border: 1px solid rgba(128, 128, 128, 0.7); }
.rg-swatch:checked { border: 3px solid @theme_fg_color; }
.rg-error { background-color: rgba(200, 60, 60, 0.16); border: 1px solid rgba(220, 90, 90, 0.85);
            border-radius: 6px; padding: 8px; }
.rg-section { font-size: 0.8em; font-weight: bold; opacity: 0.7; }
"""


def _pixbuf(surf):
    return Gdk.pixbuf_get_from_surface(surf, 0, 0, surf.get_width(), surf.get_height())


def _rgb(c):
    return tuple(int(c[i:i + 2], 16) / 255 for i in (1, 3, 5))


def _swatch_image(t):
    """bg | accent, 32x16, for the theme list."""
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, 34, 18)
    cr = cairo.Context(surf)
    for i, k in enumerate(("bg", "accent")):
        cr.set_source_rgb(*_rgb(t.palette[k]))
        cr.rectangle(1 + i * 16, 1, 16, 16)
        cr.fill()
    cr.set_source_rgba(0.5, 0.5, 0.5, 0.9)
    cr.set_line_width(1)
    cr.rectangle(0.5, 0.5, 33, 17)
    cr.stroke()
    return Gtk.Image.new_from_pixbuf(_pixbuf(surf))


def _label(text="", markup=None, **kw):
    lab = Gtk.Label(xalign=0, **kw)
    if markup:
        lab.set_markup(markup)
    else:
        lab.set_text(text)
    return lab


def _title(text):
    return _label(markup=f"<span size='large' weight='bold'>{GLib.markup_escape_text(text)}</span>")


class ToggleGroup:
    """A row of toggle buttons where exactly one is on."""
    def __init__(self, values, make, on_change):
        self.box = Gtk.Box(spacing=6)
        self.buttons, self.value, self._busy = {}, None, False
        self.on_change = on_change
        for v in values:
            b = make(v)
            b.connect("toggled", self._toggled, v)
            self.box.pack_start(b, False, False, 0)
            self.buttons[v] = b

    def set(self, value):
        self._busy = True
        for v, b in self.buttons.items():
            b.set_active(v == value)
        self.value = value
        self._busy = False

    def _toggled(self, b, v):
        if self._busy:
            return
        if not b.get_active():
            if v == self.value:
                self._busy = True
                b.set_active(True)            # one must stay on
                self._busy = False
            return
        self.set(v)
        self.on_change(v)


class App:
    def __init__(self, apply_fn, current_fn):
        self.apply_fn, self.current_fn = apply_fn, current_fn
        self.themes, self.selected = {}, None
        self.loop = GLib.MainLoop()
        prov = Gtk.CssProvider()
        prov.load_from_data(CSS)
        Gtk.StyleContext.add_provider_for_screen(Gdk.Screen.get_default(), prov,
                                                 Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        self.css = Gtk.CssProvider()                  # swatch colours
        Gtk.StyleContext.add_provider_for_screen(Gdk.Screen.get_default(), self.css,
                                                 Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        self.win = Gtk.Window(title="Theme")
        self.win.set_default_size(640, 440)
        self.win.connect("destroy", lambda *a: self.loop.quit())
        self.win.connect("key-press-event", self._key)
        self.stack = Gtk.Stack()
        self.win.add(self.stack)
        self.stack.add_named(self._main_page(), "main")
        self.stack.add_named(self._dup_page(), "duplicate")
        self.stack.add_named(self._import_page(), "import")
        self.stack.add_named(self._export_page(), "export")
        self._swatch_css()
        self.reload(self.current_fn())

    # ---- helpers -------------------------------------------------------------------------------
    def run(self):
        self.win.show_all()
        self._marks(self.current_fn())
        self.logout.hide()
        self.import_error.hide()
        self.stack.set_visible_child_name("main")
        self.loop.run()

    def _key(self, _w, ev):
        if ev.keyval == Gdk.KEY_Escape and self.stack.get_visible_child_name() != "main":
            self.show_main()
            return True
        return False

    def show_main(self, status=None):
        self.stack.set_visible_child_name("main")
        if status is not None:
            self.status.set_text(status)
        self.apply_btn.grab_focus()

    def confirm(self, text, secondary, ok):
        d = Gtk.MessageDialog(transient_for=self.win, modal=True, message_type=Gtk.MessageType.QUESTION,
                              buttons=Gtk.ButtonsType.NONE, text=text)
        d.format_secondary_text(secondary)
        d.add_buttons("Cancel", Gtk.ResponseType.CANCEL, ok, Gtk.ResponseType.OK)
        d.set_default_response(Gtk.ResponseType.OK)
        r = d.run()
        d.destroy()
        return r == Gtk.ResponseType.OK

    def _icon_button(self, name, tip):
        b = Gtk.Button()
        b.set_tooltip_text(tip)
        b.get_style_context().add_class("flat")
        img = Gtk.Image()
        b.add(img)

        def paint(*_a):
            c = b.get_style_context().get_color(Gtk.StateFlags.NORMAL)
            try:
                mask = cairo.ImageSurface.create_from_png(f"{ICONS}/{name}.png")
            except (OSError, cairo.Error):
                img.clear()
                b.set_label(tip)
                return
            s = cairo.ImageSurface(cairo.FORMAT_ARGB32, mask.get_width(), mask.get_height())
            cr = cairo.Context(s)
            cr.set_source_rgba(c.red, c.green, c.blue, c.alpha)
            cr.mask_surface(mask, 0, 0)
            img.set_from_pixbuf(_pixbuf(s))
        b.connect("style-updated", paint)
        paint()
        return b

    # ---- the theme list ------------------------------------------------------------------------
    def reload(self, select=None):
        self.themes = {}
        for tid, path, builtin in package.list_themes():
            t = T.load(path)
            if not t.errors:
                self.themes[tid] = t
        ids = [i for i in ORDER if i in self.themes]
        ids += sorted((i for i in self.themes if i not in ORDER and self.themes[i].is_builtin()),
                      key=lambda i: self.themes[i].name.lower())
        self.first_user = None
        users = sorted((i for i in self.themes if not self.themes[i].is_builtin()),
                       key=lambda i: self.themes[i].name.lower())
        if users:
            self.first_user = users[0]
        for row in self.listbox.get_children():
            self.listbox.remove(row)
        self.rows = {}
        cur = self.current_fn()
        for tid in ids + users:
            t = self.themes[tid]
            row = Gtk.ListBoxRow()
            row.theme_id = tid
            h = Gtk.Box(spacing=10, margin=6)
            h.pack_start(_swatch_image(t), False, False, 0)
            name = _label(t.name, ellipsize=3)                   # Pango.EllipsizeMode.END
            h.pack_start(name, True, True, 0)
            check = _label(markup="<span foreground='#8bd99e' weight='bold'>✓</span>")
            h.pack_end(check, False, False, 0)
            row.add(h)
            row.check = check
            self.listbox.add(row)
            self.rows[tid] = row
        self.listbox.show_all()
        self._marks(cur)
        target = select if select in self.rows else (cur if cur in self.rows else (ids + users)[0])
        self.listbox.select_row(self.rows[target])

    def _marks(self, cur):
        """The ✓ on the current theme only."""
        for tid, row in self.rows.items():
            row.check.set_visible(tid == cur)

    def _header(self, row, before):
        if getattr(row, "theme_id", None) == self.first_user:
            lab = _label("YOURS", margin_top=8, margin_start=6)
            lab.get_style_context().add_class("rg-section")
            row.set_header(lab)
        else:
            row.set_header(None)

    def _selected(self, _lb, row):
        if row is None:
            return
        self.selected = row.theme_id
        t = self.themes[self.selected]
        self.preview.set_from_pixbuf(_pixbuf(preview.draw(t, PW, PH)))
        self.name.set_markup(f"<b>{GLib.markup_escape_text(t.name)}</b>")
        desc = t.description or ("Built in." if t.is_builtin() else "")
        if t.author and not t.is_builtin():
            desc = f"{desc}  By {t.author}." if desc else f"By {t.author}."
        self.desc.set_text(desc)
        self.delete_btn.set_sensitive(not t.is_builtin())
        self.apply_btn.set_sensitive(True)

    def _main_page(self):
        box = Gtk.Box(spacing=12, margin=10)
        left = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        left.set_size_request(216, -1)
        head = Gtk.Box(spacing=2)
        head.pack_start(_title("Themes"), False, False, 0)
        exp = self._icon_button("ui-export", "Export")
        exp.connect("clicked", lambda *_a: self.open_export())
        imp = self._icon_button("ui-import", "Import")
        imp.connect("clicked", lambda *_a: self.open_import())
        head.pack_end(exp, False, False, 0)
        head.pack_end(imp, False, False, 0)
        left.pack_start(head, False, False, 0)
        self.listbox = Gtk.ListBox()
        self.listbox.set_header_func(self._header)
        self.listbox.connect("row-selected", self._selected)
        self.listbox.connect("row-activated", lambda *_a: self.apply_btn.grab_focus())
        sc = Gtk.ScrolledWindow()
        sc.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        sc.add(self.listbox)
        left.pack_start(sc, True, True, 0)
        box.pack_start(left, False, False, 0)

        right = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.preview = Gtk.Image()
        self.preview.set_size_request(PW, PH)
        right.pack_start(self.preview, False, False, 0)
        self.name = _label(margin_top=4)
        right.pack_start(self.name, False, False, 0)
        self.desc = _label(wrap=True, lines=2, max_width_chars=48)
        self.desc.set_ellipsize(3)
        right.pack_start(self.desc, False, False, 0)
        buttons = Gtk.Box(spacing=8, margin_top=4)
        self.apply_btn = Gtk.Button(label="Apply")
        self.apply_btn.get_style_context().add_class("suggested-action")
        self.apply_btn.connect("clicked", self.on_apply)
        dup = Gtk.Button(label="Duplicate")
        dup.connect("clicked", lambda *_a: self.open_duplicate())
        self.delete_btn = Gtk.Button(label="Delete")
        self.delete_btn.get_style_context().add_class("destructive-action")
        self.delete_btn.connect("clicked", self.on_delete)
        for b in (self.apply_btn, dup, self.delete_btn):
            buttons.pack_start(b, False, False, 0)
        right.pack_start(buttons, False, False, 0)
        st = Gtk.Box(spacing=8)
        self.status = _label(wrap=True, max_width_chars=40)
        st.pack_start(self.status, True, True, 0)
        self.logout = Gtk.Button(label="Log out now")
        self.logout.connect("clicked", self.on_logout)
        st.pack_end(self.logout, False, False, 0)
        right.pack_start(st, False, False, 0)
        box.pack_start(right, True, True, 0)
        return box

    # ---- apply / delete / log out --------------------------------------------------------------
    def on_apply(self, _b):
        tid = self.selected
        self.status.set_text(f"Applying {self.themes[tid].name}…")
        self.apply_btn.set_sensitive(False)
        GLib.timeout_add(60, self._do_apply, tid)

    def _do_apply(self, tid):
        try:
            t = self.apply_fn(tid)
        except Exception as e:                       # never leave the app half-way
            self.status.set_text(f"Could not apply: {e}")
            self.apply_btn.set_sensitive(True)
            return False
        self._marks(t.id)
        msg = f"{t.name} applied."
        session = (os.environ.get("XCURSOR_THEME", "Handtop"), os.environ.get("XCURSOR_SIZE", "24"))
        if (t.cursor["theme"], str(t.cursor["size"])) != session:
            msg += " The pointer changes at the next log-in."
            self.logout.show()
        else:
            self.logout.hide()
        self.status.set_text(msg)
        self.apply_btn.set_sensitive(True)
        return False

    def on_logout(self, _b):
        if self.confirm("Log out now?", "Open apps close; the desktop starts again with the new pointer.",
                        "Log out"):
            subprocess.Popen(["labwc", "--exit"])

    def on_delete(self, _b):
        t = self.themes[self.selected]
        if t.is_builtin() or not self.confirm(f"Delete “{t.name}”?", "It is removed from this handheld. "
                                              "Export it first to keep a copy.", "Delete"):
            return
        if self.current_fn() == t.id:
            self.apply_fn("handtop-dark")
        package.delete(t.id)
        self.reload("handtop-dark")
        self.status.set_text(f"Deleted {t.name}.")

    # ---- Duplicate -----------------------------------------------------------------------------
    def _swatch_css(self, colours=()):
        css = "".join(f".rg-c{c[1:]} {{ background-color: {c}; }}\n" for c in
                      set(colours) | set(Z.ACCENTS) | set(Z.BACKGROUNDS))
        self.css.load_from_data(css.encode())

    def _swatch(self, c):
        b = Gtk.ToggleButton()
        b.get_style_context().add_class("rg-swatch")
        b.get_style_context().add_class(f"rg-c{c[1:]}")
        b.set_tooltip_text(c)
        return b

    def _choice(self, label):
        return lambda v: Gtk.ToggleButton(label=label(v))

    def _dup_page(self):
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8, margin=10)
        self.dup_title = _title("Duplicate")
        outer.pack_start(self.dup_title, False, False, 0)
        body = Gtk.Box(spacing=12)
        grid = Gtk.Grid(column_spacing=10, row_spacing=8)
        self.dup_name = Gtk.Entry(max_length=32)
        self.dup_rows = {}
        grid.attach(_label("Name"), 0, 0, 1, 1)
        grid.attach(self.dup_name, 1, 0, 1, 1)
        self.dup_grid, self.dup_row = grid, 1
        body.pack_start(grid, False, False, 0)
        side = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.dup_preview = Gtk.Image()
        self.dup_preview.set_size_request(SW, SH)
        side.pack_start(self.dup_preview, False, False, 0)
        side.pack_start(_label("Everything else is copied. Export the theme to edit it further "
                               "(GUIDE.md inside explains every part).", wrap=True, max_width_chars=28),
                        False, False, 0)
        body.pack_end(side, False, False, 0)
        outer.pack_start(body, True, True, 0)
        buttons = Gtk.Box(spacing=8)
        cancel = Gtk.Button(label="Cancel")
        cancel.connect("clicked", lambda *_a: self.show_main())
        self.create_btn = Gtk.Button(label="Create")
        self.create_btn.get_style_context().add_class("suggested-action")
        self.create_btn.connect("clicked", self.on_create)
        buttons.pack_end(self.create_btn, False, False, 0)
        buttons.pack_end(cancel, False, False, 0)
        outer.pack_start(buttons, False, False, 0)
        return outer

    def _dup_group(self, key, label, values, make):
        old = self.dup_rows.get(key)
        if old:
            self.dup_grid.remove(old[1])
        else:
            self.dup_grid.attach(_label(label), 0, self.dup_row, 1, 1)
            row = self.dup_row
            self.dup_row += 1
            self.dup_rows[key] = (row, None)
        row = self.dup_rows[key][0]
        g = ToggleGroup(values, make, lambda v: self._dup_changed(key, v))
        self.dup_grid.attach(g.box, 1, row, 1, 1)
        self.dup_rows[key] = (row, g.box)
        return g

    def open_duplicate(self):
        src = self.themes[self.selected]
        self.dup_src = src
        self.dup_title.set_markup(f"<span size='large' weight='bold'>Duplicate “{GLib.markup_escape_text(src.name)}”</span>")
        self.dup_name.set_text(f"{src.name} copy"[:32])
        accents = [src.palette["accent"]] + [a for a in Z.ACCENTS if a != src.palette["accent"]][:7]
        bgs = [src.palette["bg"]] + [b for b in Z.BACKGROUNDS if b != src.palette["bg"]][:7]
        self._swatch_css(accents + bgs)
        self.g_accent = self._dup_group("accent", "Accent", accents, self._swatch)
        self.g_bg = self._dup_group("bg", "Background", bgs, self._swatch)
        self.g_icons = self._dup_group("icons", "Icons", ("dark", "light"), self._choice(str.capitalize))
        self.g_pointer = self._dup_group("pointer", "Pointer", Z.POINTERS, self._choice(str))
        self.g_text = self._dup_group("text", "Text size", Z.TEXT_SCALES,
                                      self._choice(lambda v: f"{round(v * 100)}%"))
        self.g_accent.set(accents[0])
        self.g_bg.set(bgs[0])
        self.g_icons.set(src.base)
        self.g_pointer.set(src.cursor["size"] if src.cursor["size"] in Z.POINTERS else 24)
        self.g_text.set(src.fonts["scale"] if src.fonts["scale"] in Z.TEXT_SCALES else 1.0)
        self.bases = {b: self.themes.get(f"handtop-{b}") for b in ("dark", "light")}
        self.dup_grid.show_all()
        self._dup_preview()
        self.stack.set_visible_child_name("duplicate")
        self.dup_name.grab_focus()

    def _dup_choices(self):
        src = self.dup_src
        return dict(accent=None if self.g_accent.value == src.palette["accent"] else self.g_accent.value,
                    background=None if self.g_bg.value == src.palette["bg"] else self.g_bg.value,
                    icons=self.g_icons.value, pointer=self.g_pointer.value, text=self.g_text.value)

    def _dup_changed(self, key, v):
        if key == "bg":                               # the icon set follows the background
            self.g_icons.set("dark" if Z.is_dark(v) else "light")
        self._dup_preview()

    def _dup_preview(self):
        t = Z.preview_theme(self.dup_src, {k: v for k, v in self.bases.items() if v}, **self._dup_choices())
        self.dup_preview.set_from_pixbuf(_pixbuf(preview.draw(t, SW, SH, own_picture=False)))

    def on_create(self, _b):
        name = " ".join(self.dup_name.get_text().split())[:32] or "My theme"
        tid = Z.id_from_name(name, set(self.themes) | {i for i, _p, _b in package.list_themes()})
        try:
            t = package.duplicate(self.dup_src.path, tid, name)
            Z.customize(t.path, **self._dup_choices())
        except Exception as e:
            self.show_main(f"Could not create the theme: {e}")
            return
        self.reload(tid)
        self.show_main(f"Created {name}. Apply it to use it.")

    # ---- Import --------------------------------------------------------------------------------
    def _import_page(self):
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8, margin=10)
        outer.pack_start(_title("Import a theme"), False, False, 0)
        self.import_hint = _label(wrap=True, max_width_chars=70)
        outer.pack_start(self.import_hint, False, False, 0)
        self.import_list = Gtk.ListBox()
        self.import_list.connect("row-activated", lambda *_a: self.on_import())
        sc = Gtk.ScrolledWindow()
        sc.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        sc.add(self.import_list)
        outer.pack_start(sc, True, True, 0)
        self.import_error = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.import_error.get_style_context().add_class("rg-error")
        self.import_error_label = _label(wrap=True, max_width_chars=70)
        self.import_error.pack_start(self.import_error_label, False, False, 0)
        outer.pack_start(self.import_error, False, False, 0)
        buttons = Gtk.Box(spacing=8)
        back = Gtk.Button(label="Back")
        back.connect("clicked", lambda *_a: self.show_main())
        self.import_btn = Gtk.Button(label="Import")
        self.import_btn.get_style_context().add_class("suggested-action")
        self.import_btn.connect("clicked", lambda *_a: self.on_import())
        buttons.pack_end(self.import_btn, False, False, 0)
        buttons.pack_end(back, False, False, 0)
        outer.pack_start(buttons, False, False, 0)
        return outer

    def open_import(self):
        for row in self.import_list.get_children():
            self.import_list.remove(row)
        files = Z.find_theme_files(Z.import_places())
        for path, place, size in files:
            row = Gtk.ListBoxRow()
            row.path = path
            v = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, margin=6)
            v.pack_start(_label(markup=f"<b>{GLib.markup_escape_text(os.path.basename(path))}</b>"), False, False, 0)
            kb = max(1, round(size / 1024))
            v.pack_start(_label(markup=f"<small>{GLib.markup_escape_text(place)} · "
                                       f"{kb} KB</small>" if kb < 1024 else
                                       f"<small>{GLib.markup_escape_text(place)} · {kb / 1024:.1f} MB</small>"),
                         False, False, 0)
            row.add(v)
            self.import_list.add(row)
        self.import_list.show_all()
        if files:
            self.import_hint.set_text("Theme files (.handtop-theme) in your home folder, ~/Themes, ~/Downloads "
                                      "and drives opened in Files:")
            self.import_list.select_row(self.import_list.get_row_at_index(0))
        else:
            self.import_hint.set_text("No theme files found. Copy a .handtop-theme file to ~/Themes, or plug in "
                                      "a USB drive or SD card with one and open it in Files first.")
        self.import_btn.set_sensitive(bool(files))
        self.import_error.hide()
        self.stack.set_visible_child_name("import")
        (self.import_list if files else self.import_btn).grab_focus()

    def on_import(self, replace=False):
        row = self.import_list.get_selected_row()
        if row is None:
            return
        name = os.path.basename(row.path)
        try:
            t = package.import_theme(row.path, replace=replace)
        except package.ThemeExists as e:
            if self.confirm(f"Replace “{e.id}”?", "A theme with this id is already installed.", "Replace"):
                self.on_import(replace=True)
            return
        except T.ThemeError as e:
            lines = [f"• {p.where}: {p.message}" for p in e.problems[:8]]
            if len(e.problems) > 8:
                lines.append(f"• … and {len(e.problems) - 8} more")
            self.import_error_label.set_markup(
                f"<b>{GLib.markup_escape_text(name)}: not imported</b>\n"
                + GLib.markup_escape_text("\n".join(lines + ["Nothing was changed. Fix these in the file "
                                                             "and import again."])))
            self.import_error.show()
            return
        warn = [p for p in t.problems if p.level == "warning"]
        self.reload(t.id)
        self.show_main(f"Imported {t.name}." + (f" {len(warn)} warning(s): parts were ignored." if warn else ""))

    # ---- Export --------------------------------------------------------------------------------
    def _export_page(self):
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8, margin=10)
        self.export_title = _title("Export")
        outer.pack_start(self.export_title, False, False, 0)
        self.export_hint = _label(wrap=True, max_width_chars=70)
        outer.pack_start(self.export_hint, False, False, 0)
        self.export_list = Gtk.ListBox()
        self.export_list.connect("row-activated", lambda *_a: self.on_export())
        outer.pack_start(self.export_list, True, True, 0)
        buttons = Gtk.Box(spacing=8)
        back = Gtk.Button(label="Back")
        back.connect("clicked", lambda *_a: self.show_main())
        ok = Gtk.Button(label="Export")
        ok.get_style_context().add_class("suggested-action")
        ok.connect("clicked", lambda *_a: self.on_export())
        buttons.pack_end(ok, False, False, 0)
        buttons.pack_end(back, False, False, 0)
        outer.pack_start(buttons, False, False, 0)
        return outer

    def open_export(self):
        t = self.themes[self.selected]
        self.export_title.set_markup(f"<span size='large' weight='bold'>Export “{GLib.markup_escape_text(t.name)}”</span>")
        self.export_hint.set_text(f"Saved as {t.id}.handtop-theme, with GUIDE.md inside (how to edit it). "
                                  "To use a drive, open it in Files first.")
        for row in self.export_list.get_children():
            self.export_list.remove(row)
        for label, folder in Z.export_places():
            row = Gtk.ListBoxRow()
            row.folder = folder
            row.add(_label(label, margin=8))
            self.export_list.add(row)
        self.export_list.show_all()
        self.export_list.select_row(self.export_list.get_row_at_index(0))
        self.stack.set_visible_child_name("export")
        self.export_list.grab_focus()

    def on_export(self):
        row = self.export_list.get_selected_row()
        if row is None:
            return
        t = self.themes[self.selected]
        dest = os.path.join(row.folder, f"{t.id}.handtop-theme")
        if os.path.exists(dest) and not self.confirm(f"Replace {os.path.basename(dest)}?",
                                                     f"It is already in {row.folder}.", "Replace"):
            return
        try:
            package.export_theme(t.path, dest)
        except Exception as e:
            self.show_main(f"Could not export: {e}")
            return
        self.show_main(f"Saved to {dest.replace(os.path.expanduser('~'), '~', 1)}.")


def run(apply_fn, current_fn):
    App(apply_fn, current_fn).run()
