# Controls

**Apps → Controls** (`rg35xxh-controls`): every setting of the input daemon in one app (buttons, pointer, scrolling, sticks, vibration, timing), plus button combinations, macros and profiles. Changes apply within a second, no re-login. Code: `src/controls/handtop_controls` (installed to `/usr/local/lib/rg35xxh-controls`); the settings themselves are the input daemon's ([../services/input-daemon.md](../services/input-daemon.md), "Settings layers and live reload").

## Main page

Two tabs (640×480, everything reachable with the pointer and A; L1 (Esc) or ‹ Back goes back from a sub-page). The tab row also holds the **Profile** picker and **Advanced ›**.

- **Buttons:** the External Controller status screen's pixel-art handheld at 2×, in the current theme's handheld colours (the drawing is shared: `handtop_controls/art.py`, also used by `rg35xxh-controller-screen`). The button under the pointer lights up as pressed when it can be changed (not when the boot partition file locks it, nor in rescue mode); click it to pick its action:
  - Left / right / middle click, Back / Forward (mouse), Copy, Paste, On-screen keyboard, Gamepad mode, Power menu, Nothing
  - **A key…** (Esc, Enter, arrows, F1–F12, letters, digits …), **Key combination…** (tick Ctrl / Alt / Shift / Super, pick the key), **Open an app…** (the app drawer's apps), **Run a macro…**, **Record macro (start / pause)**
- **Pointer & more:** pointer speed, acceleration (Off / Normal / Precise), scroll speed (**Try…** opens the scroll test page), natural scrolling, gamepad buttons (by position: bottom = Xbox A, as before / by label: A = A, local gamepad mode only), vibration (buzzes at each value as you set it, also while dragging), Re-center sticks.
- **Every slider** has a number box with − / + beside it: drag, step, or type a value (X opens the on-screen keyboard). Sliders and number boxes ignore the right stick's scrolling, so scrolling a page can't change a value by accident.
- **Scroll test page:** scroll speed and natural scrolling at the top; below, left an article that scrolls up and down only (headings, paragraphs, drawn pictures, a list), right a 2200×2200 px plan (lettered / numbered blocks and pins) that scrolls every way (`scrolltest.py`). Scroll speed applies while its slider is dragged.

## Advanced

Sections on the left:

| Section | What |
|---|---|
| More buttons | D-pad up / down / left / right (default "Move the pointer"), Volume + / −, a tap of F, a tap of Power. Desktop mode only; each change warns first. **Fixed:** holding Power to shut down, F + Volume = brightness, the D-pad moving between keys while the on-screen keyboard is open, and gamepad / External Controller modes. |
| Combinations | first + second button → an action (below) |
| Macros | step lists, built here or recorded (below) |
| Pointer | D-pad speed (share of the stick's top speed), acceleration curve in detail (Off / Normal / Precise = 1 / 2 / 3), speed on a monitor (100 % = as far across a big screen as across the handheld's), a test area with ten dots to click |
| Sticks | both sticks live (the input daemon's stick feed, only while this section is shown): the dead zone drawn hatched with its size, the dot grey while inside it; dead zone, swap sticks, invert each axis, Re-center |
| Scrolling | scroll curve (higher: a small push already scrolls quickly; 0: even), the scroll test page |
| Timing | hold Start to leave gamepad mode; Power: hold to shut down and the longest tap (a tap is kept at least 0.5 s shorter than the hold, so the power menu stays reachable); Volume repeat delay and speed |
| Profiles | Use (on trial, below), New, Duplicate, Rename (the on-screen keyboard comes up for names), Delete (not the profile in use), Export / Import as a `.conf` file |
| Reset | this profile, or everything (the other profiles are deleted once the reset is kept) |

## Safety: trial, warnings, rescue

- **"Keep these controls?"** with a 15 s countdown after any change to buttons, combinations, how the pointer moves (speed, acceleration, D-pad speed, dead zone, swap sticks, axis inversion), a profile switch or a reset. The change runs as a trial file; without **Keep** it is undone, by the input daemon itself, so it is undone even if the app is gone or the button needed to press Keep was the one mapped away. Tested: A → Nothing, left to run out; Keep saved Y → Ctrl + C.
- **Minimal controls** (the input daemon's `config.minimal_problems()`): a change that leaves no left click on any button, or a pointer that hardly moves with the stick and the D-pad (all four directions), gets a warning first ("This leaves you without basic controls", Cancel selected), then the countdown.
- **Boot partition file** (`rg35xxh-input.conf`, editable from Windows): shipped all commented out. A line you uncomment wins over the app; the app shows that setting locked. **Controls broken?** Uncomment `use_app_settings = no` at the top: everything the app saved is ignored (not deleted) until the `#` is back; the app then shows a rescue-mode banner and edits nothing.
- **Vibration preview:** the input daemon re-uploads the mode-change buzz at the new strength (motor idle, desktop mode, at most every 0.3 s) and plays it. Low values are below what the motor can spin up (felt from about 40 %), which the preview makes obvious (decision 2026-11-16: no rescaling).

## Combinations

Hold the first button, press the second: the combination's action runs instead of the second button's (decision 2026-11-17, "hold-modifier style"). The first button's own action then runs only when it is **tapped alone, on release**, so it can no longer be held down (a drag with A, a held key); the app warns the first time a button with a click or key becomes a first button.

- First: A B X Y, L1 R1 L2 R2, L3 R3, Select, Start, F. Second: the same without F, plus the D-pad directions. Power and Volume can't be part of one; F + Volume stays brightness.
- Desktop mode only; off while the on-screen keyboard is open.
- Stored as `first+second = action` lines in the profile's `[desktop]` section (e.g. `select+start = macro_record`).

## Macros

A macro is a text file, `~/.config/rg35xxh/controls/macros/<name>.macro`, shared by every profile. A button or combination set to **Run a macro** plays it; pressing it again stops it. While it runs, a notification says "Running macro <name>" (it stays until the end) and turns into "Macro <name> finished" or "… stopped".

Steps (one per line, `#` starts a comment; the editor writes them, friendly key names such as "Enter" or "Ctrl+C" are accepted there):

| Step | Meaning |
|---|---|
| `key KEY_ENTER` / `combo KEY_LEFTCTRL+KEY_C` | tap a key / keys together (2–4) |
| `down KEY_LEFTSHIFT` / `up KEY_LEFTSHIFT` | hold / let go of a key |
| `click left` / `press left` / `release left` | tap / hold / let go of a mouse button (left, right, middle, back, forward) |
| `text hello` | type it (US layout; characters without a US key are skipped) |
| `wait 0.25` | pause, 0.01–10 s |
| `move 40 -12` | move the pointer by x, y |
| `scroll -120 0` | wheel: vertical, horizontal (120 = one notch, + = up / right) |
| `launch chromium` | open an app (its `.desktop` file name) |
| `do copy` | copy, paste, osk_toggle, power_menu, volume_up / _down, brightness_up / _down |

Limits keep a bad file harmless: at most 1000 steps and 300 s of waiting in all; a bad line is skipped (and logged by the input daemon); anything the macro holds down is let go at the end, when stopped, on a switch to gamepad mode and when the daemon exits. A macro can't switch to gamepad mode or start another macro.

**Recording** (decisions 2026-11-17):
1. Give a button or combination the action **Record macro (start / pause)** (Select + Start works well).
2. Advanced → Macros → **Record…**: a name, **Include pointer movement** (saved as relative "move by x, y" steps: playback repeats them from wherever the pointer is, so it matches only from the same starting point; off by default) and **Keep the timing between steps** (on by default; off: the steps play back to back).
3. In any app, tap the record button to start, again to pause, again to go on (a notification shows each state).
4. Back in Controls → Macros: **Stop and save** (or Cancel). Then Edit it like any macro.

Captured: keys and key combinations (including what is typed on the on-screen keyboard), mouse buttons, scrolling, opened apps, copy / paste and the other actions above, and the waits between them (paused time is not a wait). A key or button pressed and let go with nothing between becomes one tap; pointer motion and scrolling are merged per 0.1 s. How it works: the app writes `$XDG_RUNTIME_DIR/rg35xxh-macro-rec.json` (arm / stop / cancel), the input daemon records what it sends while recording and reports in `rg35xxh-macro-rec.status`.

## Files

| Path | What |
|---|---|
| `~/.config/rg35xxh/controls/<profile>.conf` | a profile: only what differs from `/etc/rg35xxh/input.conf` (INI, same keys) |
| `~/.config/rg35xxh/controls/active` | the profile in use (one line; `default` if missing) |
| `~/.config/rg35xxh/controls/macros/<name>.macro` | macros |
| `$XDG_RUNTIME_DIR/rg35xxh-controls-trial.conf` | a change on trial (deleted by the daemon when its time is up) |
| `$XDG_RUNTIME_DIR/rg35xxh-controls-sticks(.want)` | the live stick feed (Sticks section) |
| `$XDG_RUNTIME_DIR/rg35xxh-haptic-preview` | vibration preview request |
| `$XDG_RUNTIME_DIR/rg35xxh-macro-rec.json`, `.status` | macro recording |

One window at a time (`$XDG_RUNTIME_DIR/rg35xxh-controls.lock`). Re-center sticks stays its own app too ([recenter-sticks.md](recenter-sticks.md)).

## Themes

Follows the current theme like every Handtop app (GTK widgets; the handheld drawing in the theme's `status.*` colours; highlights in `status.lit`). Checked on the device in all nine built-in themes (main tabs), and the Advanced sections in Handtop dark, High contrast, Retro, Pocket and Signal; High contrast's larger text fits. App icon `rg35xxh-controls` in every built-in theme's own style: Handtop dark / light (`tools/icons/gen_app_icons.py`), Retro, Glass, Pocket, Signal (`tools/themes/gen_*.py`), Grayscale (`gen_grayscale.py`); Debian and High contrast use their base theme's, as for the other Handtop apps. A v0.4.0 theme file without it still imports (the slot falls back to the base theme).

## Tests

`src/controls/tests` (profiles, trials, export / import, action names) and the input daemon's `src/inputd/tests` (layers, live reload, trial expiry, the new bindings, combinations, macros, recording), both run by CI and the image build.
