# On-Screen Keyboard

Design of the built-in on-screen keyboard (OSK). It is part of the input daemon (`src/inputd/rg35xxh_inputd/osk.py`), so the daemon always knows whether it is open and can route the D-pad and A to it.

## Goals

- Type anywhere (terminal, browser, dialogs) with only the handheld's controls.
- Never steal keyboard focus: keys are sent through the daemon's virtual keyboard to whatever window is focused.
- US layout only (CJK text is display-only; no input method).

## Controls

| Control | Action |
|---|---|
| X | Show / hide the keyboard |
| D-pad | Move the highlight (auto-repeat when held: 0.4 s delay, then every 0.09 s) |
| A | Type the highlighted key (the button bound to `click_left`; A by default) |
| L1 / R1 / R2 | Esc / Enter / Backspace (physical shortcuts still work while it is open) |
| Left stick | Still moves the pointer; keys can also be clicked with the pointer |
| Hide key | Same as X |

Moving up/down keeps the horizontal position (picks the key whose centre is closest). Left/right wraps around within a row. The highlight starts on `g`.

## Layout

Five rows, 12 columns (US):

```
`  1  2  3  4  5  6  7  8  9  0  ⌫
Tab q  w  e  r  t  y  u  i  o  p  -
a  s  d  f  g  h  j  k  l  ;  '  \
⇧  z  x  c  v  b  n  m  ,  .  /  ↑
Ctrl Alt [ Space ×3 ] =  [  ]  ←  ↓  →  Hide
```

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
| Key height | 30 px min | ~92 px (5 rows fill 480 px) |
| Letters / symbols | 13 px Noto Sans | 24 px Noto Sans semi-bold |
| Word keys (Tab, Ctrl, Alt, Space, Hide) | 13 px | 14 px semi-bold (so 12 columns fit 640 px) |
| Corners / gaps | 5 px / 1 px | 8 px / 2 px |

Colours: background `#141820`, keys `#2b3240` with `#3a4456` border, text `#e8eaee`; highlight `#3d5a8a` / `#8fb4ff` (blue); latched modifier `#6a4d1f` (amber), highlighted + latched `#8a6a2f` / `#ffd28f`. Same palette as the volume (blue) and brightness (amber) pop-up bars.

## Implementation notes

- GTK 3 window with gtk-layer-shell, namespace `rg35xxh-osk`, keyboard interactivity **none**.
- Layer-shell properties (monitor, layer, anchors, exclusive zone) only apply when the window is mapped, so the window is re-mapped on every show. In panel mode it waits (up to 1.5 s) for the handheld output to appear before mapping.
- `visible` is tracked by the keyboard itself (`shown`), not by GTK, because in panel mode the window appears a moment after X is pressed and the D-pad must already be routed to the keyboard.
- Keys are emitted as complete taps (press + release) with the latched modifiers held around them.

## Ideas (not implemented)

- Bigger keys on the handheld-only strip, or a size setting in `input.conf`.
- Hold a key for its shifted character; key repeat while A is held (useful for ⌫ and arrows).
- Extra row or page with F1–F12, Esc, Home/End, PgUp/PgDn, Del.
- Remember the last highlighted key between shows.
- Non-Latin layouts (would need an input method; currently out of scope).
