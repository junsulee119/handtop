# Generators for the Retro, Glass, Pocket and Signal themes

Built-in themes (in the image since v0.4.0). Each lives as a complete theme folder in
`src/theme/themes/handtop-<id>/`, which `build/07d-theme.sh` copies into the image as it is.

- `gen_retro.py [folder]` writes the Retro theme (`src/theme/themes/handtop-retro/` by default): `theme.json`, every image slot (16-colour pixel art, original drawings), its own pointer (`cursors/`, 24 px art doubled) and CSS (`css/`). The fonts in `fonts/` (W95FA, PxPlus IBM VGA 8x16, `LICENSE.txt`) are kept as they are. Needs Pillow.
- `gen_glass.py [folder]` writes the Glass theme (`src/theme/themes/handtop-glass/`): light glass; monotone line icons drawn as anti-aliased shapes (8x supersampled, centred; app and power-menu glyphs with square ends and mitred corners, `VSharp`; outlines of combined shapes by `stroke_shape`), separate 22 / 20 px app icons, a smooth pointer, a 960x720 gradient wallpaper, CSS for the floating taskbar pills and the accent in GTK apps. `fonts/` (Inter variable, `LICENSE.txt`) is kept as it is.
- `gen_pocket.py [folder]` writes the Pocket theme (`src/theme/themes/handtop-pocket/`): its own pixel art in exactly four greens (filled shapes on a small canvas, `P.outline()` adds the dark outline, every drawing centred), adds a dithered landscape wallpaper, the theme's colours and CSS. `fonts/` (Pixelify Sans, VT323, `LICENSE.txt`) is kept as it is.
- `gen_signal.py [folder]` writes the Signal theme (`src/theme/themes/handtop-signal/`): geometric icons in black with one red element (anti-aliased with gen_glass.py's `V` / `VSharp`; pixel-exact `grid()` for the images External Controller enlarges), an abstract poster wallpaper (rings and one red disc), colours and CSS. `fonts/` (Space Grotesk, Space Mono, `LICENSE.txt`) is kept as it is.

What a theme may contain: `GUIDE.md` inside any exported theme, or `docs/apps/theme.md`.
