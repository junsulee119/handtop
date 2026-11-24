"""What the Update app shows, as plain data (no GTK): tested by tests/test_model.py."""
import re
import time

STATE = "/var/lib/handtop-update"


def short_version(v, release=None):
    """The release a version belongs to: '0.5.1' -> '0.5.1', '0.5.0+202611231200.gabc1234' -> '0.5.0 (dev build)'.
    release: the metapackage's Handtop-Release field, which names it when present."""
    if not v:
        return release or "unknown"
    if release:
        return release + ("" if v == release else " (dev build)")
    m = re.match(r"^([0-9][0-9.]*)(\+.*)?$", v)
    if not m:
        return v
    return m.group(1) + (" (dev build)" if m.group(2) else "")


def mb(x):
    if x is None:
        return "?"
    return "%.1f MB" % x if x < 100 else "%d MB" % round(x)


def summarize(check):
    """The check's JSON -> what the results page lists."""
    ups = check.get("updates") or []
    handtop = [u for u in ups if u["name"] == "handtop" or u["name"].startswith("handtop-")
               or "Handtop" in (u.get("origin") or "")]
    debian = [u for u in ups if u not in handtop]
    notes = check.get("release_notes") or {}
    meta = next((u for u in ups if u["name"] == "handtop"), None)
    return {
        "nothing": not ups,
        "handtop_release": notes.get("release") or (short_version(meta["new"]) if meta else None),
        "handtop_count": len(handtop),
        "notes": notes.get("lines") or [],
        "debian": [(u["name"], u.get("old") or "new", u["new"]) for u in debian],
        "new_image": bool(check.get("new_image_needed")),
        "download_mb": check.get("download_mb"),
        "warnings": [w for w in check.get("warnings") or [] if w],
    }


def page_for(status):
    """Which page the app opens on, from the worker's status."""
    if status.get("foreign_offline_update"):
        return "foreign"
    if status.get("scheduled"):
        return "scheduled"
    if status.get("downloaded") and status.get("kind") == "update":
        return "ready"
    return "main"


def result_text(res):
    """(title, body, is_error) for the last result, or None."""
    if not res:
        return None
    when = time.strftime("%d %b %Y, %H:%M", time.localtime(res.get("time") or 0))
    msg = (res.get("message") or "").strip()
    if res.get("ok"):
        title = "Updated on %s" % when
        if msg.startswith("back to the previous"):
            title = "Went back to the previous release on %s" % when
        body = ""
        if res.get("kept_config"):
            body = ("These settings files were kept because you had edited them; the new version "
                    "of each is saved next to it:\n" + "\n".join("  " + p for p in res["kept_config"][:8])
                    + ("\n  and %d more" % (len(res["kept_config"]) - 8) if len(res["kept_config"]) > 8 else ""))
        return title, body, False
    if res.get("ok") is None:
        return "Update waiting", msg[:1].upper() + msg[1:], False
    title = "The update stopped (%s)" % when if res.get("interrupted") else "The update failed (%s)" % when
    msg = re.sub(r"^update (failed|not installed): ", "", msg)
    return title, (msg[:1].upper() + msg[1:]) if msg else "", True


def can_install(plan_status):
    """The worker would schedule this plan as far as going back is concerned (it checks the rest)."""
    rb = (plan_status or {}).get("rollback") or {}
    return bool(rb.get("possible", True) or rb.get("no_predecessor"))


def rollback_text(plan_status, previous_release):
    rb = (plan_status or {}).get("rollback") or {}
    if rb.get("no_predecessor"):
        return "This is the first update of this card: going back to the current release won't be possible."
    if rb.get("needed") is False:
        return "Only Debian's packages change; Handtop stays as it is."
    if rb.get("possible"):
        return "If something goes wrong, recovery.txt on the SD card can go back to the release you have now."
    return "Going back would not be possible: %s" % (rb.get("reason") or "unknown reason")


def source_name(line):
    """'Err:1 https://deb.debian.org/debian trixie InRelease' -> 'Debian'."""
    if "handtop" in line:
        return "Handtop"
    if "security" in line:
        return "Debian security"
    if "debian" in line:
        return "Debian"
    m = re.search(r"https?://([^/\s]+)", line)
    return m.group(1) if m else None


def friendly_error(err, details=None):
    """Worker errors -> a sentence for the app (the worker's own text is already plain)."""
    if not err:
        return "Something went wrong."
    e = err.strip()
    low = e.lower()
    if "could not refresh" in low:
        text = " ".join(details or []).lower()
        if any(k in text for k in ("no_pubkey", "badsig", "is not signed", "expkeysig", "not valid yet",
                                   "is expired", "invalid signature", "weak security")):
            return ("The update server's signature couldn't be checked. Check that the date and time are "
                    "right, then try again; if it keeps happening, the server may have a problem.")
        names = sorted({n for n in (source_name(d) for d in details or [] if d.startswith(("Err", "E:")))
                        if n})
        which = (" (%s)" % ", ".join(names)) if names else ""
        return "Couldn't reach every update server%s. Check the Wi-Fi connection and try again." % which
    if "check for updates first" in low:
        return "Check for updates first."
    if "a password is required" in low or "sudo" in low and "not allowed" in low:
        return "The update helper can't run (sudo rule missing). Reinstalling the image fixes this."
    return e[:1].upper() + e[1:]
