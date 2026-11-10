"""The current theme's rendered files, for Handtop's apps (OSK, status screen, Display, ...).

Light on purpose (no other imports): apps call it at start or each time they draw. Everything
falls back to None / the stock folder when the theme has not been rendered yet, so callers keep
their own Handtop-dark defaults."""
import os

STATE = os.path.join(os.environ.get("XDG_STATE_HOME") or os.path.expanduser("~/.local/state"),
                     "rg35xxh", "theme")
STOCK_ICONS = "/usr/local/share/rg35xxh/icons"


def read_env(path=None):
    """theme.env as a dict ({} when missing). Values are single-quoted, ' written as '\\''."""
    out = {}
    try:
        with open(path or os.path.join(STATE, "theme.env"), encoding="utf-8") as f:
            for line in f:
                if "=" not in line or line.startswith("#"):
                    continue
                k, v = line.rstrip("\n").split("=", 1)
                if len(v) >= 2 and v[0] == v[-1] == "'":
                    v = v[1:-1].replace("'\\''", "'")
                out[k] = v
    except OSError:
        pass
    return out


def colors(part, env=None):
    """{key: '#rrggbb[aa]' or None} for one part ('osk', 'status', ...); {} when not rendered."""
    env = read_env() if env is None else env
    pre = f"COLOR_{part.upper()}_"
    return {k[len(pre):].lower(): (v or None) for k, v in env.items() if k.startswith(pre)}


def icons_dir():
    d = os.path.join(STATE, "icons")
    return d if os.path.isdir(d) else STOCK_ICONS


def rgba(c):
    """'#rrggbb[aa]' -> (r, g, b) floats for cairo, (r, g, b, a) only when not opaque, so
    set_source_rgb(*c) keeps working for opaque colours. None stays None."""
    if c is None:
        return None
    v = [int(c[i:i + 2], 16) / 255 for i in range(1, len(c), 2)]
    return tuple(v[:3]) if len(v) == 3 or v[3] == 1.0 else tuple(v)


def css(c):
    """'#rrggbb[aa]' -> GTK CSS colour (rgba() when not opaque: GTK 3 has no #rrggbbaa)."""
    v = [int(c[i:i + 2], 16) for i in range(1, len(c), 2)]
    if len(v) == 3 or v[3] == 255:
        return "#%02x%02x%02x" % tuple(v[:3])
    return f"rgba({v[0]}, {v[1]}, {v[2]}, {round(v[3] / 255, 2):g})"
