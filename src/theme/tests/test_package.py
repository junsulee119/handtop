"""Import (broken and malicious zips), export, duplicate, list, delete."""
import json
import os
import stat
import struct
import zipfile
import zlib

import pytest

from handtop_theme import package, theme
from handtop_theme import schema as S
from handtop_theme.theme import ThemeError

from conftest import minimal, png, write_theme


def make_zip(path, entries, mode=None):
    """entries: {name: bytes}; mode: {name: unix mode} for special entries."""
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, data in entries.items():
            zi = zipfile.ZipInfo(name)
            zi.compress_type = zipfile.ZIP_DEFLATED
            if mode and name in mode:
                zi.external_attr = mode[name] << 16
            zf.writestr(zi, data)
    return str(path)


def good(**kw):
    return {"theme.json": json.dumps(minimal(**kw)).encode(),
            "icons/taskbar/battery-3.png": png(20, 11)}


def do_import(tmp_path, builtins, entries, **kw):
    z = make_zip(tmp_path / "t.handtop-theme", entries, kw.pop("mode", None))
    return package.import_theme(z, str(tmp_path / "user"), builtins, decode=False, **kw)


def leftovers(tmp_path):
    d = tmp_path / "user"
    return sorted(os.listdir(d)) if d.exists() else []


def test_import_good(tmp_path, builtins):
    t = do_import(tmp_path, builtins, good())
    assert t.id == "my-blue" and t.errors == []
    assert leftovers(tmp_path) == ["my-blue"]
    assert "taskbar/battery-3" in t.own


def test_import_folder_zip_and_guide_ignored(tmp_path, builtins):
    e = {f"my-blue/{k}": v for k, v in good().items()}
    e["my-blue/GUIDE.md"] = b"# old guide"
    t = do_import(tmp_path, builtins, e)
    assert t.id == "my-blue" and not os.path.exists(os.path.join(t.path, "GUIDE.md"))


def test_import_ignores_unknown_files(tmp_path, builtins):
    e = good()
    e["evil.sh"] = b"rm -rf ~"
    e["icons/apps/notreal.png"] = png(56, 56)
    t = do_import(tmp_path, builtins, e)
    assert {p.where for p in t.problems if p.level == "warning"} == {"evil.sh", "icons/apps/notreal.png"}
    assert sorted(os.listdir(t.path)) == ["icons", "theme.json"]


@pytest.mark.parametrize("name", ["../theme.json", "/etc/x", "icons/../../x.png", "C:/x", "a\\b.png",
                                  "icons//taskbar/x.png", "./theme.json"])
def test_bad_paths_refused(tmp_path, builtins, name):
    e = good()
    e[name] = b"x"
    with pytest.raises(ThemeError):
        do_import(tmp_path, builtins, e)
    assert leftovers(tmp_path) == []
    assert not (tmp_path / "x").exists()


def test_symlink_refused(tmp_path, builtins):
    e = good()
    e["icons/taskbar/battery-4.png"] = b"/etc/passwd"
    with pytest.raises(ThemeError, match="links"):
        do_import(tmp_path, builtins, e, mode={"icons/taskbar/battery-4.png": stat.S_IFLNK | 0o777})
    assert leftovers(tmp_path) == []


def test_encrypted_refused(tmp_path, builtins):
    z = make_zip(tmp_path / "t.zip", good())
    data = bytearray(open(z, "rb").read())
    # set the "encrypted" flag on every central-directory entry
    i = 0
    while True:
        i = data.find(b"PK\x01\x02", i)
        if i < 0:
            break
        flags = struct.unpack_from("<H", data, i + 8)[0] | 1
        struct.pack_into("<H", data, i + 8, flags)
        i += 4
    open(z, "wb").write(bytes(data))
    with pytest.raises(ThemeError, match="encrypted"):
        package.import_theme(z, str(tmp_path / "user"), builtins, decode=False)


def test_too_many_files(tmp_path, builtins):
    e = good()
    for i in range(S.MAX_FILES):
        e[f"junk/{i}"] = b""
    with pytest.raises(ThemeError, match="more than"):
        do_import(tmp_path, builtins, e)


def test_oversized_entry(tmp_path, builtins):
    e = good()
    e["icons/taskbar/battery-4.png"] = b"\0" * (S.MAX_ICON_BYTES + 1)
    with pytest.raises(ThemeError, match="larger than"):
        do_import(tmp_path, builtins, e)


def test_size_lie_in_zip(tmp_path, builtins):
    """The zip's directory says 10 bytes, the data inflates to far more."""
    z = make_zip(tmp_path / "t.zip", good())
    zf = zipfile.ZipFile(z)
    info = zf.getinfo("icons/taskbar/battery-3.png")
    zf.close()
    data = bytearray(open(z, "rb").read())
    i = 0                                          # patch its central-directory size
    while True:
        i = data.find(b"PK\x01\x02", i)
        if i < 0:
            break
        name_len = struct.unpack_from("<H", data, i + 28)[0]
        if data[i + 46:i + 46 + name_len] == info.filename.encode():
            struct.pack_into("<I", data, i + 24, 10)
        i += 4
    open(z, "wb").write(bytes(data))
    with pytest.raises(ThemeError):
        package.import_theme(z, str(tmp_path / "user"), builtins, decode=False)
    assert leftovers(tmp_path) == []


def test_png_bomb_refused(tmp_path, builtins):
    """A 20x11 PNG whose data inflates to megabytes."""
    def chunk(t, b):
        return struct.pack(">I", len(b)) + t + b + struct.pack(">I", zlib.crc32(t + b) & 0xFFFFFFFF)
    bomb = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 20, 11, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(b"\0" * 50_000_000, 9)) + chunk(b"IEND", b""))
    assert len(bomb) < S.MAX_ICON_BYTES
    e = good()
    e["icons/taskbar/battery-3.png"] = bomb
    with pytest.raises(ThemeError, match="larger than its size"):
        do_import(tmp_path, builtins, e)


def test_not_a_zip_and_bad_json(tmp_path, builtins):
    p = tmp_path / "x.handtop-theme"
    p.write_bytes(b"hello")
    with pytest.raises(ThemeError, match="not a theme file"):
        package.import_theme(str(p), str(tmp_path / "user"), builtins)
    with pytest.raises(ThemeError, match="JSON"):
        do_import(tmp_path, builtins, {"theme.json": b"{"})
    with pytest.raises(ThemeError, match="missing"):
        do_import(tmp_path, builtins, {"icons/taskbar/battery-3.png": png(20, 11)})


def test_reserved_id_refused(tmp_path, builtins):
    with pytest.raises(ThemeError, match="built-in"):
        do_import(tmp_path, builtins, good(id="handtop-blue"))
    with pytest.raises(ThemeError):
        do_import(tmp_path, builtins, good(id="handtop-dark"))
    assert leftovers(tmp_path) == []


def test_exists_and_replace(tmp_path, builtins):
    do_import(tmp_path, builtins, good())
    with pytest.raises(package.ThemeExists):
        do_import(tmp_path, builtins, good(name="Again"))
    t = do_import(tmp_path, builtins, good(name="Again"), replace=True)
    assert t.name == "Again" and leftovers(tmp_path) == ["my-blue"]


def test_bad_theme_leaves_old_one(tmp_path, builtins):
    do_import(tmp_path, builtins, good())
    e = good(name="Broken")
    e["icons/taskbar/battery-4.png"] = png(21, 11)
    with pytest.raises(ThemeError, match="must be 20x11"):
        do_import(tmp_path, builtins, e, replace=True)
    t = theme.load(str(tmp_path / "user" / "my-blue"), builtins)
    assert t.name == "My Blue" and leftovers(tmp_path) == ["my-blue"]


def test_export_import_roundtrip(tmp_path, builtins):
    out = package.export_theme(os.path.join(builtins, "handtop-light"), str(tmp_path / "x.handtop-theme"),
                               builtins)
    names = zipfile.ZipFile(out).namelist()
    assert names[0] == "theme.json" and "GUIDE.md" in names
    own = theme.load(os.path.join(builtins, "handtop-light"), builtins).own
    assert len(names) == 3 + len(own)                  # theme.json, GUIDE.md, wallpaper, images
    # a built-in's export cannot be imported under the same id; a renamed copy can
    with pytest.raises(ThemeError):
        package.import_theme(out, str(tmp_path / "user"), builtins, decode=False)
    d = package.duplicate(os.path.join(builtins, "handtop-light"), "my-light", "My Light",
                          str(tmp_path / "user"), builtins)
    assert d.id == "my-light" and d.errors == [] and len(d.own) == len(
        theme.load(os.path.join(builtins, "handtop-light"), builtins).own)
    out2 = package.export_theme(d.path, str(tmp_path / "y.handtop-theme"), builtins)
    package.delete("my-light", str(tmp_path / "user"))
    t = package.import_theme(out2, str(tmp_path / "user"), builtins, decode=False)
    assert t.id == "my-light" and t.errors == []
    assert json.load(open(os.path.join(t.path, "theme.json")))["name"] == "My Light"


def test_duplicate_rules(tmp_path, builtins):
    src = os.path.join(builtins, "handtop-dark")
    with pytest.raises(ValueError):
        package.duplicate(src, "handtop-x", "X", str(tmp_path / "user"), builtins)
    with pytest.raises(ValueError):
        package.duplicate(src, "Bad Id", "X", str(tmp_path / "user"), builtins)
    package.duplicate(src, "mine", "Mine", str(tmp_path / "user"), builtins)
    with pytest.raises(package.ThemeExists):
        package.duplicate(src, "mine", "Mine", str(tmp_path / "user"), builtins)


def test_list_find_delete(tmp_path, builtins):
    user = tmp_path / "user"
    write_theme(str(user), minimal(id="zeta"))
    write_theme(str(user), minimal(id="handtop-fake"))       # reserved in the user folder: skipped
    (user / "Bad Name").mkdir()
    (user / ".import-x").mkdir()
    got = package.list_themes(builtins, str(user))
    assert [(i, b) for i, _p, b in got] == [("handtop-dark", True), ("handtop-debian", True),
                                            ("handtop-grayscale", True), ("handtop-high-contrast", True),
                                            ("handtop-light", True), ("zeta", False)]
    assert package.find("zeta", builtins, str(user)).endswith("zeta")
    assert package.find("handtop-fake", builtins, str(user)) is None
    with pytest.raises(ValueError):
        package.delete("handtop-dark", str(user))
    package.delete("zeta", str(user))
    assert not (user / "zeta").exists()


def test_refusal_lists_json_and_image_problems(tmp_path, builtins):
    e = {"theme.json": json.dumps(minimal(colors={"osk.bg": "green"})).encode(),
         "icons/taskbar/battery-3.png": png(22, 11)}
    with pytest.raises(ThemeError) as err:
        do_import(tmp_path, builtins, e)
    assert {p.where for p in err.value.problems} == {"colors.osk.bg", "icons/taskbar/battery-3.png"}
