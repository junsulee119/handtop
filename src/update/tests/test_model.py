import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from handtop_update import model as M  # noqa: E402
from handtop_update import worker as W  # noqa: E402


def test_short_version():
    assert M.short_version("0.5.1") == "0.5.1"
    assert M.short_version("0.5.0+202611231200.gabc1234") == "0.5.0 (dev build)"
    assert M.short_version(None) == "unknown"


def test_summarize_splits_handtop_and_debian():
    s = M.summarize(W._CHECK)
    assert s["handtop_release"] == "0.5.1" and s["handtop_count"] == 4
    assert len(s["debian"]) == 5 and s["debian"][0][0] == "openssl"
    assert s["notes"] and not s["new_image"] and s["download_mb"] == 24.6


def test_summarize_nothing():
    assert M.summarize({"updates": []})["nothing"]


def test_page_for():
    assert M.page_for({"scheduled": True, "downloaded": True, "kind": "update"}) == "scheduled"
    assert M.page_for({"downloaded": True, "kind": "update"}) == "ready"
    assert M.page_for({"downloaded": True, "kind": "recovery"}) == "main"
    assert M.page_for({"foreign_offline_update": True}) == "foreign"
    assert M.page_for({}) == "main"


def test_result_text():
    assert M.result_text(None) is None
    t, body, err = M.result_text({"ok": False, "time": 0, "message": "update failed: x", "interrupted": True})
    assert err and "stopped" in t and body == "X"
    t, body, err = M.result_text({"ok": True, "time": 0, "message": "update installed; restarting",
                                  "kept_config": ["/etc/a.dpkg-dist"]})
    assert not err and "/etc/a.dpkg-dist" in body
    t, _, _ = M.result_text({"ok": True, "time": 0, "message": "back to the previous Handtop release; restarting"})
    assert t.startswith("Went back")


def test_rollback_text():
    assert "first update" in M.rollback_text({"rollback": {"no_predecessor": True}}, None)
    assert "Debian" in M.rollback_text({"rollback": {"needed": False}}, None)
    assert "recovery.txt" in M.rollback_text({"rollback": {"needed": True, "possible": True}}, "0.5.0")
    assert "not be possible: x" in M.rollback_text({"rollback": {"needed": True, "possible": False,
                                                                  "reason": "x"}}, None)


def test_friendly_error():
    assert "Wi-Fi" in M.friendly_error("could not refresh every package list")
    e = M.friendly_error("could not refresh every package list",
                         ["Err:1 https://junsulee119.github.io/handtop-apt trixie-stable InRelease",
                          "Err:2 https://security.debian.org/debian-security trixie-security InRelease"])
    assert "(Debian security, Handtop)" in e
    assert M.friendly_error("battery at 31%: connect") == "Battery at 31%: connect"
