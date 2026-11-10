"""The theme contract, schema 1: every field, colour and image slot a theme can set.

theme.json carries the data; images sit at fixed paths in the theme folder (IMAGE_SLOTS). This
module is the single source for the checks (theme.py), the renderer (render.py) and GUIDE.md
(guide.py), so they cannot disagree."""
from collections import OrderedDict

SCHEMA = 1
ID_RE = r"[a-z0-9][a-z0-9-]{0,39}\Z"        # theme id: folder name and file name
RESERVED_PREFIX = "handtop-"                # ids of the built-in themes
NAME_MAX = 32
BASES = ("dark", "light")

# ---- palette: the shared colours every other colour is derived from ---------------------------
PALETTE = OrderedDict([
    ("bg",          "background of the desktop's panels and windows"),
    ("surface",     "buttons and keys on the background"),
    ("surface_hi",  "a raised or active surface (active window, active title bar)"),
    ("border",      "lines around buttons and panels"),
    ("fg",          "text"),
    ("fg_dim",      "secondary text, inactive titles"),
    ("accent",      "accent fill (Apps button, highlighted button)"),
    ("accent_fg",   "accent used as text or outline on the background"),
    ("on_accent",   "text on an accent fill"),
    ("warn",        "warnings (battery low)"),
    ("error",       "errors (battery critical)"),
    ("brightness",  "the brightness bar and latched keys (amber in Handtop)"),
    ("success",     "positive state (connected, LED)"),
])

# ---- per-part colours ---------------------------------------------------------------------------
# key -> (rule, description, nullable). A theme may set any of them in "colors"; a missing one is
# derived from the theme's own palette by its rule:
#   "bg"                       a palette colour
#   "#rrggbb[aa]"              a fixed colour
#   ("mix", a, b, t)           a mixed with b (t = 0..1); a / b: palette names or fixed colours
#   ("alpha", a, x)            a with opacity x
# nullable: the theme may set null = leave the component's own default (labwc title-bar buttons).
M, A = "mix", "alpha"
COLORS = OrderedDict([
    # Waybar
    ("taskbar.bg",            ("bg", "taskbar background", False)),
    ("taskbar.fg",            ("fg", "taskbar text", False)),
    ("taskbar.border",        ((M, "bg", "fg", 0.15), "line above the taskbar", False)),
    ("taskbar.apps_bg",       ("accent", "Apps button", False)),
    ("taskbar.apps_fg",       ("on_accent", "Apps button text", False)),
    ("taskbar.active_bg",     ("surface_hi", "the active window's button", False)),
    ("taskbar.warn",          ("warn", "battery % when low", False)),
    ("taskbar.critical",      ("error", "battery % when critical", False)),
    # labwc
    ("titlebar.active_bg",    ("surface_hi", "active window title bar", False)),
    ("titlebar.inactive_bg",  ("surface", "inactive window title bar", False)),
    ("titlebar.active_fg",    ("fg", "active window title", False)),
    ("titlebar.inactive_fg",  ("fg_dim", "inactive window title", False)),
    ("titlebar.active_button",   ("fg", "title-bar buttons, active window (null: labwc's own)", True)),
    ("titlebar.inactive_button", ("fg_dim", "title-bar buttons, inactive window (null: labwc's own)", True)),
    # nwg-drawer
    ("drawer.bg",             ((A, "bg", 0.95), "app drawer background", False)),
    ("drawer.fg",             ("fg", "app names", False)),
    ("drawer.entry_bg",       ((A, "fg", 0.08), "search field", False)),
    ("drawer.hover_bg",       ((A, "fg", 0.1), "app under the pointer", False)),
    # wlogout
    ("powermenu.backdrop",    ((A, "bg", 0.92), "behind the buttons", False)),
    ("powermenu.button_bg",   ("surface", "button", False)),
    ("powermenu.button_border", ("border", "button border", False)),
    ("powermenu.fg",          ("fg", "button text", False)),
    ("powermenu.hover_bg",    ("accent", "highlighted button", False)),
    ("powermenu.hover_border", ("accent_fg", "highlighted button border", False)),
    ("powermenu.focus",       ("accent_fg", "keyboard focus outline", False)),
    # mako
    ("notify.bg",             ((A, "bg", 0.9), "notification background", False)),
    ("notify.fg",             ("fg", "notification text", False)),
    ("notify.border",         ("accent", "notification border", False)),
    # on-screen keyboard (input daemon)
    ("osk.bg",                ("bg", "keyboard background", False)),
    ("osk.key",               ("surface", "character key", False)),
    ("osk.border",            ("border", "character key border", False)),
    ("osk.fg",                ("fg", "character key label", False)),
    ("osk.spec",              ((M, "surface", "accent", 0.3), "special key (Tab, Shift, arrows)", False)),
    ("osk.spec_border",       ((M, "border", "accent", 0.5), "special key border", False)),
    ("osk.spec_fg",           ("accent_fg", "special key label", False)),
    ("osk.sel",               ("accent", "highlighted key", False)),
    ("osk.sel_border",        ("accent_fg", "highlighted key border", False)),
    ("osk.sel_fg",            ("on_accent", "highlighted key label", False)),
    ("osk.latch",             ((M, "surface", "brightness", 0.4), "latched Shift / Ctrl / Alt", False)),
    ("osk.latch_sel",         ((M, "surface", "brightness", 0.6), "latched and highlighted", False)),
    ("osk.latch_border",      ("brightness", "latched and highlighted border", False)),
    ("osk.badge",             ("accent_fg", "shoulder-button badge", False)),
    ("osk.hit",               ((M, "bg", "#000000", 0.4), "key just typed (press trace)", False)),
    ("osk.hit_border",        ("accent", "press trace border", False)),
    ("osk.hit_fg",            ("accent_fg", "press trace label", False)),
    # External Controller status screen (the drawn handheld)
    ("status.bg",             ("bg", "screen background", False)),
    ("status.body",           ("surface", "handheld body", False)),
    ("status.body_edge",      ("border", "body outline", False)),
    ("status.body_shade",     ((M, "surface", "#000000", 0.3), "body shading", False)),
    ("status.part",           ((M, "bg", "#000000", 0.3), "buttons and sticks", False)),
    ("status.part_edge",      ("border", "button outlines", False)),
    ("status.lit",            ("accent_fg", "pressed control", False)),
    ("status.lit_edge",       ((M, "accent_fg", "#ffffff", 0.5), "pressed control outline", False)),
    ("status.bezel",          ("#0d0d0f", "screen bezel", False)),
    ("status.bezel_edge",     ("border", "bezel outline", False)),
    ("status.screen",         ("#08090c", "the handheld's screen", False)),
    ("status.led",            ("success", "power LED", False)),
    ("status.cap",            ("surface", "stick caps and shoulder caps", False)),
    ("status.face_x",         ("#5c85ff", "X button", False)),
    ("status.face_y",         ("#59d16b", "Y button", False)),
    ("status.face_a",         ("#f24d4d", "A button", False)),
    ("status.face_b",         ("#fad940", "B button", False)),
    ("status.label",          ("fg", "button letters (null: drawn in the button colour)", True)),
    ("status.label_lit",      ("bg", "letters on a pressed button", False)),
    ("status.text",           ("#e8eaee", "text on the drawn screen (always dark)", False)),
    ("status.dim",            ("#949eb0", "secondary text on the drawn screen", False)),
    ("status.ok",             ("#8cd99e", "connected", False)),
    ("status.warn",           ("#ffcc66", "waiting / warning", False)),
    # Display app
    ("display.bg",            ("bg", "background", False)),
    ("display.card",          ("surface", "layout card", False)),
    ("display.card_hi",       ("surface_hi", "highlighted card", False)),
    ("display.border",        ("border", "card border", False)),
    ("display.accent",        ("accent_fg", "selection", False)),
    ("display.text",          ("fg", "text", False)),
    ("display.dim",           ("fg_dim", "secondary text", False)),
    ("display.body",          ("fg", "drawn handheld / monitor body", False)),
    ("display.off",           ("#0a0b0e", "a switched-off screen", False)),
    ("display.desk",          ("accent", "drawn desktop", False)),
    ("display.bar",           ((M, "bg", "#000000", 0.3), "drawn taskbar", False)),
    ("display.win",           ("fg", "drawn window", False)),
    ("display.sun",           ("#f0c73d", "drawn picture (mirror mode)", False)),
    ("display.track",         ("border", "slider track", False)),
    ("display.btn",           ("surface_hi", "button", False)),
    # terminal (foot)
    ("terminal.bg",           ("bg", "terminal background", False)),
    ("terminal.fg",           ("fg", "terminal text", False)),
    ("terminal.cursor",       ("accent_fg", "cursor block", False)),
    ("terminal.cursor_text",  ("bg", "text under the cursor", False)),
    ("terminal.selection_bg", ("accent", "selection", False)),
    ("terminal.selection_fg", ("on_accent", "selected text", False)),
    ("terminal.ansi0",        ("surface", "black", False)),
    ("terminal.ansi1",        ("error", "red", False)),
    ("terminal.ansi2",        ("success", "green", False)),
    ("terminal.ansi3",        ("brightness", "yellow", False)),
    ("terminal.ansi4",        ("accent_fg", "blue", False)),
    ("terminal.ansi5",        ("#c79bff", "magenta", False)),
    ("terminal.ansi6",        ("#6fd3d8", "cyan", False)),
    ("terminal.ansi7",        ("fg_dim", "white", False)),
    ("terminal.ansi8",        ((M, "fg_dim", "bg", 0.4), "bright black (comments)", False)),
    ("terminal.ansi9",        ((M, "error", "#ffffff", 0.2), "bright red", False)),
    ("terminal.ansi10",       ((M, "success", "#ffffff", 0.2), "bright green", False)),
    ("terminal.ansi11",       ((M, "brightness", "#ffffff", 0.2), "bright yellow", False)),
    ("terminal.ansi12",       ((M, "accent_fg", "#ffffff", 0.2), "bright blue", False)),
    ("terminal.ansi13",       ("#ddbfff", "bright magenta", False)),
    ("terminal.ansi14",       ("#9be6ea", "bright cyan", False)),
    ("terminal.ansi15",       ("fg", "bright white", False)),
    # volume / brightness bar (rg35xxh-osd)
    ("osd.bg",                ((A, "bg", 0.9), "bar background", False)),
    ("osd.volume_border",     ("accent", "volume bar border", False)),
    ("osd.volume_level",      ("accent_fg", "volume level", False)),
    ("osd.brightness_border", ((M, "brightness", "bg", 0.5), "brightness bar border", False)),
    ("osd.brightness_level",  ("brightness", "brightness level", False)),
    ("osd.text",              ("fg", "the number", False)),
])

# ---- other fields ------------------------------------------------------------------------------
WALLPAPER_MODES = ("center", "fill", "fit", "stretch", "tile")
STATUS_STYLES = ("solid", "hologram")
GTK_SCHEMES = ("prefer-dark", "default", "prefer-light")
CURSOR_SIZES = (16, 64)          # inclusive range
FONT_SCALES = (0.75, 1.5)

# ---- image slots -------------------------------------------------------------------------------
# Slot names are also their file names: slot "taskbar/battery-3" is icons/taskbar/battery-3.png.
# Each slot: (width, height, kind)
#   required     must exist in a complete theme; a missing one comes from the base Handtop theme
#   optional     a missing one comes from the base Handtop theme (Wi-Fi, decision 6)
#   generated    a missing one is made from its parent slot when the parent is the theme's own
#                (shake frames, small app icons); otherwise the base theme's is used
# SYSTEM_OK slots may be set to "system" in theme.json "icons": the package's own icon is used.
INPUT_MODES = ("desktop", "gamepad", "bt", "wired")
SHAKES = (-2, -1, 1, 2)
HANDTOP_APPS = ("theme", "external-controller", "display", "enable-ssh", "recenter-sticks")
DEFAULT_APPS = ("foot", "thunar", "mousepad", "chromium", "htop", "micro", "qpdfview", "xarchiver",
                "blueman")
APP_ICON_NAMES = {            # slot -> icon name looked up by GTK / labwc / Waybar
    "theme": "rg35xxh-theme", "external-controller": "rg35xxh-external-controller",
    "display": "rg35xxh-display", "enable-ssh": "rg35xxh-enable-ssh",
    "recenter-sticks": "rg35xxh-recenter-sticks",
    "foot": "foot", "thunar": "org.xfce.thunar", "mousepad": "org.xfce.mousepad",
    "chromium": "chromium", "htop": "htop", "micro": "micro", "qpdfview": "qpdfview",
    "xarchiver": "xarchiver", "blueman": "blueman",
}
WIFI = (["nm-device-wired", "nm-device-wired-secure", "nm-no-connection"]
        + [f"nm-signal-{n}{s}" for n in ("00", "25", "50", "75", "100") for s in ("", "-secure")]
        + [f"nm-stage0{st}-connecting{f:02d}" for st in (1, 2, 3) for f in range(1, 12)])
BLUETOOTH = ("blueman-tray", "blueman-active", "blueman-disabled")
POWER_ACTIONS = ("sleep", "reboot", "logout", "shutdown", "saver")
USB_TARGETS = ("pc", "console")


def _battery():
    for ch in ("", "-charging"):
        for low in ("", "-low"):
            for n in range(6):
                for sv in ("", "-saver"):
                    yield f"battery{ch}{low}-{n}{sv}"


def _slots():
    s = OrderedDict()
    s["taskbar/apps"] = (16, 16, "required")
    s["taskbar/power"] = (24, 24, "required")
    for m in INPUT_MODES:
        s[f"taskbar/inputmode-{m}"] = (23, 23, "required")
        for dx in SHAKES:
            s[f"taskbar/inputmode-{m}-shake{dx}"] = (23, 23, "generated")
    for b in _battery():
        s[f"taskbar/{b}"] = (20, 11, "required")
    for w in WIFI:
        s[f"tray/{w}"] = (23, 23, "optional")
    for b in BLUETOOTH:
        s[f"tray/{b}"] = (23, 23, "required")
    for a in HANDTOP_APPS + DEFAULT_APPS:
        s[f"apps/{a}"] = (56, 56, "required")
        s[f"apps/{a}@22"] = (22, 22, "generated")
        s[f"apps/{a}@20"] = (20, 20, "generated")
    for p in POWER_ACTIONS:
        s[f"power-menu/{p}"] = (72, 72, "required")
        s[f"power-menu/{p}-focus"] = (72, 72, "required")
    for t in USB_TARGETS:
        s[f"controller/usbtarget-{t}"] = (23, 23, "required")
    return s


IMAGE_SLOTS = _slots()
SYSTEM_OK = {k for k in IMAGE_SLOTS if k.startswith("tray/")
             or (k.startswith("apps/") and k.split("/")[1].split("@")[0] in DEFAULT_APPS)}


def parent(slot):
    """The slot a generated slot is made from (None for others)."""
    if IMAGE_SLOTS[slot][2] != "generated":
        return None
    if "@" in slot:
        return slot.split("@")[0]
    return slot.rsplit("-shake", 1)[0]


def slot_file(slot):
    return f"icons/{slot}.png"


WALLPAPER_FILE = "images/wallpaper.png"
PREVIEW_FILE = "preview.png"
PREVIEW_SIZE = (256, 192)
GUIDE_FILE = "GUIDE.md"
THEME_FILE = "theme.json"

# ---- app names (default apps only) ----------------------------------------------------------------
NAMEABLE = OrderedDict([          # names key -> .desktop file
    ("foot", "foot.desktop"), ("thunar", "thunar.desktop"), ("mousepad", "org.xfce.mousepad.desktop"),
    ("chromium", "chromium.desktop"), ("htop", "htop.desktop"), ("micro", "micro.desktop"),
    ("qpdfview", "qpdfview.desktop"), ("xarchiver", "xarchiver.desktop"),
])
APP_NAME_MAX = 24

# ---- import limits --------------------------------------------------------------------------------
MAX_ZIP_BYTES = 25 * 1024 * 1024          # the .handtop-theme file itself
MAX_TOTAL_BYTES = 20 * 1024 * 1024        # unpacked
MAX_FILES = 300
MAX_ICON_BYTES = 256 * 1024
MAX_WALLPAPER_BYTES = 4 * 1024 * 1024
MAX_WALLPAPER_SIZE = (3840, 2160)
MAX_JSON_BYTES = 64 * 1024
MAX_GUIDE_BYTES = 256 * 1024


def allowed_files():
    """Every path a theme folder may hold -> (max bytes, (w, h) or None for 'up to')."""
    files = {THEME_FILE: (MAX_JSON_BYTES, None), PREVIEW_FILE: (MAX_ICON_BYTES, PREVIEW_SIZE),
             WALLPAPER_FILE: (MAX_WALLPAPER_BYTES, None)}
    for slot, (w, h, _kind) in IMAGE_SLOTS.items():
        files[slot_file(slot)] = (MAX_ICON_BYTES, (w, h))
    return files
