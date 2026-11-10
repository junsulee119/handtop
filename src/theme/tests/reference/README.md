# Handtop v0.3.9 look, frozen

Copies of the hand-written theme configs and the palettes that were in code in Handtop v0.3.9,
before v0.4.0 moved them into the built-in themes (`src/theme/themes/handtop-{dark,light}`).
`test_builtin_look.py` checks that the built-in themes still render to the same rules and
colours. Never edit these to make a test pass: change the theme or list the difference (with its
reason) in the test.

| File | Was |
|---|---|
| `waybar-style.css`, `waybar-style-light.css` | `/etc/xdg/waybar/style.css`, `style-light.css` |
| `wlogout-style.css`, `wlogout-style-light.css` | `/etc/wlogout/style.css`, `style-light.css` |
| `nwg-drawer-handtop-{dark,light}.css` | `/etc/xdg/nwg-drawer/` |
| `mako-config`, `mako-config-light` | `/etc/xdg/mako/config`, `config-light` |
| `labwc-themerc`, `labwc-themerc-light` | `/usr/share/themes/Handtop{,-Light}/labwc/themerc` |
| `foot.ini` | `/etc/xdg/foot/foot.ini` |
| `palettes-v0.3.9.json` | `PALETTES` in `osk.py` and `rg35xxh-controller-screen` (plus its light page text), `palette()` in `rg35xxh-display`, the colours in `rg35xxh-osd.c` |
