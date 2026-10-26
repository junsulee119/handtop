"""rg35xxh-inputd's display side, in its own process: the on-screen keyboard and the pointer-hiding
touch target (both GTK 3 layer-shell windows).

Why a separate process: GDK ends a process with _exit() the moment its Wayland display goes away
(labwc exits at every log-out). Inside the input daemon that skipped the daemon's clean exit (motor
stopped, vibration effects erased, gamepad released) and left everything to the kernel; the
vibration driver has locked the whole handheld up before. Here only this process ends; the daemon
keeps no display connection and stops cleanly when the next session's autostart asks it to (see
"Stopping, restarting, one instance" in docs/services/input-daemon.md).

Protocol: one JSON array per line. stdin (from the daemon):
  ["osk", "toggle" | "hide" | "press" | "release" | "repeat" | "shift"]
  ["osk", "move", dx, dy]       ["osk", "key_state", "KEY_ESC", true|false]
  ["target", "show" | "hide"]
stdout (to the daemon):
  ["ready"]                     ["visible", true|false]   (keyboard shown / hidden, also by itself)
  ["type", ["KEY_LEFTSHIFT", ...], "KEY_A"]                 (type one key with these modifiers held)
stdin closed (the daemon ended, however it ended) -> this process exits.
argv[1]: the daemon's desktop bindings as JSON (shoulder-button badges on the keyboard).
"""
import json
import logging
import os
import sys

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("GtkLayerShell", "0.1")
from gi.repository import GLib, Gtk, GtkLayerShell  # noqa: E402

from . import osk  # noqa: E402

log = logging.getLogger("rg35xxh-inputd-ui")


class UI:
    def __init__(self, bindings):
        self.out = sys.stdout
        self.kb = osk.OnScreenKeyboard(self._type, bindings)
        self.target = None
        self.visible = False
        self.buf = b""
        GLib.io_add_watch(0, GLib.IO_IN | GLib.IO_HUP | GLib.IO_ERR, self._on_stdin)
        GLib.timeout_add(100, self._poll_visible)   # Hide key / pointer clicks change it too
        self._send("ready")

    def _send(self, *msg):
        try:
            self.out.write(json.dumps(msg) + "\n")
            self.out.flush()
        except (OSError, ValueError):      # daemon gone: stdin EOF ends us next
            pass

    def _type(self, mods, key):
        self._send("type", mods, key)

    def _poll_visible(self):
        if self.kb.visible != self.visible:
            self.visible = self.kb.visible
            self._send("visible", self.visible)
        return True

    def _on_stdin(self, fd, cond):
        try:
            data = os.read(fd, 65536)
        except OSError:
            data = b""
        if not data:
            log.info("daemon gone, exiting")
            loop.quit()
            return False
        self.buf += data
        while b"\n" in self.buf:
            line, self.buf = self.buf.split(b"\n", 1)
            try:
                self._handle(json.loads(line))
            except Exception as e:          # one bad command must not end the keyboard
                log.warning("command %r: %s", line[:80], e)
        return True

    def _handle(self, cmd):
        what, op, *args = cmd
        if what == "osk":
            if op == "toggle":
                self.kb.toggle()
            elif op == "hide":
                if self.kb.visible:
                    self.kb.hide()
            elif op == "move":
                self.kb.move(*args)
            elif op == "press":
                self.kb.press_selected()
            elif op == "release":
                self.kb.release_selected()
            elif op == "repeat":
                self.kb.repeat_selected()
            elif op == "shift":
                self.kb.toggle_shift()
            elif op == "key_state":
                self.kb.key_state(*args)
            self._poll_visible()
        elif what == "target":
            if op == "show":
                self._target().show_all()
            elif self.target:
                self.target.hide()

    def _target(self):
        """The 2x2 px transparent overlay window the hide-pointer tap lands on (top-left corner)."""
        if self.target is None:
            w = Gtk.Window()
            GtkLayerShell.init_for_window(w)
            GtkLayerShell.set_layer(w, GtkLayerShell.Layer.OVERLAY)
            GtkLayerShell.set_namespace(w, "rg35xxh-touch-target")
            GtkLayerShell.set_anchor(w, GtkLayerShell.Edge.TOP, True)
            GtkLayerShell.set_anchor(w, GtkLayerShell.Edge.LEFT, True)
            GtkLayerShell.set_exclusive_zone(w, -1)
            GtkLayerShell.set_keyboard_mode(w, GtkLayerShell.KeyboardMode.NONE)
            w.set_size_request(2, 2)
            visual = w.get_screen().get_rgba_visual()
            if visual:
                w.set_visual(visual)
            w.set_app_paintable(True)

            def clear(_w, cr):
                cr.set_operator(0)          # CAIRO_OPERATOR_CLEAR: fully transparent
                cr.paint()
                return True
            w.connect("draw", clear)
            self.target = w
        return self.target


def main():
    logging.basicConfig(level=logging.INFO, stream=sys.stderr,
                        format="%(asctime)s %(levelname)s ui: %(message)s")
    bindings = json.loads(sys.argv[1]) if len(sys.argv) > 1 else {}
    global loop
    loop = GLib.MainLoop()      # not Gtk.main(): see daemon.py run()
    UI(bindings)
    loop.run()


if __name__ == "__main__":
    main()
