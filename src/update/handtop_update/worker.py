"""Talking to the update worker (sudo -n /usr/local/sbin/handtop-update <command>) and reading what
an unprivileged app may read. HANDTOP_UPDATE_FAKE=<scenario> replaces the worker with canned answers
(screenshots in every theme without a real update: tools/update-app-shots.sh)."""
import json
import os
import subprocess
import time

WORKER = "/usr/local/sbin/handtop-update"
STATE = "/var/lib/handtop-update"
FAKE = os.environ.get("HANDTOP_UPDATE_FAKE")
TIMEOUTS = {"status": 60, "check": 900, "download": 4000, "schedule": 300, "cancel": 300, "channel": 300}


def call(*args):
    """Run a worker command: its JSON answer, or {"ok": False, "error": ...}."""
    if FAKE:
        return fake(args)
    try:
        p = subprocess.run(["sudo", "-n", WORKER] + list(args), stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE, text=True, timeout=TIMEOUTS.get(args[0], 600))
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "the update helper took too long (%s)" % args[0]}
    except OSError as e:
        return {"ok": False, "error": str(e)}
    try:
        res = json.loads(p.stdout)
    except ValueError:
        res = {"ok": False, "error": (p.stderr or p.stdout or "no answer").strip()[-300:]}
    if args[0] == "status" and "ok" not in res:
        res["ok"] = p.returncode == 0
    return res


def installed_release():
    """The installed release's name (Handtop-Release of the handtop metapackage), or None."""
    if FAKE:
        return None
    try:
        p = subprocess.run(["dpkg-query", "-W", "-f", "${Handtop-Release}", "handtop"], stdout=subprocess.PIPE,
                           stderr=subprocess.DEVNULL, text=True, timeout=30)
        return p.stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        return None


def installed_version():
    if FAKE:
        return "0.5.0"
    try:
        p = subprocess.run(["dpkg-query", "-W", "-f", "${Version}", "handtop"], stdout=subprocess.PIPE,
                           stderr=subprocess.DEVNULL, text=True, timeout=30)
        return p.stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        return None


def downloaded_mb():
    """How much of the update is in the cache so far (finished files; apt keeps partial ones private)."""
    if FAKE:
        return 4.2
    total = 0
    try:
        for f in os.listdir(os.path.join(STATE, "cache")):
            if f.endswith(".deb"):
                try:
                    total += os.path.getsize(os.path.join(STATE, "cache", f))
                except OSError:
                    pass
    except OSError:
        pass
    return total / (1 << 20)


def clock():
    """(synchronised, plausible): NTP says it's synchronised; the year is not before this build's."""
    if FAKE:
        return FAKE != "clock", FAKE != "clock"
    sync = False
    try:
        p = subprocess.run(["timedatectl", "show", "-p", "NTPSynchronized", "--value"], stdout=subprocess.PIPE,
                           stderr=subprocess.DEVNULL, text=True, timeout=10)
        sync = p.stdout.strip() == "yes"
    except (OSError, subprocess.SubprocessError):
        pass
    return sync, time.localtime().tm_year >= 2026


def signal_badge():
    """Tell the taskbar's update badge to look again (Waybar image#update, signal 11)."""
    if not FAKE:
        subprocess.run(["pkill", "-RTMIN+11", "-x", "waybar"], stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL)


# ---- canned answers for screenshots ---------------------------------------------------------------

_CHECK = {"ok": True, "download_mb": 24.6, "new_image_needed": [], "handtop_held": False, "warnings": [],
          "release_notes": {"release": "0.5.1", "lines": [
              "Updates without reflashing: an Update app, safe installs at restart and recovery.txt",
              "New: Update app", "Fixed: the pointer sometimes jumped after sleep",
              "Faster app drawer with many apps"]},
          "updates": [{"name": "handtop", "old": "0.5.0", "new": "0.5.1", "origin": "Handtop:trixie-stable"}] +
          [{"name": n, "old": "0.5.0", "new": "0.5.1", "origin": "Handtop:trixie-stable"}
           for n in ("handtop-core", "handtop-desktop", "handtop-video")] +
          [{"name": n, "old": o, "new": v, "origin": "Debian-Security:13/stable-security"} for n, o, v in (
              ("openssl", "3.5.1-1", "3.5.1-1+deb13u1"), ("libssl3t64", "3.5.1-1", "3.5.1-1+deb13u1"),
              ("chromium", "142.0.7444.59-1~deb13u1", "142.0.7444.162-1~deb13u1"),
              ("chromium-common", "142.0.7444.59-1~deb13u1", "142.0.7444.162-1~deb13u1"),
              ("tzdata", "2025b-4", "2025b-4+deb13u1"))]}


def fake(args):
    s = FAKE
    cmd = args[0]
    now = int(time.time()) - 3600
    if cmd == "status":
        st = {"ok": True, "downloaded": s in ("ready", "scheduled"), "kind": "update", "plan": "a1b2c3d4e5f6",
              "packages": 9, "scheduled": s == "scheduled", "after": "restart" if s == "scheduled" else None,
              "foreign_offline_update": False, "previous_release": "0.4.9", "joypad_override": False,
              "channel": "testing" if s == "advanced" else "stable", "reboot_required": False,
              "rollback": {"needed": True, "possible": True, "reason": None, "no_predecessor": False},
              "last_result": None}
        if s == "failed":
            st["last_result"] = {"ok": False, "time": now, "message": "update failed: not enough free space to "
                                 "install (80 MB free)", "final": True}
        if s == "done":
            st["last_result"] = {"ok": True, "time": now, "message": "update installed; restarting",
                                 "kept_config": ["/etc/rg35xxh/power.conf.dpkg-dist"], "final": True}
        return st
    if cmd == "check":
        if s == "offline":
            return {"ok": False, "error": "could not refresh every package list",
                    "details": ["Err:1 https://junsulee119.github.io/handtop-apt trixie-stable InRelease"]}
        if s == "uptodate":
            return dict(_CHECK, updates=[], release_notes=None, download_mb=0)
        if s == "newimage":
            ups = [u for u in _CHECK["updates"] if not u["name"].startswith("handtop")]
            return dict(_CHECK, updates=ups, new_image_needed=["handtop-modules-h700-7.3.0"], handtop_held=True,
                        release_notes=None, download_mb=19.0)
        return _CHECK
    if cmd == "download":
        time.sleep(1.5)
        return {"ok": True, "plan": "a1b2c3d4e5f6", "packages": 9, "download_mb": 24.6,
                "rollback": {"needed": True, "possible": True, "reason": None, "no_predecessor": False}}
    if cmd == "schedule":
        if s == "battery":
            return {"ok": False, "error": "battery at 31%: connect the charger or charge to 40% first"}
        return {"ok": True, "after": args[1] if len(args) > 1 else "restart"}
    return {"ok": True}
