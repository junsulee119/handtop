"""The built-in Handtop themes (handtop-dark, handtop-light) assembled from the repo.

Their theme.json files are in src/theme/themes/<id>/; their images are the generated pixel art
already in overlay/ (tools/icons/), copied into the theme slots here. Used by the image build
(build/07d-theme.sh) and the tests."""
import os
import shutil

from . import schema as S

IDS = ("handtop-dark", "handtop-light")
_I = "overlay/usr/local/share/rg35xxh/icons"
_HI = "overlay/usr/local/share/icons/hicolor"
_HL = "overlay/usr/local/share/icons/Handtop-Light"
_APP_FILES = {"theme": "app-theme", "external-controller": "app-external-controller",
              "display": "app-display", "enable-ssh": "app-ssh", "recenter-sticks": "app-recenter"}


def sources(repo, light):
    """slot -> source file (absolute) for one built-in theme; plus the wallpaper."""
    sfx = "-light" if light else ""
    j = lambda *p: os.path.join(repo, *p)      # noqa: E731
    out = {}
    out["taskbar/apps"] = j(_I, "panel-apps.png")
    out["taskbar/power"] = j(_I, f"panel-power{sfx}.png")
    for slot in S.IMAGE_SLOTS:
        group, name = slot.split("/")
        if group == "taskbar" and name.startswith(("inputmode-", "battery")):
            if "-shake" in name:
                mode, dx = name.split("-shake")
                out[slot] = j(_I, f"{mode}{sfx}-shake{dx}.png")
            else:
                out[slot] = j(_I, f"{name}{sfx}.png")
        elif group == "tray" and name.startswith("nm-"):
            out[slot] = j(_HL if light else _HI, "24x24", "apps", f"{name}.png")
        elif group == "tray":
            out[slot] = j(_HI, "24x24", "status", f"{name}.png")
        elif group == "power-menu":
            act, focus = (name[:-6], True) if name.endswith("-focus") else (name, False)
            out[slot] = j(_I, f"power-{act}{sfx}.png" if light or not focus else f"power-{act}-focus.png")
        elif group == "controller":
            out[slot] = j(_I, f"{name}{sfx}.png")
        elif group == "apps":
            app, _, small = name.partition("@")
            if app in _APP_FILES:
                if not small:
                    out[slot] = j(_I, f"{_APP_FILES[app]}{sfx}.png")
                continue                                   # @22 / @20: generated
            icon = S.APP_ICON_NAMES[app]
            if not small:
                f = j(_HL, "scalable", "apps", f"{icon}.png")
                out[slot] = f if light and os.path.exists(f) else j(_HI, "scalable", "apps", f"{icon}.png")
            elif small == "22" and os.path.exists(j(_HI, "22x22", "apps", f"{icon}.png")):
                out[slot] = j(_HI, "22x22", "apps", f"{icon}.png")   # today's 22 px copy (both themes)
    out[S.WALLPAPER_FILE] = j("overlay/usr/local/share/rg35xxh", f"wallpaper{sfx or '-dark'}.png")
    return out


def assemble(repo, dest):
    """Write handtop-dark and handtop-light, unpacked, into dest/<id>/."""
    for tid in IDS:
        out = os.path.join(dest, tid)
        if os.path.exists(out):
            shutil.rmtree(out)
        os.makedirs(out)
        shutil.copyfile(os.path.join(repo, "src", "theme", "themes", tid, S.THEME_FILE),
                        os.path.join(out, S.THEME_FILE))
        for slot, src in sources(repo, tid.endswith("light")).items():
            rel = slot if slot == S.WALLPAPER_FILE else S.slot_file(slot)
            os.makedirs(os.path.dirname(os.path.join(out, rel)), exist_ok=True)
            shutil.copyfile(src, os.path.join(out, rel))
    return [os.path.join(dest, t) for t in IDS]
