#!/bin/bash
# Screenshots of the Update app (and its taskbar badge) in all nine built-in themes, without real
# updates: the app runs with HANDTOP_UPDATE_FAKE (canned worker answers, src/update/handtop_update/
# worker.py) in a headless labwc session (as tools/headless-test.sh) inside a copy of a finished
# rootfs, with this checkout's overlay, theme system and Update app installed. Output:
# work/screens/update/<theme>-<page>.png.
#
#   sudo SRC_WORK=/path/to/finished/work tools/update-app-shots.sh   (in a second checkout or worktree)
set -euo pipefail
source "$(dirname "$(realpath "$0")")/../build/config.sh"
source "$TOP/build/lib/chroot.sh"
SRC_WORK="$(realpath "${SRC_WORK:?SRC_WORK: the work directory of a finished build}")"
[ "$(realpath -m "$WORK")" != "$SRC_WORK" ] || die "WORK must be a scratch directory, not SRC_WORK"
assert_scratch_copy "$SRC_WORK"
trap chroot_umount EXIT
mkdir -p "$WORK"
assert_no_mounts "$SRC_WORK/rootfs" "$ROOTFS"
rsync -aHAXx --delete --numeric-ids "$SRC_WORK/rootfs/" "$ROOTFS/"
rsync -a --chown=root:root --chmod=D755,F644 "$TOP/overlay/" "$ROOTFS/"
chmod 755 "$ROOTFS"/usr/local/sbin/* "$ROOTFS"/usr/local/bin/*
"$TOP/build/07d-theme.sh" >/dev/null
"$TOP/build/07f-update-app.sh" >/dev/null
# The badge reads the worker's state: a downloaded update shows it.
mkdir -p "$ROOTFS/var/lib/handtop-update"
printf '{\n "id": "shots",\n "kind": "update"\n}\n' > "$ROOTFS/var/lib/handtop-update/plan.json"

# THEMES and SHOTS (scenario:page pairs) narrow a run, e.g. to look into one page.
THEMES="${THEMES:-handtop-dark handtop-light handtop-retro handtop-glass handtop-pocket handtop-signal handtop-debian handtop-high-contrast handtop-grayscale}"
SHOTS="${SHOTS:-failed:main updates:results ready:ready advanced:advanced}"
chroot_mount
UID_T=$(chroot "$ROOTFS" id -u "$USER_NAME")
mkdir -p "$ROOTFS/run/user/$UID_T" && chroot "$ROOTFS" chown "$USER_NAME:" "/run/user/$UID_T" && chmod 700 "$ROOTFS/run/user/$UID_T"
S="$ROOTFS/tmp/screens"; [ -e "$S" ] && safe_rm -r "$S"; mkdir -p "$S"; chmod 777 "$S"
cat > "$S/run.sh" <<'R'
sleep 4
wlr-randr --output HEADLESS-1 --custom-mode 640x480
sleep 60
for t in $THEMES; do
  rg35xxh-theme "$t" >/dev/null 2>&1; sleep 25
  for shot in $SHOTS; do
    set -- $(echo "$shot" | tr : " ")
    page=$2; [ "$page" = main ] || [ "$page" = ready ] && page=""
    # The app runs emulated here and takes a while: shoot once trace.py says the page has settled.
    HANDTOP_UPDATE_FAKE=$1 python3 /tmp/screens/trace.py ${page:+--page $page} > "/tmp/screens/$t-$2.log" 2>&1 &
    app=$!
    for _ in $(seq 120); do grep -q '^settled' "/tmp/screens/$t-$2.log" && break; sleep 1; done
    sleep 1; grim "/tmp/screens/$t-$2.png"
    # The app allows one window at a time, so the next shot waits until this one has gone.
    kill ${SHOTS_TRACE:+-ABRT} "$app" 2>/dev/null
    for _ in 1 2 3 4 5 6 7 8 9 10; do kill -0 "$app" 2>/dev/null || break; sleep 1; done
    kill -9 "$app" 2>/dev/null; wait "$app" 2>/dev/null; sleep 1
  done
done
labwc --exit
R
chmod +x "$S/run.sh"
cat > "$S/trace.py" <<'P'
# The Update app, telling the shots loop when its page has settled: not busy, the window mapped and
# its size unchanged for two seconds (the maximize from labwc's window rule has arrived).
import sys
sys.path.insert(0, "/usr/local/lib/rg35xxh-update")
from gi.repository import GLib
GLib.set_prgname("rg35xxh-update")     # the app's own icon in the title bar and taskbar, as when launched
from handtop_update import app

App = app.App


class Traced(App):
    def __init__(self, page):
        App.__init__(self, page)
        self.last, self.same, self.told = None, 0, False
        GLib.timeout_add(1000, self.trace)

    def trace(self):
        w, a = self.win, self.stack.get_allocation()
        now = (self.busy, self.stack.get_visible_child_name(), w.get_mapped(), tuple(w.get_size()),
               a.width, a.height)
        self.same = self.same + 1 if now == self.last else 0
        self.last = now
        print("busy=%s page=%s mapped=%s win=%s stack=%dx%d" % now, flush=True)
        if not self.told and not self.busy and w.get_mapped() and self.same >= 2:
            print("settled", flush=True)
            self.told = True
        return True


app.App = Traced
app.run()
P
timeout 3600 chroot "$ROOTFS" runuser -u "$USER_NAME" -- env HOME="/home/$USER_NAME" \
  XDG_RUNTIME_DIR="/run/user/$UID_T" THEMES="$THEMES" SHOTS="$SHOTS" SHOTS_TRACE="${SHOTS_TRACE:-}" \
  PYTHONFAULTHANDLER=1 WLR_BACKENDS=headless WLR_RENDERER=pixman WLR_LIBINPUT_NO_DEVICES=1 \
  dbus-run-session labwc -s /tmp/screens/run.sh > "$WORK/update-shots.log" 2>&1 || true
mkdir -p "$WORK/screens/update" && cp "$S"/*.png "$S"/*.log "$WORK/screens/update/" 2>/dev/null || true
chmod -R a+rX "$WORK/screens"
ls "$WORK/screens/update" | wc -l
