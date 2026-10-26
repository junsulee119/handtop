# On-Screen Keyboard

Part of the input daemon ([input-daemon.md](input-daemon.md), `src/inputd/rg35xxh_inputd/osk.py`); the window runs in the daemon's display process (`ui.py`).

Design of the built-in on-screen keyboard (OSK). It is part of the input daemon (`src/inputd/rg35xxh_inputd/osk.py`), so the daemon always knows whether it is open and can route the D-pad and A to it. The GTK window itself lives in a separate child process (`ui.py`, JSON lines over stdin/stdout): the daemon keeps no display connection, so a log-out cannot end it before its clean exit (see [input-daemon.md](input-daemon.md#stopping-restarting-one-instance)).

## Goals

- Type anywhere (terminal, browser, dialogs) with only the handheld's controls.
- Never steal keyboard focus: keys are sent through the daemon's virtual keyboard to whatever window is focused.
- US layout only (CJK text is display-only; no input method).

## Controls

| Control | Action |
|---|---|
| X | Show / hide the keyboard |
| D-pad | Move the highlight (auto-repeat when held: 0.4 s delay, then every 0.09 s) |
| A | Type the highlighted key (the button bound to `click_left`; A by default). Held: the key repeats after 0.5 s, every 0.06 s (not Shift / Ctrl / Alt / Hide), with the modifiers it was typed with |
| L2 | Shift (same as the ⇧ key) while the keyboard is open; its desktop binding is skipped then |
| L1 / R1 / R2 | Esc / Enter / Backspace (physical shortcuts still work while it is open) |
| Left stick | Still moves the pointer. The keys are not clicked with the pointer (intended): A is both left click and the keyboard's type button, so a pointer click on a key would make one press do two things. Type with the D-pad and A |
| Hide key | Same as X |

Moving up/down keeps the horizontal position (picks the key whose centre is closest) and wraps from the top row to the bottom row and back. Left/right wraps around within a row. The highlight starts on `g`.

Keys that a shoulder button also types carry a small corner badge with that button's name (by default `L1` on Esc, `R1` on Enter, `L2` on ⇧, `R2` on ⌫), taken from the `[desktop]` bindings, so a remapped shoulder moves its badge.

## Layout

Five rows, 15 keys wide (US), staggered like a real keyboard: each row starts a little further right (widths in quarter keys, every row 60). Enter and ⌫ are where a real keyboard has them (wide), Ctrl sits where Caps Lock is (HHKB style), ↑ is right above ↓ with Esc beside it, Hide is next to Alt.

```
`  1  2  3  4  5  6  7  8  9  0  -  =    ⌫
Tab   q  w  e  r  t  y  u  i  o  p  [  ]  \
Ctrl    a  s  d  f  g  h  j  k  l  ;  '  Enter
⇧          z  x  c  v  b  n  m  ,  .  /  ↑  Esc
Alt  Hide  [        Space        ]  ←  ↓  →
```

Character keys (letters, digits, symbols, Space) are brighter; special keys (Esc, Tab, Enter, ⌫, ⇧, Ctrl, Alt, arrows, Hide) are darker and bluer.

- **Press trace:** a typed key goes dark (pressed in, unlike the bright highlight) and fades back over 0.35 s when it comes up, so each press is visible even when the highlight has already moved on. With A it stays pressed in while A is held (also during key repeat); with L1 / R1 / R2 the key they type (Esc / Enter / ⌫ by default) does the same while the shoulder button is held. L2 shows as Shift latching (amber).
- **Shift / Ctrl / Alt are one-shot (latched):** press once, they apply to the next key, then release. Latched keys are shown in amber; Shift also switches the labels to their shifted form (`1` → `!`, `a` → `A`).
- Ctrl+C etc. work by latching Ctrl, then typing the letter.

## Placement

The keyboard always lives on the **handheld screen** (found as the GDK monitor narrower than 100 mm; the panel is 70×53 mm).

| Situation | Behaviour |
|---|---|
| Handheld only | Bottom of the screen, about 5 × 30 px rows. Windows shrink to sit above it (exclusive zone). |
| HDMI, **monitor only** (default) | Handheld screen is off. X turns it on and the keyboard **fills the whole 640×480 screen** as a keyboard panel (overlay layer, covers the taskbar). Hiding it turns the handheld screen off again. The panel is placed far from the monitor in the output layout (x = 4000), so the pointer cannot wander onto it; use the D-pad + A. |
| HDMI, extend | Bottom of the handheld screen (right of the monitor), same as handheld-only. |
| HDMI, mirror | Bottom of the shared 640×480 picture. |

Switching is done by `rg35xxh-display osk on|off` (see `desktop.md` → External display; not while the Display app is open, which keeps the handheld screen on by itself).

## Visual design

| | Handheld (strip) | Keyboard panel (monitor-only) |
|---|---|---|
| Key height | 30 px min (strip ~170 px) | ~92 px (5 rows fill 480 px) |
| Letters / symbols | 17 px Noto Sans | 30 px Noto Sans semi-bold |
| Word keys (Esc, Tab, Enter, Ctrl, Alt, Space, Hide) | 12 px semi-bold | 12 px semi-bold (15 keys must fit 640 px; ⌫ is 22 px on the panel for the same reason) |
| Shoulder badges | 8 px semi-bold, top-right | 12 px |
| Corners / gaps | 5 px / 1 px | 8 px / 2 px |

Colours follow the Handtop theme (`~/.config/rg35xxh/theme`, re-read every time the keyboard is shown, so a theme switch needs no restart; `PALETTES` in `osk.py`):

| | Dark | Light |
|---|---|---|
| Background | `#141820` | `#d5dbe5` |
| Character keys (letters, digits, symbols, Space): key / border / text | `#2e3544` / `#3e4859` / `#eef0f4` | `#ffffff` / `#b9c1ce` / `#22262e` |
| Special keys (Tab, ⇧, Ctrl, Alt, ⌫, arrows, Hide): darker, bluer | `#1f2a3d` / `#2f4266` / `#a9c4f2` | `#dbe4f3` / `#a3b4d2` / `#2c4a7c` |
| Shoulder badge | `#8fb4ff` | `#3d68b0` |
| Press trace (dark, fades out) | `#0c1018`, border `#5b7bb0`, text `#8fb4ff` | `#9fadc4`, border `#3d68b0`, text `#14233f` |
| Highlight (blue) | `#3d5a8a`, border `#8fb4ff` | `#c9dbff`, border `#3d68b0`, text `#1a2a4a` |
| Latched modifier (amber) | `#6a4d1f`; highlighted `#8a6a2f` / `#ffd28f` | `#ffe2a8`; highlighted `#ffd28f` / `#8a6a2f` |

Blue and amber match the volume and brightness pop-up bars.

## Implementation notes

- GTK 3 window with gtk-layer-shell, namespace `rg35xxh-osk`, keyboard interactivity **none**, **overlay** layer. On the top layer it was hidden under the app launcher (nwg-drawer runs with `-ovl`, an overlay surface). Trade-off: with both open, the keyboard covers the launcher's bottom rows (fine: close the keyboard to reach them).
- Layer-shell properties (monitor, layer, anchors, exclusive zone) only apply when the window is mapped, so the window is re-mapped on every show. In panel mode it waits (up to 1.5 s) for the handheld output to appear before mapping.
- `visible` is tracked by the keyboard itself (`shown`), not by GTK, because in panel mode the window appears a moment after X is pressed and the D-pad must already be routed to the keyboard.
- Keys are emitted as complete taps (press + release) with the latched modifiers held around them.

## Ideas (not implemented)

- Bigger keys on the handheld-only strip, or a size setting in `input.conf`.
- Hold a key for its shifted character.
- Extra row or page with F1–F12, Esc, Home/End, PgUp/PgDn, Del.
- Remember the last highlighted key between shows.
- Non-Latin layouts (would need an input method; currently out of scope).
