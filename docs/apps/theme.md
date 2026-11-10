# Theme

The **Theme** app (`rg35xxh-theme`) picks a theme and applies it at once. Built in: **Handtop (dark)** (default) and **Handtop (light)**. Since v0.4.0 every theme is a theme folder (the `.handtop-theme` format, below); the app is the only program that reads them.

## Usage

**Apps → Theme**, or from a terminal:

| Command | Does |
|---|---|
| `rg35xxh-theme ID` | apply a theme (`dark` / `light` still work: `handtop-dark` / `handtop-light`) |
| `rg35xxh-theme --get` / `--list` | the current theme's id / the installed themes |
| `rg35xxh-theme --import FILE [--replace]` | install a `.handtop-theme` (checked first; refused with the list of problems) |
| `rg35xxh-theme --export ID FILE` | write a theme as a `.handtop-theme` (with `GUIDE.md`) |
| `rg35xxh-theme --ensure` | session start (labwc autostart): render the current theme again if its files are missing or out of date |

The choice is the theme id in `~/.config/rg35xxh/theme` (v0.3.x's `dark` / `light` are read as the built-in themes and rewritten at the next log-in). Built-in themes are in `/usr/share/rg35xxh/themes/`, yours in `~/.local/share/rg35xxh/themes/`.

## How a theme reaches the desktop

Applying renders the theme into **`~/.local/state/rg35xxh/theme/`** (replaced as a whole) and points the session at it. Components read only these files; each falls back to Handtop dark's copy in `/etc` or `/usr/local/share/rg35xxh/icons` when nothing is rendered.

| Part | Reads | Applied |
|---|---|---|
| Taskbar (Waybar) | `waybar.css` via `rg35xxh-themed waybar` | Waybar is stopped; its restart loop (`rg35xxh-waybar`) starts it again |
| Taskbar icons (input mode, battery) | `icons/` (`rg35xxh-inputmode`, `rg35xxh-battery`) | the icon scripts are signalled |
| Notifications (mako) | `mako.conf` via `rg35xxh-themed mako` | restarted |
| Wallpaper (swaybg) | `WALLPAPER*` in `theme.env`, `wallpaper.png` | restarted |
| Window title bars (labwc) | the user theme `Handtop`: `~/.local/share/themes/Handtop/labwc/themerc` links to `labwc/themerc` (a file of your own there wins) | `labwc --reconfigure` |
| App and tray icons | the GTK icon theme **`Handtop-Current`** = `~/.local/share/icons/Handtop-Current` → `icon-theme/` (inherits the theme's GTK icon theme); labwc's window icons too (`<theme><icon>` in `rc.xml`). Handtop's apps name their icons (`Icon=rg35xxh-theme`, ...) | at once in new windows; Waybar's tray after its restart |
| App drawer (nwg-drawer) | `nwg-drawer.css`, copied to `~/.config/nwg-drawer/handtop.css` by `rg35xxh-drawer` | when it opens |
| Power menu (wlogout) | `wlogout.css` (`rg35xxh-power-menu`) | when it opens |
| On-screen keyboard | `COLOR_OSK_*` in `theme.env` | each time it is shown |
| External Controller (app and status screen) | `icons/`, `COLOR_STATUS_*` | when it opens |
| Display app | `COLOR_DISPLAY_*` | when it opens |
| GTK apps | gsettings `color-scheme`, `gtk-theme`, `icon-theme` (only when it was Handtop's or Adwaita: a theme you chose yourself is left alone), `cursor-theme`, `cursor-size`, `text-scaling-factor`; the same in `~/.config/gtk-3.0/settings.ini` | open apps may need a restart; the desktop cursor changes at the next log-in |

`theme.env` holds everything as `KEY='value'` lines (`THEME_ID`, `THEME_BASE`, `ICONS`, `WALLPAPER*`, every palette colour as `PALETTE_*`, every part colour as `COLOR_<PART>_<KEY>`); read it as data, never source it. Python apps use `handtop_theme.current` (`/usr/local/lib/rg35xxh-theme`).

`--ensure` compares a stamp (renderer version, theme folder, newest file in it) with `.stamp` in the rendered folder, so a normal log-in costs one quick check; after an update that changes the renderer (`RENDER_VERSION`) or an edited theme, it renders again before anything that reads the files starts. A missing or broken theme falls back to Handtop dark (logged in `~/.local/state/session/theme.log`).

Your own `~/.config/waybar/style.css` or `~/.config/mako/config` still wins over every theme.

Not themed yet: the terminal (foot; one dark terminal) and the volume / brightness bar (`rg35xxh-osd`): step 6 of v0.4.0.

## History

- v0.2.0: dark / light, one file per component and theme (`style-light.css`, `config-light`, the `Handtop-Light` labwc and icon themes, `-light` icons), switched by the app.
- v0.4.0: themes as data (`src/theme/`). The v0.3.9 configs and palettes are kept in `src/theme/tests/reference/` and the built-in themes are tested to render the same rules and colours.

## Theme files (v0.4.0)

The next Theme app reads themes as `.handtop-theme` files (a zip: `theme.json` + PNG images at fixed paths) that cover every static visual part. The code is `src/theme/handtop_theme/` (installed to `/usr/local/lib/rg35xxh-theme/` by `build/07d-theme.sh`, which also assembles the built-in themes).

| Module | Does |
|---|---|
| `schema.py` | The contract, schema 1: 13 palette colours, 111 per-part colours each with a rule that derives it from the palette, 173 image slots (fixed name, size, required / optional / generated, which may be `"system"`), renameable default apps, import limits |
| `theme.py` | Reads and checks `theme.json`, checks every image, and fills in what a theme leaves out: palette colours from its base theme (`handtop-dark` / `handtop-light`), part colours from its own palette, images from the base (or made from the theme's own: shake frames, 22 / 20 px app icons); a wallpaper image is never inherited |
| `pngcheck.py` | PNG check without a decoder (chunk CRCs, IHDR, image data inflated with a hard limit), then a full decode with GdkPixbuf |
| `imgops.py` | GdkPixbuf: smooth downscale (HYPER) for small app icons, the sideways shift for shake frames. No Pillow on the device |
| `package.py` | Import (only the contract's paths are unpacked; no `..`, absolute paths, links or encrypted entries; sizes checked on the bytes read; the theme is checked in a temporary folder and only then moved into place), export (adds `GUIDE.md`), duplicate, list, delete |
| `current.py` | For apps: the rendered `theme.env`, colours per part, the icon folder (no other imports) |
| `render.py` | Writes `theme.env`, Waybar / mako / labwc / wlogout / nwg-drawer / foot configs, the flat `icons/` folder and the `Handtop-Current` GTK icon theme into one folder, swapped in whole |
| `guide.py` | `GUIDE.md`, generated from the schema |
| `builtin.py` | Assembles the built-in `handtop-dark` / `handtop-light` themes from `src/theme/themes/<id>/theme.json` and the generated pixel art in `overlay/` |

Decisions (2026-11-10): rendered files go to `~/.local/state/rg35xxh/theme/` (a cache may be cleared), `theme.env` included (one generated set in one place); `~/.config/rg35xxh/theme` keeps only the choice (the theme id); part colours a theme leaves out are derived from its own palette, so a palette-only theme still looks consistent; input-mode shake frames may be drawn by the theme, otherwise the whole icon is shifted; Wi-Fi tray icons are optional in a theme, Bluetooth tray icons are a slot.

Tests: `python3 -m pytest -q src/theme/tests` (also in `tools/ci-checks.sh`). `test_builtin_look.py` checks that the built-in themes render to the same rules and colours as today's configs and palettes, with each intended difference listed.
