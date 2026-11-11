"""Image work with GdkPixbuf (on the device through GTK; no Pillow): load, scale, shift.

Tests replace these with stubs when GdkPixbuf is not installed (CI)."""


def _gdk():
    import gi
    gi.require_version("GdkPixbuf", "2.0")
    from gi.repository import GdkPixbuf
    return GdkPixbuf


def available():
    try:
        _gdk()
        return True
    except (ImportError, ValueError):
        return False


def load(path):
    return _gdk().Pixbuf.new_from_file(path)


def size(path):
    pb = load(path)
    return pb.get_width(), pb.get_height()


def scale(src, dst, w, h):
    """Smooth downscale (HYPER, close to Lanczos) for small app icons."""
    G = _gdk()
    pb = load(src)
    if not pb.get_has_alpha():
        pb = pb.add_alpha(False, 0, 0, 0)
    pb.scale_simple(w, h, G.InterpType.HYPER).savev(dst, "png", [], [])


def shift(src, dst, dx):
    """The whole image moved dx px sideways on a transparent canvas of the same size (a shake
    frame made from a theme's own input-mode icon)."""
    G = _gdk()
    pb = load(src)
    if not pb.get_has_alpha():
        pb = pb.add_alpha(False, 0, 0, 0)
    w, h = pb.get_width(), pb.get_height()
    out = G.Pixbuf.new(G.Colorspace.RGB, True, 8, w, h)
    out.fill(0x00000000)
    sx, tx, cw = (0, dx, w - dx) if dx >= 0 else (-dx, 0, w + dx)
    if cw > 0:
        pb.copy_area(sx, 0, cw, h, out, tx, 0)
    out.savev(dst, "png", [], [])


def argb(src, size):
    """The image scaled to size x size (HYPER; exact for pixel art drawn at 2x) as premultiplied
    ARGB ints, for an Xcursor image."""
    G = _gdk()
    pb = load(src)
    if not pb.get_has_alpha():
        pb = pb.add_alpha(False, 0, 0, 0)
    if (pb.get_width(), pb.get_height()) != (size, size):
        pb = pb.scale_simple(size, size, G.InterpType.HYPER)
    data, stride = pb.get_pixels(), pb.get_rowstride()
    out = []
    for y in range(size):
        row = data[y * stride:y * stride + size * 4]
        for x in range(0, size * 4, 4):
            r, g, b, a = row[x], row[x + 1], row[x + 2], row[x + 3]
            out.append(a << 24 | (r * a // 255) << 16 | (g * a // 255) << 8 | (b * a // 255))
    return out
