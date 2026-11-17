"""Advanced > Profiles > Apps…: link apps to a profile (auto-switch per app). While a linked app is
in front, the input daemon uses that profile instead of the one picked by hand; anything else in
front (an app without a link, the bare desktop, Controls itself) uses the picked one.

Two pages: the profile's apps (with Remove), and a picker with the windows open now first (their
exact app id, from the daemon) and then the installed apps.

Mixed into app.App through AdvancedMixin (uses App's _page(), stack, back() ...)."""
import gi
gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk  # noqa: E402

from . import actions as A  # noqa: E402
from . import store  # noqa: E402


def _lab(text, dim=False, markup=False, **kw):
    lab = Gtk.Label(xalign=0, **kw)
    lab.set_line_wrap(True)
    if markup:
        lab.set_markup(text)
    else:
        lab.set_text(text)
    if dim:
        lab.get_style_context().add_class("rg-dim")
    return lab


def _shown(name):
    return "Default" if name == "default" else name


class LinksMixin:
    # ---- the profile's apps ------------------------------------------------------------------
    def _links_page(self):
        box, sw = self._page("links_title")
        inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        add = Gtk.Button(label="Add an app…", halign=Gtk.Align.START)
        add.connect("clicked", lambda *_: self._open_link_pick())
        inner.pack_start(add, False, False, 0)
        self.links_list = Gtk.ListBox()
        self.links_list.set_selection_mode(Gtk.SelectionMode.NONE)
        frame = Gtk.Frame()
        frame.add(self.links_list)
        inner.pack_start(frame, False, False, 0)
        inner.pack_start(_lab("While one of these apps is in front, this profile is used instead of the one "
                              "you picked; anything else in front uses the picked one. The switch waits "
                              "until no button is held, and External Controller mode keeps the profile it "
                              "started with.", dim=True), False, False, 0)
        sw.add(inner)
        return box

    def open_links(self, profile):
        self.links_profile = profile
        self.links_title.set_markup(f"<b>Apps for {GLib.markup_escape_text(_shown(profile))}</b>")
        self._fill_links()
        self.stack.set_visible_child_name("links")

    def _app_name(self, app_id):
        low = app_id.lower()
        names = getattr(self, "window_names", None)
        if names is None:
            names = self.window_names = {i.lower(): n for i, n in A.window_ids()}
        return names.get(low) or self.app_names.get(app_id) or app_id

    def _fill_links(self):
        for r in self.links_list.get_children():
            self.links_list.remove(r)
        apps = store.apps_of(self.links_profile)
        for app_id in apps:
            row = Gtk.ListBoxRow(activatable=False)
            line = Gtk.Box(spacing=8, margin=4)
            name = self._app_name(app_id)
            line.pack_start(_lab(name, hexpand=True), True, True, 0)
            if name != app_id:                    # the id it matches, e.g. "Thunar" for File Manager
                line.pack_start(_lab(app_id, dim=True), False, False, 0)
            rm = Gtk.Button(label="Remove")
            rm.connect("clicked", lambda _b, a=app_id: self._unlink(a))
            line.pack_start(rm, False, False, 0)
            row.add(line)
            self.links_list.add(row)
        if not apps:
            self.links_list.add(_lab("No apps yet.", dim=True, margin=6))
        self.links_list.show_all()

    def _unlink(self, app_id):
        store.unlink_app(app_id)
        self._fill_links()
        self._fill_profile_list()

    # ---- picker ------------------------------------------------------------------------------
    def _link_pick_page(self):
        box, sw = self._page("linkpick_title")
        self.linkpick_list = Gtk.ListBox()
        self.linkpick_list.set_activate_on_single_click(True)
        self.linkpick_list.connect("row-activated", lambda _l, r: self._link_chosen(r))
        sw.add(self.linkpick_list)
        return box

    def _pick_row(self, app_id, text):
        other = store.linked_to(app_id)
        if other == self.links_profile:
            return None
        row = Gtk.ListBoxRow()
        row.app_id = app_id
        line = Gtk.Box(spacing=8, margin=6)
        line.pack_start(_lab(text, hexpand=True), True, True, 0)
        if other:
            line.pack_start(_lab(f"now: {_shown(other)}", dim=True), False, False, 0)
        row.add(line)
        return row

    def _pick_header(self, text):
        row = Gtk.ListBoxRow(activatable=False, selectable=False)
        row.add(_lab(f"<b>{GLib.markup_escape_text(text)}</b>", markup=True, margin=6))
        return row

    def _open_link_pick(self):
        for r in self.linkpick_list.get_children():
            self.linkpick_list.remove(r)
        self.linkpick_title.set_markup(
            f"<b>Link an app to {GLib.markup_escape_text(_shown(self.links_profile))}</b>")
        watching, windows = store.open_windows()
        self.linkpick_list.add(self._pick_header("Open now"))
        rows = [self._pick_row(a, f"{self._app_name(a)} — {t}" if t and t != self._app_name(a) else self._app_name(a))
                for a, t in windows]
        rows = [r for r in rows if r]
        for r in rows:
            self.linkpick_list.add(r)
        if not rows:
            self.linkpick_list.add(_lab("Nothing else is open." if watching else
                                        "Open windows aren't available (the input daemon isn't watching them).",
                                        dim=True, margin=6))
        self.linkpick_list.add(self._pick_header("Installed apps"))
        open_ids = {a.lower() for a, _ in windows}
        for app_id, name in A.window_ids():
            if app_id.lower() in open_ids or app_id.lower() == store.APP_SELF:
                continue
            r = self._pick_row(app_id, name)
            if r:
                self.linkpick_list.add(r)
        self.linkpick_list.show_all()
        self.stack.set_visible_child_name("linkpick")

    def _link_chosen(self, row):
        if not hasattr(row, "app_id"):
            return
        try:
            store.link_app(row.app_id, self.links_profile)
        except (OSError, ValueError) as e:
            self.linkpick_title.set_text(f"Not linked: {e}")
            return
        self.open_links(self.links_profile)
        self._fill_profile_list()
