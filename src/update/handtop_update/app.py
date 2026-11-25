"""The Update app's window (rg35xxh-update). 640x480, everything reachable with the D-pad / pointer
and A; Escape (B) goes back to the main page.

  Main       the installed release and channel, the last result (failed / stopped / kept settings
             files), Check for updates, Advanced
  Results    Handtop's release and its notes, a "needs a new image" notice, Debian's updates (count,
             Show lists them), Download (size)
  Download   progress (finished files in the cache), then "Preparing"
  Ready      what will be installed, whether going back is possible; Restart and install, Install and
             power off, Cancel update
  Scheduled  installs at the next restart: Restart now, Cancel update
  Advanced   stable / testing channel, the release kept for going back, what recovery.txt can do

Every privileged step is the update worker's (worker.py); this app only shows and asks."""
import os
import sys
import threading
import time

import gi
gi.require_version("Gdk", "3.0")
gi.require_version("Gtk", "3.0")
from gi.repository import Gdk, GLib, Gtk, Pango  # noqa: E402

from . import model as M  # noqa: E402
from . import worker as W  # noqa: E402

SEEN = os.path.join(os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config")), "rg35xxh",
                    "update-seen")
CSS = b"""
.rg-card { border: 1px solid alpha(@theme_fg_color, 0.35); border-radius: 6px; padding: 10px; }
.rg-error { background-color: alpha(@theme_fg_color, 0.07); border: 2px solid @theme_fg_color;
            border-radius: 6px; padding: 8px; }
.rg-section { font-size: 0.8em; font-weight: bold; opacity: 0.7; }
.rg-dim { opacity: 0.75; }
.rg-big { min-height: 36px; }
"""


def _label(text="", markup=None, dim=False, wrap=True, cls=None):
    lab = Gtk.Label(xalign=0)
    if markup:
        lab.set_markup(markup)
    else:
        lab.set_text(text)
    if wrap:
        lab.set_line_wrap(True)
        lab.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
    if dim:
        lab.get_style_context().add_class("rg-dim")
    if cls:
        lab.get_style_context().add_class(cls)
    return lab


def _title(text):
    return _label(markup="<span size='large' weight='bold'>%s</span>" % GLib.markup_escape_text(text))


def _button(text, cb, suggested=False, destructive=False):
    b = Gtk.Button(label=text)
    b.get_style_context().add_class("rg-big")
    if suggested:
        b.get_style_context().add_class("suggested-action")
    if destructive:
        b.get_style_context().add_class("destructive-action")
    b.connect("clicked", lambda *_: cb())
    return b


def _page():
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
    for m in ("top", "bottom", "start", "end"):
        getattr(box, "set_margin_" + m)(12)
    return box


def _framed():
    """A page whose content scrolls (big text sizes, e.g. High contrast) above a button row that
    always stays in view: (page, body); pack the content into body, the row with page.pack_end."""
    p = _page()
    body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
    p.pack_start(_scrolled(body), True, True, 0)
    return p, body


def _theme_icon(name):
    """One of the current theme's rendered taskbar images (Handtop dark's until a theme is applied)."""
    for d in (os.path.join(os.environ.get("XDG_STATE_HOME", os.path.expanduser("~/.local/state")),
                           "rg35xxh", "theme", "icons"), "/usr/local/share/rg35xxh/icons"):
        f = os.path.join(d, name + ".png")
        if os.path.isfile(f):
            return Gtk.Image.new_from_file(f)
    return None


def _scrolled(child):
    sw = Gtk.ScrolledWindow()
    sw.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
    sw.add(child)
    return sw


class App:
    def __init__(self, start_page=None):
        self.loop = GLib.MainLoop()
        prov = Gtk.CssProvider()
        prov.load_from_data(CSS)
        Gtk.StyleContext.add_provider_for_screen(Gdk.Screen.get_default(), prov,
                                                 Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        self.win = Gtk.Window(title="Update")
        self.win.set_icon_name("rg35xxh-update")
        self.win.set_default_size(640, 440)
        self.win.connect("destroy", lambda *a: self.loop.quit())
        # While the worker is busy (scheduling, then the restart request) the window stays: closing it
        # would end the thread that asks for the restart (review 2026-11-26 #53).
        self.win.connect("delete-event", lambda *a: self.busy)
        self.win.connect("key-press-event", self._key)
        self.stack = Gtk.Stack()
        self.stack.set_transition_type(Gtk.StackTransitionType.NONE)
        self.win.add(self.stack)
        self.status, self.check, self.busy = {}, None, False
        self.start_page = start_page
        self._show_busy("Reading the update state…")
        self.win.show_all()
        self._run(lambda: W.call("status"), self._status_done)

    # ---- plumbing ----------------------------------------------------------------------------------

    def _run(self, work, done):
        """work() in a thread, done(result) back on the GTK thread."""
        self.busy = True

        def go():
            try:
                res = work()
            except Exception as e:          # noqa: BLE001 - shown, never a crash
                res = {"ok": False, "error": str(e)}
            GLib.idle_add(self._done, done, res)
        threading.Thread(target=go, daemon=True).start()

    def _done(self, done, res):
        self.busy = False
        done(res)
        return False

    def _set(self, name, widget):
        old = self.stack.get_child_by_name(name)
        if old:
            self.stack.remove(old)
        self.stack.add_named(widget, name)
        widget.show_all()
        self.stack.set_visible_child_name(name)

    def _key(self, _w, ev):
        if ev.keyval == Gdk.KEY_Escape and not self.busy and self.stack.get_visible_child_name() not in (
                "main", "ready", "scheduled", "foreign"):
            self.refresh()
            return True
        return False

    def _error_box(self, text, title=None):
        """A problem, in the theme's own colours with its "update failed" picture (no fixed red: Pocket,
        Grayscale and High contrast have no such colour)."""
        box = Gtk.Box(spacing=10)
        box.get_style_context().add_class("rg-error")
        img = _theme_icon("update-failed")
        if img:
            img.set_valign(Gtk.Align.START)
            box.pack_start(img, False, False, 0)
        col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        if title:
            col.pack_start(_label(markup="<b>%s</b>" % GLib.markup_escape_text(title)), False, False, 0)
        if text:
            col.pack_start(_label(text), False, False, 0)
        box.pack_start(col, True, True, 0)
        return box, col

    # ---- busy ---------------------------------------------------------------------------------------

    def _show_busy(self, text, progress=False):
        p = _page()
        p.set_valign(Gtk.Align.CENTER)
        sp = Gtk.Spinner()
        sp.start()
        p.pack_start(sp, False, False, 0)
        self.busy_label = _label(text)
        self.busy_label.set_xalign(0.5)
        self.busy_label.set_justify(Gtk.Justification.CENTER)
        p.pack_start(self.busy_label, False, False, 0)
        self.busy_bar = None
        if progress:
            self.busy_bar = Gtk.ProgressBar()
            p.pack_start(self.busy_bar, False, False, 0)
        self._set("busy", p)

    # ---- main ---------------------------------------------------------------------------------------

    def refresh(self):
        self._show_busy("Reading the update state…")
        self._run(lambda: W.call("status"), self._status_done)

    def _status_done(self, st):
        self.status = st if st.get("ok", True) else {}
        if not st.get("ok", True) and "error" in st:
            self._main(error=M.friendly_error(st.get("error")))
            return
        page = self.start_page or M.page_for(self.status)
        self.start_page = None
        {"ready": self._ready, "scheduled": self._scheduled, "foreign": self._foreign,
         "advanced": self._advanced, "results": lambda: self._do_check(),
         "list": lambda: self._do_check(show_list=True)}.get(page, self._main)()

    def _header(self, p):
        ver = W.installed_version()
        ch = self.status.get("channel") or "stable"
        p.pack_start(_title("Handtop %s" % M.short_version(ver, W.installed_release())), False, False, 0)
        p.pack_start(_label("Channel: %s" % ("testing (early builds)" if ch == "testing" else "stable"),
                            dim=True), False, False, 0)

    def _result_card(self, p):
        res = M.result_text(self.status.get("last_result"))
        if not res:
            return
        title, body, err = res
        if err:
            box, col = self._error_box(body, title)
            if self.status.get("previous_release"):
                col.pack_start(_label("If the handheld no longer works properly, recovery.txt on the SD card's "
                                      "boot partition can go back to the previous release (Advanced explains how).",
                                      dim=True), False, False, 0)
            else:
                col.pack_start(_label("Run the update again. If the handheld no longer works properly, flashing "
                                      "the current image is the way back (no earlier release is kept).",
                                      dim=True), False, False, 0)
        else:
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
            box.get_style_context().add_class("rg-card")
            box.pack_start(_label(markup="<b>%s</b>" % GLib.markup_escape_text(title)), False, False, 0)
            if body:
                box.pack_start(_label(body), False, False, 0)
        p.pack_start(box, False, False, 0)
        self._mark_seen()

    def _mark_seen(self):
        t = (self.status.get("last_result") or {}).get("time")
        if not t:
            return
        try:
            os.makedirs(os.path.dirname(SEEN), exist_ok=True)
            with open(SEEN, "w") as f:
                f.write("%s\n" % t)
            W.signal_badge()
        except OSError:
            pass

    def _main(self, error=None):
        p, body = _framed()
        self._header(body)
        self._result_card(body)
        if error:
            body.pack_start(self._error_box(error)[0], False, False, 0)
        body.pack_start(_label("Updates are installed when the handheld restarts, so nothing changes while "
                            "you use it. Checking needs Wi-Fi.", dim=True), False, False, 0)
        row = Gtk.Box(spacing=8)
        row.pack_start(_button("Advanced ›", self._advanced), False, False, 0)
        row.pack_end(_button("Check for updates", self._do_check, suggested=True), False, False, 0)
        p.pack_end(row, False, False, 0)
        self._set("main", p)

    # ---- check ----------------------------------------------------------------------------------------

    def _do_check(self, show_list=False):
        self._show_busy("Checking the clock…")

        def work():
            for i in range(30):                         # signatures need the right time
                sync, plausible = W.clock()
                if sync:
                    break
                GLib.idle_add(self.busy_label.set_text, "Waiting for the clock to be set over the network… %d s" % (30 - i))
                time.sleep(1)
            if not sync and not plausible:
                return {"ok": False, "clock": True}
            GLib.idle_add(self.busy_label.set_text, "Checking for updates…")
            return W.call("check")
        self._run(work, lambda res: self._check_done(res, show_list))

    def _check_done(self, res, show_list=False):
        if res.get("clock"):
            self._main(error="The handheld's clock is wrong (it shows %s), so updates can't be checked safely. "
                             "Connect to Wi-Fi, wait a minute for the clock to set itself, then check again."
                       % time.strftime("%d %b %Y"))
            return
        if not res.get("ok"):
            self._main(error=M.friendly_error(res.get("error"), res.get("details")))
            return
        self.check = res
        self._results(show_list)

    def _results(self, show_list=False):
        s = M.summarize(self.check)
        p = _page()
        if s["nothing"] and not s["new_image"]:
            p, body = _framed()
            body.pack_start(_title("Everything is up to date"), False, False, 0)
            body.pack_start(_label("Handtop %s and all of Debian's packages are the newest available on the %s "
                                "channel." % (M.short_version(W.installed_version(), W.installed_release()),
                                              self.status.get("channel") or "stable"), dim=True), False, False, 0)
            for w in s["warnings"]:
                body.pack_start(_label(w, dim=True), False, False, 0)
            p.pack_end(_button("Done", self.refresh), False, False, 0)
            self._set("results", p)
            return
        body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        if s["handtop_release"]:
            body.pack_start(_title("Handtop %s" % s["handtop_release"]), False, False, 0)
            for line in s["notes"]:
                body.pack_start(_label("•  " + line), False, False, 0)
        if s["new_image"]:
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            box.get_style_context().add_class("rg-card")
            box.pack_start(_label(markup="<b>A new Handtop release needs a new image</b>"), False, False, 0)
            box.pack_start(_label("It comes with a new kernel, which only flashing the new image can bring. "
                                  "Until then only Debian's updates are offered here.", dim=True), False, False, 0)
            body.pack_start(box, False, False, 0)
        if s["debian"]:
            body.pack_start(_label("DEBIAN", cls="rg-section"), False, False, 6)
            row = Gtk.Box(spacing=8)
            row.pack_start(_label("%d updates to Debian's packages (security fixes included when there are any)"
                                  % len(s["debian"])), True, True, 0)
            listbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            for n, old, new in s["debian"]:
                listbox.pack_start(_label("%s   %s → %s" % (n, old, new), dim=True, wrap=True), False, False, 0)
            tog = Gtk.Button(label="Hide" if show_list else "Show")

            def toggle(b):
                vis = not listbox.get_visible()
                listbox.set_visible(vis)
                b.set_label("Hide" if vis else "Show")
            tog.connect("clicked", toggle)
            row.pack_end(tog, False, False, 0)
            body.pack_start(row, False, False, 0)
            body.pack_start(listbox, False, False, 0)
        for w in s["warnings"]:
            body.pack_start(_label(w, dim=True), False, False, 0)
        p.pack_start(_scrolled(body), True, True, 0)
        row = Gtk.Box(spacing=8)
        row.pack_start(_button("Back", self.refresh), False, False, 0)
        if not s["nothing"]:            # e.g. a new image is needed and Debian has nothing new
            row.pack_end(_button("Download (%s)" % M.mb(s["download_mb"]), self._do_download, suggested=True),
                         False, False, 0)
        p.pack_end(row, False, False, 0)
        self._set("results", p)                       # shows everything ...
        if s["debian"] and not show_list:
            listbox.hide()                                # ... so the list is hidden afterwards

    # ---- download --------------------------------------------------------------------------------------

    def _do_download(self):
        total = (self.check or {}).get("download_mb") or 0
        self._show_busy("Downloading…", progress=True)

        def tick():
            if self.stack.get_visible_child_name() != "busy" or not self.busy_bar:
                return False
            got = W.downloaded_mb()
            if total and got < total:
                self.busy_bar.set_fraction(min(1.0, got / total))
                self.busy_label.set_text("Downloading… %s of %s" % (M.mb(got), M.mb(total)))
            else:
                self.busy_bar.pulse()
                self.busy_label.set_text("Checking the files and keeping the current release for going back…")
            return True
        GLib.timeout_add(500, tick)

        def done(res):
            if not res.get("ok"):
                self._main(error=M.friendly_error(res.get("error")))
                return
            W.signal_badge()
            self.refresh()
        self._run(lambda: W.call("download"), done)

    # ---- ready / scheduled -------------------------------------------------------------------------------

    def _ready(self, error=None):
        st = self.status
        p, body = _framed()
        body.pack_start(_title("Ready to install"), False, False, 0)
        body.pack_start(_label("%d packages are downloaded. They are installed while the handheld restarts: "
                            "a few minutes with text on the screen. Don't switch it off then." %
                            (st.get("packages") or 0)), False, False, 0)
        body.pack_start(_label(M.rollback_text(st, st.get("previous_release")), dim=True), False, False, 0)
        body.pack_start(_label("Needs 40 % battery or the charger, and no controller mode running.", dim=True),
                     False, False, 0)
        if error:
            body.pack_start(self._error_box(error)[0], False, False, 0)
        row = Gtk.Box(spacing=8)
        row.pack_start(_button("Cancel update", self._do_cancel), False, False, 0)
        row.pack_start(_button("Advanced ›", self._advanced), False, False, 0)
        if M.can_install(st):
            row.pack_end(_button("Restart and install", lambda: self._do_schedule("restart"), suggested=True),
                         False, False, 0)
            row.pack_end(_button("Install and power off", lambda: self._do_schedule("poweroff")), False, False, 0)
        p.pack_end(row, False, False, 0)
        self._set("ready", p)

    def _do_schedule(self, after):
        self._show_busy("Checking the battery and the downloaded files…")

        def done(res):
            if not res.get("ok"):
                self._ready(error=M.friendly_error(res.get("error")))
                return
            W.signal_badge()
            self._restart_now()
        plan = (self.status or {}).get("plan")
        self._run(lambda: W.call("schedule", after, *([plan] if plan else [])), done)

    def _restart_now(self):
        self._show_busy("Restarting to install the update…")

        def done(err):
            if err:                      # refused (e.g. by policy): say so, the update stays scheduled
                def back(st):
                    self.status = st if st.get("ok", True) else self.status
                    self._scheduled(error="The handheld couldn't restart (%s). The update stays scheduled: "
                                          "restart it from the power menu." % err)
                self._run(lambda: W.call("status"), back)
        self._run(W.reboot, done)

    def _scheduled(self, error=None):
        st = self.status
        p, body = _framed()
        body.pack_start(_title("The update installs at the next restart"), False, False, 0)
        if error:
            body.pack_start(self._error_box(error)[0], False, False, 0)
        after = "then the handheld switches off" if st.get("after") == "poweroff" else "then the desktop starts again"
        body.pack_start(_label("%d packages; %s." % (st.get("packages") or 0, after)), False, False, 0)
        body.pack_start(_label(M.rollback_text(st, st.get("previous_release")), dim=True), False, False, 0)
        row = Gtk.Box(spacing=8)
        row.pack_start(_button("Cancel update", self._do_cancel), False, False, 0)
        row.pack_end(_button("Restart now", self._restart_now, suggested=True), False, False, 0)
        p.pack_end(row, False, False, 0)
        self._set("scheduled", p)

    def _do_cancel(self):
        self._show_busy("Cancelling…")

        def done(res):
            W.signal_badge()
            self.start_page = None
            if not res.get("ok"):
                self._main(error=M.friendly_error(res.get("error")))
            else:
                self.refresh()
        self._run(lambda: W.call("cancel"), done)

    def _foreign(self):
        p, body = _framed()
        body.pack_start(_title("Another update is waiting"), False, False, 0)
        body.pack_start(_label("A different program has scheduled an update for the next restart "
                            "(/system-update). Restart to let it finish; this app won't touch it."),
                     False, False, 0)
        p.pack_end(_button("Close", self.win.destroy), False, False, 0)
        self._set("foreign", p)

    # ---- advanced -------------------------------------------------------------------------------------------

    def _advanced(self):
        st = self.status
        p = _page()
        body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        body.pack_start(_title("Advanced"), False, False, 0)
        body.pack_start(_label("CHANNEL", cls="rg-section"), False, False, 4)
        ch = st.get("channel") or "stable"
        row = Gtk.Box(spacing=8)
        stable = Gtk.RadioButton.new_with_label(None, "Stable")
        testing = Gtk.RadioButton.new_with_label_from_widget(stable, "Testing")
        (testing if ch == "testing" else stable).set_active(True)
        row.pack_start(stable, False, False, 0)
        row.pack_start(testing, False, False, 0)
        body.pack_start(row, False, False, 0)
        body.pack_start(_label("Testing gets new releases before everyone else, to try them out. They may "
                               "have bugs. Switching cancels a downloaded update; going back to Stable keeps "
                               "the newer packages until Stable catches up.", dim=True), False, False, 0)

        def switched(b, which):
            if not b.get_active() or which == (self.status.get("channel") or "stable"):
                return
            self.start_page = "advanced"                # come back here after the switch
            self._show_busy("Switching to %s…" % which)

            def done(res):
                W.signal_badge()
                if res.get("ok"):
                    self.refresh()
                else:
                    self.start_page = None
                    self._main(error=M.friendly_error(res.get("error")))
            self._run(lambda: W.call("channel", which), done)
        stable.connect("toggled", switched, "stable")
        testing.connect("toggled", switched, "testing")
        body.pack_start(_label("GOING BACK", cls="rg-section"), False, False, 8)
        prev = st.get("previous_release")
        body.pack_start(_label("Release kept for going back: %s" % (M.short_version(prev) if prev else
                               "none yet (kept when an update changes Handtop)")), False, False, 0)
        body.pack_start(_label(
            "If the handheld doesn't work properly after an update, put the SD card in a PC, open recovery.txt "
            "on its boot partition and change a line, save, and start the handheld again:\n"
            "  handtop=previous   goes back to the kept release\n"
            "  joypad=previous    uses the controls driver from before the last update\n"
            "  joypad=current     goes back to the current controls driver\n"
            "Each line is acted on once; what happened is written to logs\\recovery-NNNNNN.txt.", dim=True),
            False, False, 0)
        if st.get("joypad_override"):
            body.pack_start(_label("The previous controls driver is in use (joypad=previous).", dim=True),
                            False, False, 0)
        p.pack_start(_scrolled(body), True, True, 0)
        row = Gtk.Box(spacing=8)
        row.pack_start(_button("‹ Back", self.refresh), False, False, 0)
        p.pack_end(row, False, False, 0)
        self._set("advanced", p)


def run(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    page = argv[argv.index("--page") + 1] if "--page" in argv else None
    app = App(page)
    try:
        app.loop.run()
    except KeyboardInterrupt:
        pass
