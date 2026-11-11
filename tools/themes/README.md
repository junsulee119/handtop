# Downloadable themes

Themes that are not in the image but attached to a release as `.handtop-theme` files. Each lives
as a complete theme folder in `src/theme/extra/<id>/` (what the Theme app's Import reads).

- `gen_retro.py [folder]` writes the Retro theme (`src/theme/extra/retro/` by default): `theme.json`, every image slot (16-colour pixel art, original drawings), its own pointer (`cursors/`, 24 px art doubled) and CSS (`css/`). The fonts in `fonts/` (W95FA, PxPlus IBM VGA 8x16, `LICENSE.txt`) are kept as they are. Needs Pillow.
- `pack-extra-themes.py <output folder>` checks every theme in `src/theme/extra/` the way an import does (GdkPixbuf and fontconfig where installed), writes `handtop-<id>.handtop-theme` with `GUIDE.md` inside, and imports the result once more to be sure it is accepted.

What a theme may contain: `GUIDE.md` inside any exported theme, or `docs/apps/theme.md`.
