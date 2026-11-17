"""handtop_media.player with a fake mpv module: queue, repeat, previous, the auto-sleep flag."""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
pytest.importorskip("gi")

from handtop_media import player as P  # noqa: E402


class FakeMPV:
    def __init__(self, **kw):
        self.kw = kw
        self.commands = []
        self.observers = {}
        self.time_pos = 0.0
        self.terminated = False

    def observe_property(self, name, cb):
        self.observers[name] = cb

    def command(self, *a):
        self.commands.append(a)

    def terminate(self):
        self.terminated = True


class FakeModule:
    MPV = FakeMPV


@pytest.fixture
def pl(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
    monkeypatch.setattr(P.GLib, "idle_add", lambda f, *a: f(*a))
    changes = []
    p = P.Player(lambda: changes.append(1), mpv_module=FakeModule)
    p.changes = changes
    return p


def test_no_config_no_video(pl):
    kw = pl.m.kw
    assert kw["config"] is False and kw["video"] is False and kw["ytdl"] is False


def test_play_replaces_queue(pl):
    pl.play(["/m/a.mp3", "/m/b.mp3"], 1)
    assert pl.m.commands == [("stop",), ("loadfile", "/m/a.mp3", "append"),
                             ("loadfile", "/m/b.mp3", "append"), ("set", "playlist-pos", "1"),
                             ("set", "pause", "no")]


def test_repeat_cycles_off_all_one(pl):
    assert pl.repeat() == "off"
    assert pl.cycle_repeat() == "all"
    pl.m.observers["loop-playlist"]("loop-playlist", "inf")
    assert pl.repeat() == "all"
    assert pl.cycle_repeat() == "one"
    pl.m.observers["loop-playlist"]("loop-playlist", False)
    pl.m.observers["loop-file"]("loop-file", "inf")
    assert pl.repeat() == "one"
    assert pl.cycle_repeat() == "off"


def test_prev_restarts_song_after_3_s(pl):
    pl.m.observers["idle-active"]("idle-active", False)
    pl.m.observers["playlist-pos"]("playlist-pos", 2)
    pl.m.time_pos = 10.0
    pl.prev()
    assert pl.m.commands[-1] == ("seek", "0", "absolute")
    pl.m.time_pos = 1.0
    pl.prev()
    assert pl.m.commands[-1] == ("playlist-prev", "weak")


def test_flag_while_playing_only(pl, tmp_path):
    flag = tmp_path / P.FLAG
    pl.m.observers["idle-active"]("idle-active", False)
    pl.m.observers["pause"]("pause", False)
    assert flag.read_text().strip() == str(os.getpid())
    pl.m.observers["pause"]("pause", True)
    assert not flag.exists()
    pl.m.observers["pause"]("pause", False)
    assert flag.exists()
    pl.close()
    assert not flag.exists() and pl.m.terminated


def test_title_from_tags_or_file_name(pl):
    pl.m.observers["path"]("path", "/m/03 Song.flac")
    assert pl.title() == ("03 Song", "", "")
    pl.m.observers["metadata"]("metadata", {"TITLE": "Song", "ARTIST": "Band", "Album": "LP"})
    assert pl.title() == ("Song", "Band", "LP")
