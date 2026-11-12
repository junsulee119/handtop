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
    a("- Static looks only: colours, images, fonts, pointer, wallpaper, app names of the default apps, "
      "and optional CSS added to a few parts.")
    a("- Never behaviour, animation timing, scripts or config text: Handtop writes every config itself.")
    a("- Not in themes: the boot screen and boot logo, Battery saver (a theme only draws its icons), "
      "Moonlight and Tailscale's own logos.\n")
    a("## theme.json\n")
    a("| Field | Value |\n|---|---|")
    a(f"| `schema` | `{S.SCHEMA}` |")
    a("| `id` | 1-40 characters `a-z`, `0-9`, `-`; also the folder name. `handtop-…` is kept for the built-in themes |")
    a(f"| `name` | shown in the Theme app, 1-{S.NAME_MAX} characters |")
    a("| `base` | `dark` or `light`: the built-in Handtop theme that fills in anything left out, and what apps that only know dark / light use |")
    a("| `author`, `description` | optional, one line each (anything else is ignored) |")
    a("| `version` | optional whole number from 1; raise it whenever you share a changed theme |")
    a("| `license` | optional, one line: the licence of the theme and of its fonts and images, e.g. `CC BY 4.0; fonts OFL 1.1` |")
    a("| `tags` | optional, up to 8 short words (`a-z`, `0-9`, `-`) to find the theme by, e.g. `[\"pixel\", \"retro\"]` |")
    a("| `palette` | the shared colours (below) |")
    a("| `colors` | optional per-part colours (below), `\"<part>.<key>\": \"#rrggbb\"` |")
    a(f"| `wallpaper` | `color` (an alpha part is dropped: the wallpaper is opaque), `image` (`\"{S.WALLPAPER_FILE}\"` or `null`), `mode` ({', '.join(S.WALLPAPER_MODES)}) |")
    a(f"| `gtk` | `color_scheme` ({', '.join(S.GTK_SCHEMES)}), `theme`, `icon_theme`: installed names |")
    a(f"| `cursor` | `theme` (installed; ignored when the theme draws its own pointer), `size` {S.CURSOR_SIZES[0]}-{S.CURSOR_SIZES[1]}, "
      f"`hotspots` (`\"<shape>\": [x, y]` on the {S.CURSOR_ART} px drawing). Applies at the next log-in |")
    a(f"| `fonts` | `ui`, `mono` (installed font names, or the family of the theme's own font file), `scale` {S.FONT_SCALES[0]}-{S.FONT_SCALES[1]} (GTK apps, taskbar, notifications, app drawer; the power menu's large labels and window titles stay as they are) |")
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
    a("## Pointer (optional)\n")
    a(f"Draw any of these at {S.CURSOR_ART}×{S.CURSOR_ART} (twice the 24 px size; pixel art drawn at 2× "
      "stays crisp). Handtop makes an Xcursor set from them with a 24 px and a 48 px size; shapes you "
      "leave out are Handtop's own. The hotspot is the pixel that points (default in brackets).\n")
    a("| File | Used for | Default hotspot |\n|---|---|---|")
    for shape, (names, hs) in S.CURSOR_SHAPES.items():
        a(f"| `{S.cursor_file(shape)}` | {', '.join(names)} | {list(hs)} |")
    a("\n## Fonts (optional)\n")
    a(f"`fonts/ui.ttf` (or `.otf`) for text and `fonts/mono.ttf` for the terminal, at most "
      f"{S.MAX_FONT_BYTES >> 20} MB each, one font per file (no collections; a variable font is fine). Set `fonts.ui` / "
      "`fonts.mono` to the font's family name; the import checks it with fontconfig. Put the font "
      f"licence in `{S.FONT_LICENSE_FILE}`: only share fonts whose licence allows it (for example "
      "the SIL Open Font License). Applying the theme installs its fonts for your user; the next "
      "theme's replace them.\n")
    a("## CSS (optional)\n")
    a("GTK CSS added after Handtop's own rules for a part, so yours wins. Plain UTF-8 text, at most "
      f"{S.MAX_CSS_BYTES >> 10} KB; `@import`, `url()` and backslash escapes are refused. Keep the "
      "taskbar 32 px high and the power menu's three columns within 640 px. GTK reads "
      "`css/apps.css` in every GTK 3 program, the taskbar, app drawer and power menu included, "
      "and it wins over their own rules: test those too.\n")
    a("| File | Added to |\n|---|---|")
    for part, d in S.CSS_PARTS.items():
        a(f"| `{S.css_file(part)}` | {d} |")
    a("")
    a("## Drawing tips (mistakes found on the device)\n")
    a("Handtop places every image by its full size, never by what is drawn in it, so the drawing "
      "itself must be centred:\n")
    a("- **Centre the drawing inside its image**, both ways. A drawing that starts at the top or "
      "the left edge of a 23×23 icon sits visibly high or to one side on the taskbar (Retro's first "
      "mouse icon sat 4 px high; app icons were up to 8 px off in the app drawer). Check the "
      "bounding box of the drawn pixels: its middle should be the image's middle.")
    a("- **Match the width parity.** A shape centred in an odd-sized image (23, 11) needs an odd "
      "width; in an even-sized one (16, 24, 56, 72) an even width. A 2 px stick in a ring drawn "
      "around a single centre pixel leans half a pixel to one side: centre the ring on the line "
      "between the two stick columns. A 15 px drawing in a 16 px image cannot be centred: draw it "
      "16 px wide.")
    a("- **Icons that change keep one baseline.** Signal bars, battery levels and animation "
      "frames: centre the full set (all bars, the whole battery), not what happens to be lit, so "
      "the icon does not jump. Put badges (padlock, error mark, dots) in a corner, outside that "
      "centring.")
    a("- **Pixel art at 2×** (app icons 56 px, power menu 72 px, pointer 48 px): draw at half size "
      "and double every pixel, so lines stay 2 px and crisp. The 22 / 20 px app icons and the "
      "pointer's 24 px size are made from these by smooth scaling.")
    a("- **Check it on the taskbar**, not only in a picture viewer: take a screenshot and compare "
      "the vertical middle of every icon and button. Handtop's own icons sit 1 px above the "
      "taskbar's middle; buttons you add with `css/taskbar.css` should share that line (Retro: "
      "2 px margin above, 3 px below).")
    a("- **`css/apps.css` reaches the taskbar, app drawer and power menu too** (they are GTK 3 "
      "programs) and overrides their rules: a broad rule such as `list, .view, row { background: "
      "white }` turned Retro's app drawer white. Keep its selectors narrow and look at all three.")
    a("- **Pointer hotspots** are in 48 px units: double the pixel you mean in 24 px art. The "
      "pointer changes at the next log-in.\n")
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
