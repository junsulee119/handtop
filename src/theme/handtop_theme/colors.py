"""Colours: '#rrggbb' or '#rrggbbaa' strings, parsed to (r, g, b, a) with 0-255 ints."""
import re

_HEX = re.compile(r"#[0-9a-fA-F]{6}([0-9a-fA-F]{2})?\Z")


def valid(s):
    return isinstance(s, str) and bool(_HEX.match(s))


def parse(s):
    if not valid(s):
        raise ValueError(f"not a colour: {s!r} (use #rrggbb or #rrggbbaa)")
    v = [int(s[i:i + 2], 16) for i in range(1, len(s), 2)]
    return tuple(v) if len(v) == 4 else (*v, 255)


def fmt(c):
    r, g, b, a = (max(0, min(255, round(x))) for x in c)
    return f"#{r:02x}{g:02x}{b:02x}" + ("" if a == 255 else f"{a:02x}")


def mix(a, b, t):
    """t = 0 gives a, 1 gives b (alpha mixed too)."""
    pa, pb = parse(a), parse(b)
    return fmt([x + (y - x) * t for x, y in zip(pa, pb)])


def with_alpha(c, alpha):
    r, g, b, _ = parse(c)
    return fmt((r, g, b, alpha * 255))


def rgb(c):
    """'#rrggbb' without alpha (for configs that take none)."""
    return fmt((*parse(c)[:3], 255))


def css(c):
    """CSS form: #rrggbb, or rgba(r, g, b, 0.xx) when not opaque."""
    r, g, b, a = parse(c)
    if a == 255:
        return f"#{r:02x}{g:02x}{b:02x}"
    return f"rgba({r}, {g}, {b}, {round(a / 255, 2):g})"


def floats(c):
    """(r, g, b, a) as 0-1 floats, for cairo."""
    return tuple(x / 255 for x in parse(c))
