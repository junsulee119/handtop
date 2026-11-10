# Theme

The **Theme** app (`rg35xxh-theme`, helper `rg35xxh-themed`): dark (default) or light, switched live.

## Usage

**Apps → Theme** (or `rg35xxh-theme dark|light`, `rg35xxh-theme --get`): dark (default) or light. The choice is one file, `~/.config/rg35xxh/theme`, read by every themed part; a switch applies live.

| Part | How it follows the theme |
|---|---|
| Waybar | `rg35xxh-themed waybar` (started and restarted by `rg35xxh-waybar`; a theme switch only stops Waybar) adds `-s /etc/xdg/waybar/style-light.css` (imports `style.css`, overrides the colours) |
| Taskbar icons | input mode and battery scripts pick the `-light` PNGs; Wi-Fi tray icons come from the `Handtop-Light` icon theme, which the Theme app makes the GTK icon theme (gsettings `icon-theme`; Adwaita for dark; a theme the user chose is left alone) |
| Wallpaper | `rg35xxh-themed swaybg`: the Handtop logo + wordmark (`wallpaper-dark.png` / `wallpaper-light.png`, from `tools/icons/gen_logo.py`) centred on `#1e2430` / `#dfe4ec` |
| Notifications | `rg35xxh-themed mako`: `/etc/xdg/mako/config` / `config-light` |
| Window title bars | labwc theme `Handtop` (`/usr/share/themes/Handtop/labwc/themerc`). Light: the Theme app links `/usr/share/themes/Handtop-Light/labwc/themerc` as `~/.local/share/themes/Handtop/labwc/themerc` (user themes win) and runs `labwc --reconfigure`. `themerc-override` only keeps the title-bar padding |
| App drawer | `rg35xxh-drawer` copies `/etc/xdg/nwg-drawer/handtop-<theme>.css` into `~/.config/nwg-drawer` (nwg-drawer's `-s` only takes a name there) |
| Handtop app icons | light: per-user copies of their `.desktop` files in `~/.local/share/applications` with the `-light` icon (marked `X-Handtop-Theme=light`, removed again for dark) |
| Power menu | `rg35xxh-power-menu`: `/etc/wlogout/style.css` / `style-light.css` (buttons stay mid-blue: wlogout's icons are light) |
| GTK apps | `gsettings` color-scheme + `gtk-application-prefer-dark-theme` in `~/.config/gtk-3.0/settings.ini`; open apps may need a restart |

Your own `~/.config/waybar/style.css` or `~/.config/mako/config` still wins over both themes.

Not themed yet (stay dark): terminal (foot), volume/brightness bar (`rg35xxh-osd`), on-screen keyboard, External Controller status screen (it already draws from `PALETTES`, so light is new palette entries). Possible later: follow the time of day.

## Theme files (v0.4.0, in progress)

The next Theme app reads themes as `.handtop-theme` files (a zip: `theme.json` + PNG images at fixed paths) that cover every static visual part. The code is `src/theme/handtop_theme/`; only the Theme app will use it, components read the files it renders. Step 1 (this code) is not wired into the session yet: today's dark / light switch above is unchanged.

| Module | Does |
|---|---|
| `schema.py` | The contract, schema 1: 13 palette colours, 111 per-part colours each with a rule that derives it from the palette, 173 image slots (fixed name, size, required / optional / generated, which may be `"system"`), renameable default apps, import limits |
| `theme.py` | Reads and checks `theme.json`, checks every image, and fills in what a theme leaves out: palette colours from its base theme (`handtop-dark` / `handtop-light`), part colours from its own palette, images from the base (or made from the theme's own: shake frames, 22 / 20 px app icons); a wallpaper image is never inherited |
| `pngcheck.py` | PNG check without a decoder (chunk CRCs, IHDR, image data inflated with a hard limit), then a full decode with GdkPixbuf |
| `imgops.py` | GdkPixbuf: smooth downscale (HYPER) for small app icons, the sideways shift for shake frames. No Pillow on the device |
| `package.py` | Import (only the contract's paths are unpacked; no `..`, absolute paths, links or encrypted entries; sizes checked on the bytes read; the theme is checked in a temporary folder and only then moved into place), export (adds `GUIDE.md`), duplicate, list, delete |
| `render.py` | Writes `theme.env`, Waybar / mako / labwc / wlogout / nwg-drawer / foot configs, the flat `icons/` folder and the `Handtop-Current` GTK icon theme into one folder, swapped in whole |
| `guide.py` | `GUIDE.md`, generated from the schema |
| `builtin.py` | Assembles the built-in `handtop-dark` / `handtop-light` themes from `src/theme/themes/<id>/theme.json` and the generated pixel art in `overlay/` |

Decisions (2026-11-10): rendered files go to `~/.local/state/rg35xxh/theme/` (a cache may be cleared); `~/.config/rg35xxh/theme` keeps the choice (the theme id) and gets a `theme.env` next to it; part colours a theme leaves out are derived from its own palette, so a palette-only theme still looks consistent; input-mode shake frames may be drawn by the theme, otherwise the whole icon is shifted; Wi-Fi tray icons are optional in a theme, Bluetooth tray icons are a slot.

Tests: `python3 -m pytest -q src/theme/tests` (also in `tools/ci-checks.sh`). `test_builtin_look.py` checks that the built-in themes render to the same rules and colours as today's configs and palettes, with each intended difference listed.
