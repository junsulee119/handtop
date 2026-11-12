# Editing this Handtop theme (schema 1)

This file is written by Handtop's Theme app and ignored when the theme is imported. It lists everything a theme can change. Edit `theme.json` and the PNG files, zip the folder (or its contents), rename it to `<name>.handtop-theme`, then **Apps → Theme → Import** and **Apply** on the handheld. The Theme app lists every problem it finds.

## What a theme is

- Static looks only: colours, images, fonts, pointer, wallpaper, app names of the default apps, and optional CSS added to a few parts.
- Never behaviour, animation timing, scripts or config text: Handtop writes every config itself.
- Not in themes: the boot screen and boot logo, Battery saver (a theme only draws its icons), Moonlight and Tailscale's own logos.

## theme.json

| Field | Value |
|---|---|
| `schema` | `1` |
| `id` | 1-40 characters `a-z`, `0-9`, `-`; also the folder name. `handtop-…` is kept for the built-in themes |
| `name` | shown in the Theme app, 1-32 characters |
| `base` | `dark` or `light`: the built-in Handtop theme that fills in anything left out, and what apps that only know dark / light use |
| `author`, `description` | optional, one line each (anything else is ignored) |
| `version` | optional whole number from 1; raise it whenever you share a changed theme |
| `license` | optional, one line: the licence of the theme and of its fonts and images, e.g. `CC BY 4.0; fonts OFL 1.1` |
| `tags` | optional, up to 8 short words (`a-z`, `0-9`, `-`) to find the theme by, e.g. `["pixel", "retro"]` |
| `palette` | the shared colours (below) |
| `colors` | optional per-part colours (below), `"<part>.<key>": "#rrggbb"` |
| `wallpaper` | `color` (an alpha part is dropped: the wallpaper is opaque), `image` (`"images/wallpaper.png"` or `null`), `mode` (center, fill, fit, stretch, tile) |
| `gtk` | `color_scheme` (prefer-dark, default, prefer-light), `theme`, `icon_theme`: installed names |
| `cursor` | `theme` (installed; ignored when the theme draws its own pointer), `size` 16-64, `hotspots` (`"<shape>": [x, y]` on the 48 px drawing). Applies at the next log-in |
| `fonts` | `ui`, `mono` (installed font names, or the family of the theme's own font file), `scale` 0.75-1.5 (GTK apps, taskbar, notifications, app drawer; the power menu's large labels and window titles stay as they are) |
| `borders` | line width 1-3 (taskbar line, notification and power-menu borders, keyboard keys; 1 = Handtop's) |
| `icons` | `"<slot>": "system"` to use the package's own icon (only slots marked *system ok*) |
| `names` | `"<app>": "Name"` for default apps, 1-24 characters, or `"system"` |

Colours are `#rrggbb`, or `#rrggbbaa` with opacity. Anything left out is filled in: palette colours from the base theme, part colours from your own palette (rules below), images from the base theme (or made from your own image, where noted). The wallpaper image is never taken from the base theme.

### Palette

| Key | Used for |
|---|---|
| `bg` | background of the desktop's panels and windows |
| `surface` | buttons and keys on the background |
| `surface_hi` | a raised or active surface (active window, active title bar) |
| `border` | lines around buttons and panels |
| `fg` | text |
| `fg_dim` | secondary text, inactive titles |
| `accent` | accent fill (Apps button, highlighted button) |
| `accent_fg` | accent used as text or outline on the background |
| `on_accent` | text on an accent fill |
| `warn` | warnings (battery low) |
| `error` | errors (battery critical) |
| `brightness` | the brightness bar and latched keys (amber in Handtop) |
| `success` | positive state (connected, LED) |

### Part colours (`colors`)

| Key | Used for | When left out |
|---|---|---|
| `taskbar.bg` | taskbar background | `bg` |
| `taskbar.fg` | taskbar text | `fg` |
| `taskbar.border` | line above the taskbar | `bg` mixed 15 % with `fg` |
| `taskbar.apps_bg` | Apps button | `accent` |
| `taskbar.apps_fg` | Apps button text | `on_accent` |
| `taskbar.active_bg` | the active window's button | `surface_hi` |
| `taskbar.warn` | battery % when low | `warn` |
| `taskbar.critical` | battery % when critical | `error` |
| `titlebar.active_bg` | active window title bar | `surface_hi` |
| `titlebar.inactive_bg` | inactive window title bar | `surface` |
| `titlebar.active_fg` | active window title | `fg` |
| `titlebar.inactive_fg` | inactive window title | `fg_dim` |
| `titlebar.active_button` | title-bar buttons, active window (null: labwc's own) (may be `null`) | `fg` |
| `titlebar.inactive_button` | title-bar buttons, inactive window (null: labwc's own) (may be `null`) | `fg_dim` |
| `drawer.bg` | app drawer background | `bg` at 95 % opacity |
| `drawer.fg` | app names | `fg` |
| `drawer.entry_bg` | search field | `fg` at 8 % opacity |
| `drawer.hover_bg` | app under the pointer | `fg` at 10 % opacity |
| `powermenu.backdrop` | behind the buttons | `bg` at 92 % opacity |
| `powermenu.button_bg` | button | `surface` |
| `powermenu.button_border` | button border | `border` |
| `powermenu.fg` | button text | `fg` |
| `powermenu.hover_bg` | highlighted button | `accent` |
| `powermenu.hover_border` | highlighted button border | `accent_fg` |
| `powermenu.focus` | keyboard focus outline | `accent_fg` |
| `notify.bg` | notification background | `bg` at 90 % opacity |
| `notify.fg` | notification text | `fg` |
| `notify.border` | notification border | `accent` |
| `osk.bg` | keyboard background | `bg` |
| `osk.key` | character key | `surface` |
| `osk.border` | character key border | `border` |
| `osk.fg` | character key label | `fg` |
| `osk.spec` | special key (Tab, Shift, arrows) | `surface` mixed 30 % with `accent` |
| `osk.spec_border` | special key border | `border` mixed 50 % with `accent` |
| `osk.spec_fg` | special key label | `accent_fg` |
| `osk.sel` | highlighted key | `accent` |
| `osk.sel_border` | highlighted key border | `accent_fg` |
| `osk.sel_fg` | highlighted key label | `on_accent` |
| `osk.latch` | latched Shift / Ctrl / Alt | `surface` mixed 40 % with `brightness` |
| `osk.latch_sel` | latched and highlighted | `surface` mixed 60 % with `brightness` |
| `osk.latch_border` | latched and highlighted border | `brightness` |
| `osk.badge` | shoulder-button badge | `accent_fg` |
| `osk.hit` | key just typed (press trace) | `bg` mixed 40 % with `#000000` |
| `osk.hit_border` | press trace border | `accent` |
| `osk.hit_fg` | press trace label | `accent_fg` |
| `status.bg` | screen background | `bg` |
| `status.body` | handheld body | `surface` |
| `status.body_edge` | body outline | `border` |
| `status.body_shade` | body shading | `surface` mixed 30 % with `#000000` |
| `status.part` | buttons and sticks | `bg` mixed 30 % with `#000000` |
| `status.part_edge` | button outlines | `border` |
| `status.lit` | pressed control | `accent_fg` |
| `status.lit_edge` | pressed control outline | `accent_fg` mixed 50 % with `#ffffff` |
| `status.bezel` | screen bezel | `#0d0d0f` (fixed) |
| `status.bezel_edge` | bezel outline | `border` |
| `status.screen` | the handheld's screen | `#08090c` (fixed) |
| `status.led` | power LED | `success` |
| `status.cap` | stick caps and shoulder caps | `surface` |
| `status.face_x` | X button | `#5c85ff` (fixed) |
| `status.face_y` | Y button | `#59d16b` (fixed) |
| `status.face_a` | A button | `#f24d4d` (fixed) |
| `status.face_b` | B button | `#fad940` (fixed) |
| `status.label` | button letters (null: drawn in the button colour) (may be `null`) | `fg` |
| `status.label_lit` | letters on a pressed button | `bg` |
| `status.text` | page text (around the handheld) | `fg` |
| `status.dim` | secondary page text | `fg_dim` |
| `status.ok` | connected | `success` |
| `status.warn` | waiting / warning | `warn` |
| `status.screen_text` | text on the drawn screen (always dark) | `#e8ebed` (fixed) |
| `status.screen_dim` | secondary text on the drawn screen | `#949eb0` (fixed) |
| `status.screen_ok` | connected, on the drawn screen | `#8cd99e` (fixed) |
| `status.screen_warn` | warning, on the drawn screen | `#ffcc66` (fixed) |
| `display.bg` | background | `bg` |
| `display.card` | layout card | `surface` |
| `display.card_hi` | highlighted card | `surface_hi` |
| `display.border` | card border | `border` |
| `display.accent` | selection | `accent_fg` |
| `display.text` | text | `fg` |
| `display.dim` | secondary text | `fg_dim` |
| `display.body` | drawn handheld / monitor body | `fg` |
| `display.off` | a switched-off screen | `#0a0b0e` (fixed) |
| `display.desk` | drawn desktop | `accent` |
| `display.bar` | drawn taskbar | `bg` mixed 30 % with `#000000` |
| `display.win` | drawn window | `fg` |
| `display.sun` | drawn picture (mirror mode) | `#f0c73d` (fixed) |
| `display.track` | slider track | `border` |
| `display.btn` | button | `surface_hi` |
| `terminal.bg` | terminal background | `bg` |
| `terminal.fg` | terminal text | `fg` |
| `terminal.cursor` | cursor block | `accent_fg` |
| `terminal.cursor_text` | text under the cursor | `bg` |
| `terminal.selection_bg` | selection | `accent` |
| `terminal.selection_fg` | selected text | `on_accent` |
| `terminal.ansi0` | black | `surface` |
| `terminal.ansi1` | red | `error` |
| `terminal.ansi2` | green | `success` |
| `terminal.ansi3` | yellow | `brightness` mixed 20 % with `fg` |
| `terminal.ansi4` | blue | `#4a86e8` mixed 25 % with `fg` |
| `terminal.ansi5` | magenta | `#b45fd8` mixed 20 % with `fg` |
| `terminal.ansi6` | cyan | `#2aa1b3` mixed 20 % with `fg` |
| `terminal.ansi7` | white | `fg_dim` |
| `terminal.ansi8` | bright black (comments) | `fg_dim` mixed 40 % with `bg` |
| `terminal.ansi9` | bright red | `error` mixed 40 % with `fg` |
| `terminal.ansi10` | bright green | `success` mixed 40 % with `fg` |
| `terminal.ansi11` | bright yellow | `brightness` mixed 40 % with `fg` |
| `terminal.ansi12` | bright blue | `#4a86e8` mixed 45 % with `fg` |
| `terminal.ansi13` | bright magenta | `#b45fd8` mixed 45 % with `fg` |
| `terminal.ansi14` | bright cyan | `#2aa1b3` mixed 45 % with `fg` |
| `terminal.ansi15` | bright white | `fg` |
| `osd.bg` | bar background | `bg` at 90 % opacity |
| `osd.volume_border` | volume bar border | `accent` |
| `osd.volume_level` | volume level | `accent_fg` |
| `osd.brightness_border` | brightness bar border | `brightness` mixed 50 % with `bg` |
| `osd.brightness_level` | brightness level | `brightness` |
| `osd.text` | the number | `fg` |

## Images

PNG only, exact pixel size, at the path shown (relative to the theme folder). Pixel art is shown at its own size, never scaled (except where noted).

| File | Size | If missing |
|---|---|---|
| `icons/taskbar/apps.png` | 16×16 | base theme's |
| `icons/taskbar/power.png` | 24×24 | base theme's |
| `icons/taskbar/inputmode-desktop.png` | 23×23 | base theme's |
| `icons/taskbar/inputmode-desktop-shake-2.png` | 23×23 | made from `icons/taskbar/inputmode-desktop.png` (the whole icon shifted sideways) if that one is yours, else the base theme's |
| `icons/taskbar/inputmode-desktop-shake-1.png` | 23×23 | made from `icons/taskbar/inputmode-desktop.png` (the whole icon shifted sideways) if that one is yours, else the base theme's |
| `icons/taskbar/inputmode-desktop-shake1.png` | 23×23 | made from `icons/taskbar/inputmode-desktop.png` (the whole icon shifted sideways) if that one is yours, else the base theme's |
| `icons/taskbar/inputmode-desktop-shake2.png` | 23×23 | made from `icons/taskbar/inputmode-desktop.png` (the whole icon shifted sideways) if that one is yours, else the base theme's |
| `icons/taskbar/inputmode-gamepad.png` | 23×23 | base theme's |
| `icons/taskbar/inputmode-gamepad-shake-2.png` | 23×23 | made from `icons/taskbar/inputmode-gamepad.png` (the whole icon shifted sideways) if that one is yours, else the base theme's |
| `icons/taskbar/inputmode-gamepad-shake-1.png` | 23×23 | made from `icons/taskbar/inputmode-gamepad.png` (the whole icon shifted sideways) if that one is yours, else the base theme's |
| `icons/taskbar/inputmode-gamepad-shake1.png` | 23×23 | made from `icons/taskbar/inputmode-gamepad.png` (the whole icon shifted sideways) if that one is yours, else the base theme's |
| `icons/taskbar/inputmode-gamepad-shake2.png` | 23×23 | made from `icons/taskbar/inputmode-gamepad.png` (the whole icon shifted sideways) if that one is yours, else the base theme's |
| `icons/taskbar/inputmode-bt.png` | 23×23 | base theme's |
| `icons/taskbar/inputmode-bt-shake-2.png` | 23×23 | made from `icons/taskbar/inputmode-bt.png` (the whole icon shifted sideways) if that one is yours, else the base theme's |
| `icons/taskbar/inputmode-bt-shake-1.png` | 23×23 | made from `icons/taskbar/inputmode-bt.png` (the whole icon shifted sideways) if that one is yours, else the base theme's |
| `icons/taskbar/inputmode-bt-shake1.png` | 23×23 | made from `icons/taskbar/inputmode-bt.png` (the whole icon shifted sideways) if that one is yours, else the base theme's |
| `icons/taskbar/inputmode-bt-shake2.png` | 23×23 | made from `icons/taskbar/inputmode-bt.png` (the whole icon shifted sideways) if that one is yours, else the base theme's |
| `icons/taskbar/inputmode-wired.png` | 23×23 | base theme's |
| `icons/taskbar/inputmode-wired-shake-2.png` | 23×23 | made from `icons/taskbar/inputmode-wired.png` (the whole icon shifted sideways) if that one is yours, else the base theme's |
| `icons/taskbar/inputmode-wired-shake-1.png` | 23×23 | made from `icons/taskbar/inputmode-wired.png` (the whole icon shifted sideways) if that one is yours, else the base theme's |
| `icons/taskbar/inputmode-wired-shake1.png` | 23×23 | made from `icons/taskbar/inputmode-wired.png` (the whole icon shifted sideways) if that one is yours, else the base theme's |
| `icons/taskbar/inputmode-wired-shake2.png` | 23×23 | made from `icons/taskbar/inputmode-wired.png` (the whole icon shifted sideways) if that one is yours, else the base theme's |
| `icons/taskbar/battery-0.png` | 20×11 | base theme's |
| `icons/taskbar/battery-0-saver.png` | 20×11 | base theme's |
| `icons/taskbar/battery-1.png` | 20×11 | base theme's |
| `icons/taskbar/battery-1-saver.png` | 20×11 | base theme's |
| `icons/taskbar/battery-2.png` | 20×11 | base theme's |
| `icons/taskbar/battery-2-saver.png` | 20×11 | base theme's |
| `icons/taskbar/battery-3.png` | 20×11 | base theme's |
| `icons/taskbar/battery-3-saver.png` | 20×11 | base theme's |
| `icons/taskbar/battery-4.png` | 20×11 | base theme's |
| `icons/taskbar/battery-4-saver.png` | 20×11 | base theme's |
| `icons/taskbar/battery-5.png` | 20×11 | base theme's |
| `icons/taskbar/battery-5-saver.png` | 20×11 | base theme's |
| `icons/taskbar/battery-low-0.png` | 20×11 | base theme's |
| `icons/taskbar/battery-low-0-saver.png` | 20×11 | base theme's |
| `icons/taskbar/battery-low-1.png` | 20×11 | base theme's |
| `icons/taskbar/battery-low-1-saver.png` | 20×11 | base theme's |
| `icons/taskbar/battery-low-2.png` | 20×11 | base theme's |
| `icons/taskbar/battery-low-2-saver.png` | 20×11 | base theme's |
| `icons/taskbar/battery-low-3.png` | 20×11 | base theme's |
| `icons/taskbar/battery-low-3-saver.png` | 20×11 | base theme's |
| `icons/taskbar/battery-low-4.png` | 20×11 | base theme's |
| `icons/taskbar/battery-low-4-saver.png` | 20×11 | base theme's |
| `icons/taskbar/battery-low-5.png` | 20×11 | base theme's |
| `icons/taskbar/battery-low-5-saver.png` | 20×11 | base theme's |
| `icons/taskbar/battery-charging-0.png` | 20×11 | base theme's |
| `icons/taskbar/battery-charging-0-saver.png` | 20×11 | base theme's |
| `icons/taskbar/battery-charging-1.png` | 20×11 | base theme's |
| `icons/taskbar/battery-charging-1-saver.png` | 20×11 | base theme's |
| `icons/taskbar/battery-charging-2.png` | 20×11 | base theme's |
| `icons/taskbar/battery-charging-2-saver.png` | 20×11 | base theme's |
| `icons/taskbar/battery-charging-3.png` | 20×11 | base theme's |
| `icons/taskbar/battery-charging-3-saver.png` | 20×11 | base theme's |
| `icons/taskbar/battery-charging-4.png` | 20×11 | base theme's |
| `icons/taskbar/battery-charging-4-saver.png` | 20×11 | base theme's |
| `icons/taskbar/battery-charging-5.png` | 20×11 | base theme's |
| `icons/taskbar/battery-charging-5-saver.png` | 20×11 | base theme's |
| `icons/taskbar/battery-charging-low-0.png` | 20×11 | base theme's |
| `icons/taskbar/battery-charging-low-0-saver.png` | 20×11 | base theme's |
| `icons/taskbar/battery-charging-low-1.png` | 20×11 | base theme's |
| `icons/taskbar/battery-charging-low-1-saver.png` | 20×11 | base theme's |
| `icons/taskbar/battery-charging-low-2.png` | 20×11 | base theme's |
| `icons/taskbar/battery-charging-low-2-saver.png` | 20×11 | base theme's |
| `icons/taskbar/battery-charging-low-3.png` | 20×11 | base theme's |
| `icons/taskbar/battery-charging-low-3-saver.png` | 20×11 | base theme's |
| `icons/taskbar/battery-charging-low-4.png` | 20×11 | base theme's |
| `icons/taskbar/battery-charging-low-4-saver.png` | 20×11 | base theme's |
| `icons/taskbar/battery-charging-low-5.png` | 20×11 | base theme's |
| `icons/taskbar/battery-charging-low-5-saver.png` | 20×11 | base theme's |
| `icons/tray/nm-device-wired.png` | 23×23 | base theme's, *system ok* |
| `icons/tray/nm-device-wired-secure.png` | 23×23 | base theme's, *system ok* |
| `icons/tray/nm-no-connection.png` | 23×23 | base theme's, *system ok* |
| `icons/tray/nm-signal-00.png` | 23×23 | base theme's, *system ok* |
| `icons/tray/nm-signal-00-secure.png` | 23×23 | base theme's, *system ok* |
| `icons/tray/nm-signal-25.png` | 23×23 | base theme's, *system ok* |
| `icons/tray/nm-signal-25-secure.png` | 23×23 | base theme's, *system ok* |
| `icons/tray/nm-signal-50.png` | 23×23 | base theme's, *system ok* |
| `icons/tray/nm-signal-50-secure.png` | 23×23 | base theme's, *system ok* |
| `icons/tray/nm-signal-75.png` | 23×23 | base theme's, *system ok* |
| `icons/tray/nm-signal-75-secure.png` | 23×23 | base theme's, *system ok* |
| `icons/tray/nm-signal-100.png` | 23×23 | base theme's, *system ok* |
| `icons/tray/nm-signal-100-secure.png` | 23×23 | base theme's, *system ok* |
| `icons/tray/nm-stage01-connecting01.png` | 23×23 | base theme's, *system ok* |
| `icons/tray/nm-stage01-connecting02.png` | 23×23 | base theme's, *system ok* |
| `icons/tray/nm-stage01-connecting03.png` | 23×23 | base theme's, *system ok* |
| `icons/tray/nm-stage01-connecting04.png` | 23×23 | base theme's, *system ok* |
| `icons/tray/nm-stage01-connecting05.png` | 23×23 | base theme's, *system ok* |
| `icons/tray/nm-stage01-connecting06.png` | 23×23 | base theme's, *system ok* |
| `icons/tray/nm-stage01-connecting07.png` | 23×23 | base theme's, *system ok* |
| `icons/tray/nm-stage01-connecting08.png` | 23×23 | base theme's, *system ok* |
| `icons/tray/nm-stage01-connecting09.png` | 23×23 | base theme's, *system ok* |
| `icons/tray/nm-stage01-connecting10.png` | 23×23 | base theme's, *system ok* |
| `icons/tray/nm-stage01-connecting11.png` | 23×23 | base theme's, *system ok* |
| `icons/tray/nm-stage02-connecting01.png` | 23×23 | base theme's, *system ok* |
| `icons/tray/nm-stage02-connecting02.png` | 23×23 | base theme's, *system ok* |
| `icons/tray/nm-stage02-connecting03.png` | 23×23 | base theme's, *system ok* |
| `icons/tray/nm-stage02-connecting04.png` | 23×23 | base theme's, *system ok* |
| `icons/tray/nm-stage02-connecting05.png` | 23×23 | base theme's, *system ok* |
| `icons/tray/nm-stage02-connecting06.png` | 23×23 | base theme's, *system ok* |
| `icons/tray/nm-stage02-connecting07.png` | 23×23 | base theme's, *system ok* |
| `icons/tray/nm-stage02-connecting08.png` | 23×23 | base theme's, *system ok* |
| `icons/tray/nm-stage02-connecting09.png` | 23×23 | base theme's, *system ok* |
| `icons/tray/nm-stage02-connecting10.png` | 23×23 | base theme's, *system ok* |
| `icons/tray/nm-stage02-connecting11.png` | 23×23 | base theme's, *system ok* |
| `icons/tray/nm-stage03-connecting01.png` | 23×23 | base theme's, *system ok* |
| `icons/tray/nm-stage03-connecting02.png` | 23×23 | base theme's, *system ok* |
| `icons/tray/nm-stage03-connecting03.png` | 23×23 | base theme's, *system ok* |
| `icons/tray/nm-stage03-connecting04.png` | 23×23 | base theme's, *system ok* |
| `icons/tray/nm-stage03-connecting05.png` | 23×23 | base theme's, *system ok* |
| `icons/tray/nm-stage03-connecting06.png` | 23×23 | base theme's, *system ok* |
| `icons/tray/nm-stage03-connecting07.png` | 23×23 | base theme's, *system ok* |
| `icons/tray/nm-stage03-connecting08.png` | 23×23 | base theme's, *system ok* |
| `icons/tray/nm-stage03-connecting09.png` | 23×23 | base theme's, *system ok* |
| `icons/tray/nm-stage03-connecting10.png` | 23×23 | base theme's, *system ok* |
| `icons/tray/nm-stage03-connecting11.png` | 23×23 | base theme's, *system ok* |
| `icons/tray/blueman-tray.png` | 23×23 | base theme's, *system ok* |
| `icons/tray/blueman-active.png` | 23×23 | base theme's, *system ok* |
| `icons/tray/blueman-disabled.png` | 23×23 | base theme's, *system ok* |
| `icons/apps/theme.png` | 56×56 | base theme's |
| `icons/apps/theme@22.png` | 22×22 | made from `icons/apps/theme.png` (smooth downscale; draw it for crisp pixel art) if that one is yours, else the base theme's |
| `icons/apps/theme@20.png` | 20×20 | made from `icons/apps/theme.png` (smooth downscale; draw it for crisp pixel art) if that one is yours, else the base theme's |
| `icons/apps/external-controller.png` | 56×56 | base theme's |
| `icons/apps/external-controller@22.png` | 22×22 | made from `icons/apps/external-controller.png` (smooth downscale; draw it for crisp pixel art) if that one is yours, else the base theme's |
| `icons/apps/external-controller@20.png` | 20×20 | made from `icons/apps/external-controller.png` (smooth downscale; draw it for crisp pixel art) if that one is yours, else the base theme's |
| `icons/apps/display.png` | 56×56 | base theme's |
| `icons/apps/display@22.png` | 22×22 | made from `icons/apps/display.png` (smooth downscale; draw it for crisp pixel art) if that one is yours, else the base theme's |
| `icons/apps/display@20.png` | 20×20 | made from `icons/apps/display.png` (smooth downscale; draw it for crisp pixel art) if that one is yours, else the base theme's |
| `icons/apps/enable-ssh.png` | 56×56 | base theme's |
| `icons/apps/enable-ssh@22.png` | 22×22 | made from `icons/apps/enable-ssh.png` (smooth downscale; draw it for crisp pixel art) if that one is yours, else the base theme's |
| `icons/apps/enable-ssh@20.png` | 20×20 | made from `icons/apps/enable-ssh.png` (smooth downscale; draw it for crisp pixel art) if that one is yours, else the base theme's |
| `icons/apps/recenter-sticks.png` | 56×56 | base theme's |
| `icons/apps/recenter-sticks@22.png` | 22×22 | made from `icons/apps/recenter-sticks.png` (smooth downscale; draw it for crisp pixel art) if that one is yours, else the base theme's |
| `icons/apps/recenter-sticks@20.png` | 20×20 | made from `icons/apps/recenter-sticks.png` (smooth downscale; draw it for crisp pixel art) if that one is yours, else the base theme's |
| `icons/apps/foot.png` | 56×56 | base theme's, *system ok* |
| `icons/apps/foot@22.png` | 22×22 | made from `icons/apps/foot.png` (smooth downscale; draw it for crisp pixel art) if that one is yours, else the base theme's, *system ok* |
| `icons/apps/foot@20.png` | 20×20 | made from `icons/apps/foot.png` (smooth downscale; draw it for crisp pixel art) if that one is yours, else the base theme's, *system ok* |
| `icons/apps/thunar.png` | 56×56 | base theme's, *system ok* |
| `icons/apps/thunar@22.png` | 22×22 | made from `icons/apps/thunar.png` (smooth downscale; draw it for crisp pixel art) if that one is yours, else the base theme's, *system ok* |
| `icons/apps/thunar@20.png` | 20×20 | made from `icons/apps/thunar.png` (smooth downscale; draw it for crisp pixel art) if that one is yours, else the base theme's, *system ok* |
| `icons/apps/mousepad.png` | 56×56 | base theme's, *system ok* |
| `icons/apps/mousepad@22.png` | 22×22 | made from `icons/apps/mousepad.png` (smooth downscale; draw it for crisp pixel art) if that one is yours, else the base theme's, *system ok* |
| `icons/apps/mousepad@20.png` | 20×20 | made from `icons/apps/mousepad.png` (smooth downscale; draw it for crisp pixel art) if that one is yours, else the base theme's, *system ok* |
| `icons/apps/chromium.png` | 56×56 | base theme's, *system ok* |
| `icons/apps/chromium@22.png` | 22×22 | made from `icons/apps/chromium.png` (smooth downscale; draw it for crisp pixel art) if that one is yours, else the base theme's, *system ok* |
| `icons/apps/chromium@20.png` | 20×20 | made from `icons/apps/chromium.png` (smooth downscale; draw it for crisp pixel art) if that one is yours, else the base theme's, *system ok* |
| `icons/apps/htop.png` | 56×56 | base theme's, *system ok* |
| `icons/apps/htop@22.png` | 22×22 | made from `icons/apps/htop.png` (smooth downscale; draw it for crisp pixel art) if that one is yours, else the base theme's, *system ok* |
| `icons/apps/htop@20.png` | 20×20 | made from `icons/apps/htop.png` (smooth downscale; draw it for crisp pixel art) if that one is yours, else the base theme's, *system ok* |
| `icons/apps/micro.png` | 56×56 | base theme's, *system ok* |
| `icons/apps/micro@22.png` | 22×22 | made from `icons/apps/micro.png` (smooth downscale; draw it for crisp pixel art) if that one is yours, else the base theme's, *system ok* |
| `icons/apps/micro@20.png` | 20×20 | made from `icons/apps/micro.png` (smooth downscale; draw it for crisp pixel art) if that one is yours, else the base theme's, *system ok* |
| `icons/apps/qpdfview.png` | 56×56 | base theme's, *system ok* |
| `icons/apps/qpdfview@22.png` | 22×22 | made from `icons/apps/qpdfview.png` (smooth downscale; draw it for crisp pixel art) if that one is yours, else the base theme's, *system ok* |
| `icons/apps/qpdfview@20.png` | 20×20 | made from `icons/apps/qpdfview.png` (smooth downscale; draw it for crisp pixel art) if that one is yours, else the base theme's, *system ok* |
| `icons/apps/xarchiver.png` | 56×56 | base theme's, *system ok* |
| `icons/apps/xarchiver@22.png` | 22×22 | made from `icons/apps/xarchiver.png` (smooth downscale; draw it for crisp pixel art) if that one is yours, else the base theme's, *system ok* |
| `icons/apps/xarchiver@20.png` | 20×20 | made from `icons/apps/xarchiver.png` (smooth downscale; draw it for crisp pixel art) if that one is yours, else the base theme's, *system ok* |
| `icons/apps/blueman.png` | 56×56 | base theme's, *system ok* |
| `icons/apps/blueman@22.png` | 22×22 | made from `icons/apps/blueman.png` (smooth downscale; draw it for crisp pixel art) if that one is yours, else the base theme's, *system ok* |
| `icons/apps/blueman@20.png` | 20×20 | made from `icons/apps/blueman.png` (smooth downscale; draw it for crisp pixel art) if that one is yours, else the base theme's, *system ok* |
| `icons/power-menu/sleep.png` | 72×72 | base theme's |
| `icons/power-menu/sleep-focus.png` | 72×72 | base theme's |
| `icons/power-menu/reboot.png` | 72×72 | base theme's |
| `icons/power-menu/reboot-focus.png` | 72×72 | base theme's |
| `icons/power-menu/logout.png` | 72×72 | base theme's |
| `icons/power-menu/logout-focus.png` | 72×72 | base theme's |
| `icons/power-menu/shutdown.png` | 72×72 | base theme's |
| `icons/power-menu/shutdown-focus.png` | 72×72 | base theme's |
| `icons/power-menu/saver.png` | 72×72 | base theme's |
| `icons/power-menu/saver-focus.png` | 72×72 | base theme's |
| `icons/controller/usbtarget-pc.png` | 23×23 | base theme's |
| `icons/controller/usbtarget-console.png` | 23×23 | base theme's |
| `images/wallpaper.png` | up to 3840×2160, 4 MB | no image (colour only) |
| `preview.png` | 256×192 | drawn by the Theme app |

Input-mode icons shake on a mode change: `…-shake-2`, `-shake-1`, `-shake1`, `-shake2` are the frames (the drawing moved that many pixels). Handtop moves only the drawing inside its glass frame; without your own frames the whole icon moves.

## Pointer (optional)

Draw any of these at 48×48 (twice the 24 px size; pixel art drawn at 2× stays crisp). Handtop makes an Xcursor set from them with a 24 px and a 48 px size; shapes you leave out are Handtop's own. The hotspot is the pixel that points (default in brackets).

| File | Used for | Default hotspot |
|---|---|---|
| `cursors/arrow.png` | left_ptr, default, arrow, top_left_arrow | [0, 0] |
| `cursors/hand.png` | hand2, hand1, pointer | [10, 2] |
| `cursors/text.png` | xterm, text, ibeam | [6, 14] |
| `cursors/busy.png` | watch, wait | [10, 14] |
| `cursors/progress.png` | left_ptr_watch, progress | [0, 0] |

## Fonts (optional)

`fonts/ui.ttf` (or `.otf`) for text and `fonts/mono.ttf` for the terminal, at most 2 MB each, one font per file (no collections; a variable font is fine). Set `fonts.ui` / `fonts.mono` to the font's family name; the import checks it with fontconfig. Put the font licence in `fonts/LICENSE.txt`: only share fonts whose licence allows it (for example the SIL Open Font License). Applying the theme installs its fonts for your user; the next theme's replace them.

## CSS (optional)

GTK CSS added after Handtop's own rules for a part, so yours wins. Plain UTF-8 text, at most 64 KB; `@import`, `url()` and backslash escapes are refused. Keep the taskbar 32 px high and the power menu's three columns within 640 px. GTK reads `css/apps.css` in every GTK 3 program, the taskbar, app drawer and power menu included, and it wins over their own rules: test those too.

| File | Added to |
|---|---|
| `css/apps.css` | GTK 3 apps' windows (linked as ~/.config/gtk-3.0/gtk.css unless you have your own) |
| `css/taskbar.css` | the taskbar (Waybar) |
| `css/drawer.css` | the app drawer (nwg-drawer) |
| `css/powermenu.css` | the power menu (wlogout) |

## Drawing tips (mistakes found on the device)

Handtop places every image by its full size, never by what is drawn in it, so the drawing itself must be centred:

- **Centre the drawing inside its image**, both ways. A drawing that starts at the top or the left edge of a 23×23 icon sits visibly high or to one side on the taskbar (Retro's first mouse icon sat 4 px high; app icons were up to 8 px off in the app drawer). Check the bounding box of the drawn pixels: its middle should be the image's middle.
- **Match the width parity.** A shape centred in an odd-sized image (23, 11) needs an odd width; in an even-sized one (16, 24, 56, 72) an even width. A 2 px stick in a ring drawn around a single centre pixel leans half a pixel to one side: centre the ring on the line between the two stick columns. A 15 px drawing in a 16 px image cannot be centred: draw it 16 px wide.
- **Icons that change keep one baseline.** Signal bars, battery levels and animation frames: centre the full set (all bars, the whole battery), not what happens to be lit, so the icon does not jump. Put badges (padlock, error mark, dots) in a corner, outside that centring.
- **Pixel art at 2×** (app icons 56 px, power menu 72 px, pointer 48 px): draw at half size and double every pixel, so lines stay 2 px and crisp. The 22 / 20 px app icons and the pointer's 24 px size are made from these by smooth scaling.
- **Check it on the taskbar**, not only in a picture viewer: take a screenshot and compare the vertical middle of every icon and button. Handtop's own icons sit 1 px above the taskbar's middle; buttons you add with `css/taskbar.css` should share that line (Retro: 2 px margin above, 3 px below).
- **`css/apps.css` reaches the taskbar, app drawer and power menu too** (they are GTK 3 programs) and overrides their rules: a broad rule such as `list, .view, row { background: white }` turned Retro's app drawer white. Keep its selectors narrow and look at all three.
- **Pointer hotspots** are in 48 px units: double the pixel you mean in 24 px art. The pointer changes at the next log-in.

## App names

Default apps only: `foot`, `thunar`, `mousepad`, `chromium`, `htop`, `micro`, `qpdfview`, `xarchiver`. Handtop's own apps keep their names.

## Limits

- The theme file: at most 25 MB; unpacked 20 MB, 300 files; each icon 256 KB.
- Only the files listed here are read; anything else is ignored. No links, no paths outside the theme folder.
- Any error refuses the whole theme and the current one stays.

## Example

```json
{
  "schema": 1,
  "id": "my-blue",
  "name": "My Blue",
  "base": "dark",
  "palette": { "bg": "#10243f", "accent": "#2f6fd6", "accent_fg": "#9cc3ff" },
  "colors": { "taskbar.border": "#2f6fd6" },
  "wallpaper": { "color": "#0b1a2e", "image": null },
  "names": { "thunar": "Files" }
}
```
