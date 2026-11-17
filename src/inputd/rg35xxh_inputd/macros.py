"""Macros: a button runs a list of steps (pure logic, unit-tested; the daemon plays and records them).

A macro is a text file, ~/.config/rg35xxh/controls/macros/<name>.macro, one step per line ('#' starts a
comment), shared by every profile. A binding "macro:<name>" plays it; pressing it again while it runs
stops it. Steps:

  key KEY_X            tap a key                   down KEY_X / up KEY_X   hold / let go of a key
  combo KEY_A+KEY_B    tap keys together           text <anything>         type it (US layout)
  click left           tap a mouse button          press left / release left
  wait 0.25            pause (seconds, 0.01-10)    move 40 -12             move the pointer by x, y
  scroll -120 0        wheel: vertical, horizontal (120 = one notch; + = up / right)
  launch <app id>      start an app                do <action>             copy, paste, osk_toggle,
                                                                           power_menu, volume_up ...
Limits keep a bad file harmless: at most MAX_STEPS steps and MAX_WAIT seconds of waiting in all;
anything held is let go at the end, when stopped, and on a switch to gamepad mode.
"""
import os
import re

MAX_STEPS = 1000
MAX_WAIT = 300.0
MAX_BYTES = 65536
NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 _.-]{0,39}$")
_KEY = re.compile(r"^KEY_[A-Z0-9_]+$")
BUTTONS = ("left", "right", "middle", "back", "forward")
DO = ("copy", "paste", "osk_toggle", "power_menu", "volume_up", "volume_down", "brightness_up", "brightness_down")

# Typing text on a US keyboard: char -> (shift?, key)
_SHIFTED = dict(zip('~!@#$%^&*()_+{}|:"<>?', "`1234567890-=[]\\;',./"))
_PLAIN = {"`": "GRAVE", "-": "MINUS", "=": "EQUAL", "[": "LEFTBRACE", "]": "RIGHTBRACE", "\\": "BACKSLASH",
          ";": "SEMICOLON", "'": "APOSTROPHE", ",": "COMMA", ".": "DOT", "/": "SLASH", " ": "SPACE",
          "\t": "TAB", "\n": "ENTER"}


def char_key(ch):
    """(modifier keys, key) to type ch, or None if a US keyboard has no key for it."""
    if "a" <= ch <= "z" or "0" <= ch <= "9":
        return [], "KEY_" + ch.upper()
    if "A" <= ch <= "Z":
        return ["KEY_LEFTSHIFT"], "KEY_" + ch
    if ch in _PLAIN:
        return [], "KEY_" + _PLAIN[ch]
    if ch in _SHIFTED:
        base = _SHIFTED[ch]
        return ["KEY_LEFTSHIFT"], ("KEY_" + base if base.isdigit() else "KEY_" + _PLAIN[base])
    return None


def macros_dir():
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.join(os.path.expanduser("~"), ".config")
    return os.path.join(base, "rg35xxh", "controls", "macros")


def path(name):
    return os.path.join(macros_dir(), name + ".macro")


def parse(text, known_key=lambda k: True):
    """(steps, problems): steps are tuples like ("key", "KEY_A"), ("wait", 0.25), ("move", 4, -2);
    a bad line is left out and named in problems."""
    steps, problems, waited = [], [], 0.0
    for n, raw in enumerate(text.splitlines(), 1):
        line = raw.split("#", 1)[0].strip() if not raw.lstrip().startswith("text ") else raw.strip()
        if not line:
            continue
        word, _, rest = line.partition(" ")
        step = None
        try:
            if word in ("key", "down", "up") and _KEY.match(rest) and known_key(rest):
                step = (word, rest)
            elif word == "combo" and 2 <= len(rest.split("+")) <= 4 and all(
                    _KEY.match(k) and known_key(k) for k in rest.split("+")):
                step = ("combo", rest)
            elif word in ("click", "press", "release") and rest in BUTTONS:
                step = (word, rest)
            elif word == "text" and rest and len(rest) <= 500:
                step = ("text", rest)
            elif word == "wait":
                v = float(rest)
                if 0.01 <= v <= 10:
                    step = ("wait", round(v, 3))
            elif word == "move":
                x, y = (int(v) for v in rest.split())
                if abs(x) <= 4000 and abs(y) <= 4000:
                    step = ("move", x, y)
            elif word == "scroll":
                v, h = (int(v) for v in rest.split())
                if abs(v) <= 12000 and abs(h) <= 12000:
                    step = ("scroll", v, h)
            elif word == "launch" and re.match(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,99}$", rest):
                step = ("launch", rest)
            elif word == "do" and rest in DO:
                step = ("do", rest)
        except ValueError:
            step = None
        if step is None:
            problems.append(f"line {n}: {raw.strip()[:60]!r} not understood (skipped)")
            continue
        if step[0] == "wait":
            if waited + step[1] > MAX_WAIT:
                problems.append(f"line {n}: more than {MAX_WAIT:.0f} s of waiting in all (rest skipped)")
                break
            waited += step[1]
        steps.append(step)
        if len(steps) >= MAX_STEPS:
            problems.append(f"more than {MAX_STEPS} steps (rest skipped)")
            break
    return steps, problems


def format_steps(steps, title=None):
    out = [f"# Handtop macro{': ' + title if title else ''} (one step per line; see Controls > Advanced > Macros)"]
    for st in steps:
        out.append(" ".join(str(v) for v in st))
    return "\n".join(out) + "\n"


def load(name, known_key=lambda k: True):
    with open(path(name), encoding="utf-8") as f:
        text = f.read(MAX_BYTES + 1)
    if len(text) > MAX_BYTES:
        return [], [f"{name}: file too large"]
    return parse(text, known_key)


def save(name, steps):
    if not NAME_RE.match(name):
        raise ValueError(f"not a macro name: {name!r}")
    os.makedirs(macros_dir(), exist_ok=True)
    tmp = path(name) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(format_steps(steps, name))
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path(name))


def names():
    try:
        return sorted((f[:-6] for f in os.listdir(macros_dir()) if f.endswith(".macro") and NAME_RE.match(f[:-6])),
                      key=str.lower)
    except OSError:
        return []


class Recorder:
    """Turns what the daemon sends while recording into steps: waits between events (paused time
    left out; none at all with timing=False: the steps then run back to back), pointer motion merged
    into one move per event or 0.1 s, a key or button pressed and let go with nothing in between
    becomes one tap."""
    def __init__(self, pointer, timing=True):
        self.pointer = pointer
        self.timing = timing
        self.steps = []
        self.last = None            # time of the last recorded event (None: none yet or just resumed)
        self.mx = self.my = 0       # pointer motion not written yet
        self.mt = None              # when that motion started
        self.st = 0.0               # when the last scroll step started

    def resume(self, t):
        self.last = t if self.steps else None

    def _gap(self, t):
        if self.timing and self.last is not None and t - self.last >= 0.03:
            self.steps.append(("wait", round(min(t - self.last, 10.0), 2)))
        self.last = t

    def _flush_move(self):
        if self.mx or self.my:
            self.steps.append(("move", self.mx, self.my))
        self.mx = self.my = 0
        self.mt = None

    def event(self, t, step):
        """step: ("down"/"up", KEY), ("press"/"release", button), ("scroll", v, h), ("launch", id),
        ("do", action), ("move", dx, dy)."""
        if len(self.steps) >= MAX_STEPS - 2:
            return False                                   # full: the daemon stops recording
        if step[0] == "move":
            if not self.pointer:
                return True
            if self.mt is None:
                self._flush_move()
                self._gap(t)
                self.mt = t
            self.mx += step[1]
            self.my += step[2]
            self.last = t                                  # a wait counts from the last motion
            if t - self.mt >= 0.1:
                self._flush_move()
            return True
        self._flush_move()
        self._gap(t)
        prev = self.steps[-1] if self.steps else None
        if prev and ((prev[0], step[0]) in (("down", "up"), ("press", "release"))) and prev[1] == step[1]:
            self.steps[-1] = ("key" if step[0] == "up" else "click", step[1])
        elif prev and prev[0] == "scroll" and step[0] == "scroll" and t - self.st < 0.1:
            self.steps[-1] = ("scroll", max(-12000, min(12000, prev[1] + step[1])),
                              max(-12000, min(12000, prev[2] + step[2])))   # one step per 0.1 s
        else:
            self.steps.append(step)
            self.st = t
        return True

    def finish(self):
        self._flush_move()
        while self.steps and self.steps[-1][0] == "wait":
            self.steps.pop()
        return self.steps
