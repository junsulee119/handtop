# Input-mode icons

Pixel-art taskbar icons (23×23) for the input daemon's modes, installed to
`overlay/usr/local/share/rg35xxh/icons/inputmode-{desktop,gamepad,bt,wired}[-light].png`
and shown by Waybar's `image#inputmode` module (`rg35xxh-inputmode`).

- `gen_base.py` — the pixel art (one string grid per drawing; gamepad/BT/wired show an RG35XX H: D-pad, coloured X/A/B/Y, dark screen with glare, 3x3 sticks; all widths and heights odd so they centre exactly) and the glass frame (rounded square, 1 px ring, translucent tint).
- `gen_rainbow.py` — dark-taskbar set: external modes (BT, wired) get diagonal rainbow stripes (gradient, saturation 0.65, value 0.58) with a 1 px clear halo around the drawing. The final set is the third variant, written as `grad65-2-<mode>.png`.
- `gen_light.py` — light-taskbar set (`inputmode-<mode>-light.png`): dark drawing, pastel glass, deeper ring; needs the dark PNGs in the same folder for its preview.

- `gen_shake.py` — shake frames (`inputmode-<mode>[-light]-shake<dx>.png`, dx = -2, -1, 1, 2): the drawing shifted sideways inside the glass. the input daemon shows them on the old icon (one damped-spring swing per 60 ms frame, ~0.36 s) before switching to the new one, vibrating in step.
- `gen_battery.py` — taskbar battery icons (`battery[-charging][-low]-<bars>[-light].png`, 20x11): shell always white/ink, 5 bars of 20 %, red bars at 0-20 %, a yellow bolt (1 px clear outline) while charging. Run with the icon folder as the argument. `rg35xxh-battery --animate` steps the charging animation (bars from the current level up to full).

Run in a scratch folder (they write preview PNGs next to themselves): `python3 gen_rainbow.py && python3 gen_light.py && python3 gen_shake.py`. Needs Pillow.
- `gen_app_icons.py <icon folder>` — app drawer icons: `app-theme.png`, and `app-external-controller.png` (27x27 art doubled + 1 px margin = exactly 56 px, the drawer's icon size).
