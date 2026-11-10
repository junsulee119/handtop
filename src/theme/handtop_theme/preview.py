"""A small picture of a theme for the Theme app: wallpaper, a window, a notification and the
taskbar, drawn with cairo from the theme's own colours and images (the theme's preview.png when
it has one). Imports cairo, so only the app uses it."""
import os

import cairo

from . import schema as S


def _rgb(c):
    v = [int(c[i:i + 2], 16) / 255 for i in range(1, len(c), 2)]
    return v if len(v) == 4 else v + [1.0]


STOCK = "/usr/share/icons/hicolor/22x22"     # the packages' own tray icons ("system")


def _image(t, slot, cache):
    how = t.images.get(slot, ("system",))
    if how[0] == "file":
        path = how[1]
    elif how[0] == "system" and slot.startswith("tray/"):
        name = slot.split("/")[1]
        path = f"{STOCK}/{'status' if name.startswith('blueman') else 'apps'}/{name}.png"
    else:
        return None
    if path not in cache:
        try:
            cache[path] = cairo.ImageSurface.create_from_png(path)
        except (OSError, cairo.Error):
            cache[path] = None
    return cache[path]


def _paste(cr, img, x, y, h):
    """Paint img at (x, y) scaled to height h, pixel-sharp. Returns the width used."""
    z = h / img.get_height()
    cr.save()
    cr.translate(x, y)
    cr.scale(z, z)
    cr.set_source_surface(img, 0, 0)
    cr.get_source().set_filter(cairo.FILTER_NEAREST)
    cr.paint()
    cr.restore()
    return img.get_width() * z


def draw(t, W, H, font="Noto Sans", own_picture=True):
    """An ARGB32 surface W x H showing theme t (a resolved theme.Theme). own_picture: use the
    theme's preview.png when it has one (not for the Duplicate screen's live preview)."""
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
    cr = cairo.Context(surf)
    own = os.path.join(t.path, S.PREVIEW_FILE)
    if own_picture and os.path.exists(own):
        try:
            img = cairo.ImageSurface.create_from_png(own)
            cr.scale(W / img.get_width(), H / img.get_height())
            cr.set_source_surface(img, 0, 0)
            cr.paint()
            return surf
        except (OSError, cairo.Error):
            pass
    s, cache = W / 640, {}
    col = t.colors
    cr.set_source_rgba(*_rgb(t.wallpaper["color"]))
    cr.paint()
    if t.wallpaper["image"]:
        try:
            img = cairo.ImageSurface.create_from_png(t.wallpaper["image"])
            cr.save()
            cr.scale(W / 640, H / 480)
            cr.set_source_surface(img, (640 - img.get_width()) / 2, (448 - img.get_height()) / 2)
            cr.get_source().set_filter(cairo.FILTER_NEAREST)
            cr.paint()
            cr.restore()
        except (OSError, cairo.Error):
            pass
    cr.select_font_face(font, cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
    # a window: title bar and a terminal
    x0, y0, x1, y1 = 40 * s, 40 * s, 420 * s, 330 * s
    cr.set_source_rgba(*_rgb(col["terminal.bg"]))
    cr.rectangle(x0, y0, x1 - x0, y1 - y0)
    cr.fill()
    cr.set_source_rgba(*_rgb(col["titlebar.active_bg"]))
    cr.rectangle(x0, y0, x1 - x0, 28 * s)
    cr.fill()
    cr.set_source_rgba(*_rgb(col["titlebar.active_fg"]))
    cr.set_font_size(15 * s)
    ext = cr.text_extents("Terminal")
    cr.move_to((x0 + x1 - ext.width) / 2, y0 + 19 * s)
    cr.show_text("Terminal")
    for i, k in enumerate(("ansi1", "ansi2", "ansi3", "ansi4", "ansi5", "ansi6")):
        cr.set_source_rgba(*_rgb(col[f"terminal.{k}"]))
        cr.rectangle(x0 + (12 + i * 40) * s, y0 + 44 * s, 32 * s, 8 * s)
        cr.fill()
    # a notification
    nx, ny, nw, nh = 396 * s, 56 * s, 228 * s, 62 * s
    cr.set_source_rgba(*_rgb(col["notify.bg"]))
    cr.rectangle(nx, ny, nw, nh)
    cr.fill_preserve()
    cr.set_source_rgba(*_rgb(col["notify.border"]))
    cr.set_line_width(max(1, t.borders) * 1.5 * s)
    cr.stroke()
    cr.set_source_rgba(*_rgb(col["notify.fg"]))
    cr.set_font_size(15 * s)
    cr.move_to(nx + 10 * s, ny + 24 * s)
    cr.show_text("Charging")
    cr.select_font_face(font, cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
    cr.set_font_size(12 * s)
    cr.move_to(nx + 10 * s, ny + 46 * s)
    cr.show_text("Battery 54 %")
    # the taskbar, at its real size (32 px, every icon 1:1) so the pixel art stays sharp; the
    # icons are laid out from the right and stop before the Apps button on a narrow preview
    th, ty, bw = 32, H - 32, max(1, t.borders)
    cr.set_source_rgba(*_rgb(col["taskbar.bg"]))
    cr.rectangle(0, ty, W, th)
    cr.fill()
    cr.set_source_rgba(*_rgb(col["taskbar.border"]))
    cr.rectangle(0, ty, W, bw)
    cr.fill()
    cr.set_source_rgba(*_rgb(col["taskbar.apps_bg"]))
    cr.rectangle(0, ty + bw, 76, th - bw)
    cr.fill()
    apps = _image(t, "taskbar/apps", cache)
    if apps:
        _paste(cr, apps, 9, ty + 8, apps.get_height())
    cr.select_font_face(font, cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
    cr.set_font_size(12)
    cr.set_source_rgba(*_rgb(col["taskbar.apps_fg"]))
    cr.move_to(31, ty + 21)
    cr.show_text("Apps")
    x = W
    power = _image(t, "taskbar/power", cache)
    if power:
        x -= power.get_width() + 6
        _paste(cr, power, x, ty + (th - power.get_height()) // 2, power.get_height())
    cr.select_font_face(font, cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
    cr.set_font_size(12)
    cr.set_source_rgba(*_rgb(col["taskbar.fg"]))
    x -= cr.text_extents("12:00").x_advance + 10
    cr.move_to(x, ty + 21)
    cr.show_text("12:00")
    x -= 6
    for slot in ("taskbar/battery-4", "tray/nm-signal-100", "tray/blueman-tray", "taskbar/inputmode-desktop"):
        img = _image(t, slot, cache)
        if img is None:
            continue
        if x - img.get_width() < 76 + 4:
            break
        x -= img.get_width()
        _paste(cr, img, x, ty + (th - img.get_height()) // 2, img.get_height())
        x -= 8
    return surf
