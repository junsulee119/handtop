# Theme

The **Theme** app (`rg35xxh-theme`, helper `rg35xxh-themed`): dark (default) or light, switched live.

## Usage

**Apps → Theme** (or `rg35xxh-theme dark|light`, `rg35xxh-theme --get`): dark (default) or light. The choice is one file, `~/.config/rg35xxh/theme`, read by every themed part; a switch applies live.

| Part | How it follows the theme |
|---|---|
| Waybar | `rg35xxh-themed waybar` (autostart) adds `-s /etc/xdg/waybar/style-light.css` (imports `style.css`, overrides the colours); the Theme app restarts it |
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
