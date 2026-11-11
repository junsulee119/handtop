"""The real image work (imgops.py, GdkPixbuf). Skipped where GdkPixbuf is not installed (CI);
run on the device: python3 -m pytest -q src/theme/tests/test_gdk.py"""
import os

import pytest

from handtop_theme import imgops, package, pngcheck, render, theme

pytestmark = pytest.mark.skipif(not imgops.available(), reason="GdkPixbuf not installed")


def test_builtins_decode(builtins):
    for tid in ("handtop-dark", "handtop-light"):
        t = theme.load(os.path.join(builtins, tid), builtins, decode=True)
        assert t.problems == []


def test_scale_and_shift(tmp_path, builtins):
    src = os.path.join(builtins, "handtop-dark/icons/apps/thunar.png")
    imgops.scale(src, str(tmp_path / "s.png"), 20, 20)
    assert imgops.size(str(tmp_path / "s.png")) == (20, 20)
    gp = os.path.join(builtins, "handtop-dark/icons/taskbar/inputmode-gamepad.png")
    for dx in (-2, 2):
        out = str(tmp_path / f"h{dx}.png")
        imgops.shift(gp, out, dx)
        a, b = imgops.load(gp), imgops.load(out)
        assert (b.get_width(), b.get_height()) == (23, 23)
        pa, pb, rs = a.get_pixels(), b.get_pixels(), a.get_rowstride()
        x = 10
        assert pb[11 * rs + (x + dx) * 4: 11 * rs + (x + dx) * 4 + 4] == pa[11 * rs + x * 4: 11 * rs + x * 4 + 4]


def test_render_with_real_ops(tmp_path, builtins):
    from conftest import minimal, png, write_theme
    d = write_theme(str(tmp_path), minimal(), {"icons/taskbar/inputmode-bt.png": png(23, 23),
                                               "icons/apps/htop.png": png(56, 56)})
    t = theme.load(d, builtins, decode=True)
    out = render.render(t, str(tmp_path / "theme"))
    assert imgops.size(os.path.join(out, "icons/inputmode-bt-shake-2.png")) == (23, 23)
    assert imgops.size(os.path.join(out, "icon-theme/20x20/apps/htop.png")) == (20, 20)


def test_decode_refuses_garbage(tmp_path):
    p = tmp_path / "x.png"
    p.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\0" * 40)
    with pytest.raises(pngcheck.BadPNG):
        pngcheck.decode(str(p))


def test_import_decodes(tmp_path, builtins):
    out = package.export_theme(os.path.join(builtins, "handtop-dark"), str(tmp_path / "x.handtop-theme"), builtins)
    d = package.duplicate(os.path.join(builtins, "handtop-dark"), "copy", "Copy", str(tmp_path / "u"), builtins)
    out = package.export_theme(d.path, str(tmp_path / "c.handtop-theme"), builtins)
    package.delete("copy", str(tmp_path / "u"))
    t = package.import_theme(out, str(tmp_path / "u"), builtins, decode=True)
    assert t.errors == []


def test_grayscale_images_are_grey(builtins):
    from handtop_theme import schema as S
    t = theme.load(os.path.join(builtins, "handtop-grayscale"), builtins, decode=True)
    assert t.problems == []
    for slot in ("taskbar/inputmode-bt", "taskbar/battery-charging-low-1", "apps/chromium", "power-menu/shutdown"):
        pb = imgops.load(t.images[slot][1])
        px, n = pb.get_pixels(), pb.get_n_channels()
        for i in range(0, len(px) - n, n):
            assert px[i] == px[i + 1] == px[i + 2], slot
        assert S.IMAGE_SLOTS[slot][:2] == (pb.get_width(), pb.get_height())


def test_argb_for_pointer(tmp_path):
    from conftest import png
    f = tmp_path / "p.png"
    f.write_bytes(png(48, 48, (255, 0, 0, 128)))
    px = imgops.argb(str(f), 24)
    assert len(px) == 24 * 24
    assert px[0] >> 24 == 128 and (px[0] >> 16) & 0xff == 128   # premultiplied red at half alpha
