"""handtop_media.files: listing order, covers, resume positions, time format (no GTK)."""
import hashlib
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from handtop_media import files  # noqa: E402


def test_listing_natural_order_folders_first_hidden_left_out(tmp_path):
    for d in ("Album 10", "album 2", ".hidden"):
        (tmp_path / d).mkdir()
    for f in ("Track 10.mp3", "track 2.FLAC", "notes.txt", ".x.mp3", "cover.jpg"):
        (tmp_path / f).write_bytes(b"")
    folders, names = files.listing(str(tmp_path), files.AUDIO)
    assert folders == ["album 2", "Album 10"]
    assert names == ["track 2.FLAC", "Track 10.mp3"]


def test_listing_unreadable_folder_is_empty(tmp_path):
    assert files.listing(str(tmp_path / "missing"), files.VIDEO) == ([], [])


def test_cover_file_any_case(tmp_path):
    assert files.cover_file(str(tmp_path)) is None
    (tmp_path / "Folder.JPG").write_bytes(b"")
    assert files.cover_file(str(tmp_path)) == str(tmp_path / "Folder.JPG")
    (tmp_path / "cover.png").write_bytes(b"")
    assert files.cover_file(str(tmp_path)) == str(tmp_path / "cover.png")   # "cover" first


def test_title_and_time():
    assert files.title_of("01 Song.name.mp3") == "01 Song.name"
    assert files.title_of("README") == "README"
    assert files.fmt_time(187) == "3:07"
    assert files.fmt_time(3723) == "1:02:03"
    assert files.fmt_time(None) == "" and files.fmt_time(-1) == ""


def test_resume_pos_reads_mpv_watch_later(tmp_path):
    path = "/home/rg/Videos/a b.mkv"
    name = hashlib.md5(path.encode()).hexdigest().upper()
    assert files.resume_pos(path, str(tmp_path)) is None
    (tmp_path / name).write_text("# /home/rg/Videos/a b.mkv\nstart=754.250000\nvolume=80\n")
    assert files.resume_pos(path, str(tmp_path)) == 754.25
    (tmp_path / name).write_text("start=0.4\n")            # the very start: no "Resume at"
    assert files.resume_pos(path, str(tmp_path)) is None
    (tmp_path / name).write_text("start=bad\n")
    assert files.resume_pos(path, str(tmp_path)) is None


def test_under(tmp_path):
    (tmp_path / "a" / "b").mkdir(parents=True)
    assert files.under(str(tmp_path / "a" / "b"), str(tmp_path / "a"))
    assert files.under(str(tmp_path / "a"), str(tmp_path / "a"))
    assert not files.under(str(tmp_path / "ab"), str(tmp_path / "a"))
