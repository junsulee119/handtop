"""Unit tests for the Display app's layout code (overlay/usr/local/bin/rg35xxh-display), with
wlr-randr and notify-send replaced: nothing touches a real output. Run from the repo:
python3 -m pytest -q tests. The cases come from the codebase audit of 2026-10-30 (M09, M10)."""
import importlib.machinery
import importlib.util
import os
import subprocess

TOP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
path = os.path.join(TOP, "overlay", "usr", "local", "bin", "rg35xxh-display")
loader = importlib.machinery.SourceFileLoader("rg35xxh_display", path)
display = importlib.util.module_from_spec(importlib.util.spec_from_loader(loader.name, loader))
loader.exec_module(display)


def monitor(w, h, scale=1.0, transform="normal"):
    return {"name": "HDMI-A-1", "enabled": True, "scale": scale, "transform": transform,
            "position": {"x": 0, "y": 0},
            "modes": [{"width": w, "height": h, "refresh": 60.0, "current": True}]}


def handheld():
    return {"name": display.INTERNAL, "enabled": True, "scale": 1.0, "transform": "normal",
            "position": {"x": 0, "y": 0},
            "modes": [{"width": 640, "height": 480, "refresh": 60.0, "current": True}]}


# ---- M09: the extend layout uses the monitor's size in layout coordinates
def test_logical_size():
    md = {"width": 3840, "height": 2160}
    assert display.logical_size(monitor(3840, 2160), md) == (3840, 2160)
    assert display.logical_size(monitor(3840, 2160, scale=2), md) == (1920, 1080)
    assert display.logical_size(monitor(3840, 2160, scale=1.5), md) == (2560, 1440)
    assert display.logical_size(monitor(3840, 2160, scale=2, transform="90"), md) == (1080, 1920)
    assert display.logical_size(monitor(3840, 2160, transform="flipped-270"), md) == (2160, 3840)


def extend_with(monkeypatch, tmp_path, mon):
    calls = []
    monkeypatch.setattr(display, "outputs", lambda timeout=5: {"HDMI-A-1": mon, display.INTERNAL: handheld()})
    monkeypatch.setattr(display, "randr", lambda *a: calls.append(a))
    monkeypatch.setattr(display, "mode", lambda: "extend")
    monkeypatch.setattr(display, "PICKER_FLAG", str(tmp_path / "no-picker"))
    monkeypatch.setattr(display, "OSK_FLAG", str(tmp_path / "no-osk"))
    monkeypatch.setattr(display, "saved_spec", lambda ext: None)
    display._apply()
    return next(c for c in calls if c[:2] == ("--output", display.INTERNAL))


def test_extend_places_handheld_below_a_scaled_monitor(monkeypatch, tmp_path):
    # the audit's case: 3840x2160 at scale 2 -> handheld at 640,1080 (was 1600,2160: a gap)
    call = extend_with(monkeypatch, tmp_path, monitor(3840, 2160, scale=2))
    assert call[-1] == "640,1080"


def test_extend_at_scale_1_unchanged(monkeypatch, tmp_path):
    call = extend_with(monkeypatch, tmp_path, monitor(1920, 1080))
    assert call[-1] == "640,1080"


def test_pointer_layout_uses_the_same_size(monkeypatch, tmp_path):
    out = tmp_path / "layout"
    monkeypatch.setattr(display, "POINTER_LAYOUT", str(out))
    monkeypatch.setattr(display, "outputs", lambda timeout=5: {"HDMI-A-1": monitor(3840, 2160, scale=2, transform="90")})
    display.write_pointer_layout()
    import json
    (rect,) = json.loads(out.read_text())
    assert (rect["w"], rect["h"]) == (1080, 1920)


# ---- M10: external commands have a time limit and never raise
def test_stuck_commands_time_out_and_do_not_raise(monkeypatch):
    seen = []

    def run(cmd, **kw):
        seen.append((cmd[0], kw.get("timeout")))
        raise subprocess.TimeoutExpired(cmd, kw.get("timeout"))
    monkeypatch.setattr(display.subprocess, "run", run)
    display.randr("--output", "HDMI-A-1", "--off")
    display.notify("hello")
    assert seen == [("wlr-randr", 5), ("notify-send", 3)]


def test_missing_notify_send_does_not_raise(monkeypatch):
    def run(cmd, **kw):
        raise FileNotFoundError(cmd[0])
    monkeypatch.setattr(display.subprocess, "run", run)
    display.notify("hello")
