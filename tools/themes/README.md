# Downloadable themes

Themes that are not in the image but attached to a release as `.handtop-theme` files. Each lives
as a complete theme folder in `src/theme/extra/<id>/` (what the Theme app's Import reads).

- `gen_retro.py [folder]` writes the Retro theme (`src/theme/extra/retro/` by default): `theme.json`, every image slot (16-colour pixel art, original drawings), its own pointer (`cursors/`, 24 px art doubled) and CSS (`css/`). The fonts in `fonts/` (W95FA, PxPlus IBM VGA 8x16, `LICENSE.txt`) are kept as they are. Needs Pillow.
- `gen_glass.py [folder]` writes the Glass theme (`src/theme/extra/glass/`): light glass; monotone line icons drawn as anti-aliased shapes (8x supersampled, centred; app and power-menu glyphs with square ends and mitred corners, `VSharp`; outlines of combined shapes by `stroke_shape`), separate 22 / 20 px app icons, a smooth pointer, a 960x720 gradient wallpaper, CSS for the floating taskbar pills and the accent in GTK apps. `fonts/` (Inter variable, `LICENSE.txt`) is kept as it is.
- `gen_pocket.py [folder]` writes the Pocket theme (`src/theme/extra/pocket/`): its own pixel art in exactly four greens (filled shapes on a small canvas, `P.outline()` adds the dark outline, every drawing centred), adds a dithered landscape wallpaper, the theme's colours and CSS. `fonts/` (Pixelify Sans, VT323, `LICENSE.txt`) is kept as it is.
- `pack-extra-themes.py <output folder>` checks every theme in `src/theme/extra/` the way an import does (GdkPixbuf and fontconfig where installed), writes `handtop-<id>.handtop-theme` with `GUIDE.md` inside, and imports the result once more to be sure it is accepted.

What a theme may contain: `GUIDE.md` inside any exported theme, or `docs/apps/theme.md`.
