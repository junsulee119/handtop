"""Shared helpers for the theme tests. Run from the repo: python3 -m pytest -q src/theme/tests
(or cd src/theme && python3 -m pytest -q tests). No GdkPixbuf needed: image scaling and shifting
use a stub here; test_gdk.py covers the real ones where GdkPixbuf is installed (the device)."""
import json
import os
import shutil
import struct
import sys
import zlib

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))                     # src/theme
REPO = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))

from handtop_theme import builtin  # noqa: E402


def png(w, h, rgba=(255, 0, 0, 255)):
    """A solid RGBA PNG, written with the standard library."""
    def chunk(t, b):
        return struct.pack(">I", len(b)) + t + b + struct.pack(">I", zlib.crc32(t + b) & 0xFFFFFFFF)
    raw = b"".join(b"\x00" + bytes(rgba) * w for _ in range(h))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


class StubOps:
    """Records generated images instead of decoding them."""
    def __init__(self):
        self.calls = []

    def scale(self, src, dst, w, h):
        self.calls.append(("scale", src, dst, w, h))
        with open(dst, "wb") as f:
            f.write(png(w, h))

    def shift(self, src, dst, dx):
        self.calls.append(("shift", src, dst, dx))
        shutil.copyfile(src, dst)


@pytest.fixture(scope="session")
def builtins(tmp_path_factory):
    d = tmp_path_factory.mktemp("builtin")
    builtin.assemble(REPO, str(d))
    return str(d)


@pytest.fixture
def ops():
    return StubOps()


def write_theme(root, data, files=None):
    """A theme folder root/<id> with theme.json = data and files {rel: bytes}."""
    d = os.path.join(root, data.get("id", "t"))
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "theme.json"), "w") as f:
        json.dump(data, f)
    for rel, b in (files or {}).items():
        p = os.path.join(d, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "wb") as f:
            f.write(b)
    return d


def minimal(**kw):
    d = {"schema": 1, "id": "my-blue", "name": "My Blue", "base": "dark"}
    d.update(kw)
    return d
