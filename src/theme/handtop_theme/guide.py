"""GUIDE.md: how to edit a theme, written into every exported or duplicated theme. Generated
from schema.py, so it always matches the Handtop version that wrote it."""
from . import schema as S


def _rule(rule):
    if isinstance(rule, str):
        return f"`{rule}`" if not rule.startswith("#") else f"`{rule}` (fixed)"
    if rule[0] == "mix":
        return f"`{rule[1]}` mixed {round(rule[3] * 100)} % with `{rule[2]}`"
    return f"`{rule[1]}` at {round(rule[2] * 100)} % opacity"


def generate():
    L = []
    a = L.append
    a(f"# Editing this Handtop theme (schema {S.SCHEMA})\n")
    a("This file is written by Handtop's Theme app and ignored when the theme is imported. It lists "
      "everything a theme can change. Edit `theme.json` and the PNG files, zip the folder (or its "
      "contents), rename it to `<name>.handtop-theme`, then **Apps → Theme → Import** and **Apply** "
      "on the handheld. The Theme app lists every problem it finds.\n")
    a("## What a theme is\n")
    a("- Static looks only: colours, images, fonts, cursor, wallpaper, app names of the default apps.")
    a("- Never behaviour, animation timing, scripts or CSS / config text: Handtop writes every config itself.")
    a("- Not in themes: the boot screen and boot logo, Battery saver (a theme only draws its icons), "
      "Moonlight and Tailscale's own logos.\n")
    a("## theme.json\n")
    a("| Field | Value |\n|---|---|")
    a(f"| `schema` | `{S.SCHEMA}` |")
    a("| `id` | 1-40 characters `a-z`, `0-9`, `-`; also the folder name. `handtop-…` is kept for the built-in themes |")
    a(f"| `name` | shown in the Theme app, 1-{S.NAME_MAX} characters |")
    a("| `base` | `dark` or `light`: the built-in Handtop theme that fills in anything left out, and what apps that only know dark / light use |")
    a("| `author`, `description` | optional, one line each |")
    a("| `palette` | the shared colours (below) |")
    a("| `colors` | optional per-part colours (below), `\"<part>.<key>\": \"#rrggbb\"` |")
    a(f"| `wallpaper` | `color`, `image` (`\"{S.WALLPAPER_FILE}\"` or `null`), `mode` ({', '.join(S.WALLPAPER_MODES)}) |")
    a(f"| `status_screen` | `style`: {' or '.join(S.STATUS_STYLES)} (External Controller's drawn handheld) |")
    a(f"| `gtk` | `color_scheme` ({', '.join(S.GTK_SCHEMES)}), `theme`, `icon_theme`: installed names |")
    a(f"| `cursor` | `theme` (installed), `size` {S.CURSOR_SIZES[0]}-{S.CURSOR_SIZES[1]} (applies at the next log-in) |")
    a(f"| `fonts` | `ui`, `mono` (installed font names), `scale` {S.FONT_SCALES[0]}-{S.FONT_SCALES[1]} (GTK apps, taskbar, notifications, app drawer; the power menu's large labels and window titles stay as they are) |")
    a(f"| `borders` | line width {S.BORDERS[0]}-{S.BORDERS[1]} (taskbar line, notification and power-menu borders, keyboard keys; 1 = Handtop's) |")
    a("| `icons` | `\"<slot>\": \"system\"` to use the package's own icon (only slots marked *system ok*) |")
    a(f"| `names` | `\"<app>\": \"Name\"` for default apps, 1-{S.APP_NAME_MAX} characters, or `\"system\"` |\n")
    a("Colours are `#rrggbb`, or `#rrggbbaa` with opacity. Anything left out is filled in: palette "
      "colours from the base theme, part colours from your own palette (rules below), images from the "
      "base theme (or made from your own image, where noted). The wallpaper image is never taken from "
      "the base theme.\n")
    a("### Palette\n")
    a("| Key | Used for |\n|---|---|")
    for k, d in S.PALETTE.items():
        a(f"| `{k}` | {d} |")
    a("\n### Part colours (`colors`)\n")
    a("| Key | Used for | When left out |\n|---|---|---|")
    for k, (rule, d, nullable) in S.COLORS.items():
        a(f"| `{k}` | {d}{' (may be `null`)' if nullable else ''} | {_rule(rule)} |")
    a("\n## Images\n")
    a("PNG only, exact pixel size, at the path shown (relative to the theme folder). Pixel art is "
      "shown at its own size, never scaled (except where noted).\n")
    a("| File | Size | If missing |\n|---|---|---|")
    for slot, (w, h, kind) in S.IMAGE_SLOTS.items():
        if kind == "generated":
            miss = f"made from `{S.slot_file(S.parent(slot))}`" + (
                " (smooth downscale; draw it for crisp pixel art)" if "@" in slot
                else " (the whole icon shifted sideways)")
            miss += " if that one is yours, else the base theme's"
        else:
            miss = "base theme's"
        sysok = ", *system ok*" if slot in S.SYSTEM_OK else ""
        a(f"| `{S.slot_file(slot)}` | {w}×{h} | {miss}{sysok} |")
    a(f"| `{S.WALLPAPER_FILE}` | up to {S.MAX_WALLPAPER_SIZE[0]}×{S.MAX_WALLPAPER_SIZE[1]}, "
      f"{S.MAX_WALLPAPER_BYTES >> 20} MB | no image (colour only) |")
    a(f"| `{S.PREVIEW_FILE}` | {S.PREVIEW_SIZE[0]}×{S.PREVIEW_SIZE[1]} | drawn by the Theme app |\n")
    a("Input-mode icons shake on a mode change: `…-shake-2`, `-shake-1`, `-shake1`, `-shake2` are "
      "the frames (the drawing moved that many pixels). Handtop moves only the drawing inside its "
      "glass frame; without your own frames the whole icon moves.\n")
    a("## App names\n")
    a("Default apps only: " + ", ".join(f"`{k}`" for k in S.NAMEABLE) + ". Handtop's own apps keep "
      "their names.\n")
    a("## Limits\n")
    a(f"- The theme file: at most {S.MAX_ZIP_BYTES >> 20} MB; unpacked {S.MAX_TOTAL_BYTES >> 20} MB, "
      f"{S.MAX_FILES} files; each icon {S.MAX_ICON_BYTES >> 10} KB.")
    a("- Only the files listed here are read; anything else is ignored. No links, no paths outside "
      "the theme folder.")
    a("- Any error refuses the whole theme and the current one stays.\n")
    a("## Example\n")
    a("```json\n{\n  \"schema\": 1,\n  \"id\": \"my-blue\",\n  \"name\": \"My Blue\",\n  \"base\": \"dark\",\n"
      "  \"palette\": { \"bg\": \"#10243f\", \"accent\": \"#2f6fd6\", \"accent_fg\": \"#9cc3ff\" },\n"
      "  \"colors\": { \"taskbar.border\": \"#2f6fd6\" },\n"
      "  \"wallpaper\": { \"color\": \"#0b1a2e\", \"image\": null },\n"
      "  \"names\": { \"thunar\": \"Files\" }\n}\n```")
    return "\n".join(L) + "\n"
