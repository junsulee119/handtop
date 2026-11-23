# Update

**Apps → Update** (`rg35xxh-update`): checks for, downloads and installs updates to Handtop and Debian.
Updates are installed while the handheld restarts (a maintenance boot), never while it is in use.
Code: `src/update/handtop_update` (installed to `/usr/local/lib/rg35xxh-update`). Every privileged step
is the update worker's (`/usr/local/sbin/handtop-update`, through sudo): [../services/update.md](../services/update.md).

Updates are checked only when the app is opened (decision 2026-11-18); nothing runs in the background.

## Pages

640x480, everything reachable with the pointer (stick / D-pad) and A; B (Escape) goes back.

- **Main:** the installed release (`0.5.0`, or `0.5.0 (dev build)`) and the channel; the last result when
  there is one: the update failed or was stopped (red, with a pointer to `recovery.txt`), or which edited
  settings files were kept (the package's version saved next to each as `.dpkg-dist`). **Check for
  updates** (waits up to 30 s for the clock to be set over the network: signatures need the right time;
  a clock before 2026 is reported instead of checking), **Advanced ›**.
- **Results:** "Everything is up to date", or Handtop's new release with its short notes (they come with
  the signed package lists: the `handtop` package's `Handtop-Changes` field, from `CHANGELOG.md`), a notice
  when that release needs a new image (only Debian's updates are offered then), Debian's updates as a
  count (**Show** lists name, old → new). **Download (size)**. A server that can't be reached is named
  ("Couldn't reach every update server (Debian security)"), never reported as "no updates".
- **Downloading:** progress from the finished files in the cache, then "Checking the files and keeping the
  current release for going back".
- **Ready to install:** what is downloaded and whether going back will be possible; **Restart and
  install** (the desktop comes back), **Install and power off**, **Cancel update**, **Advanced ›**. A
  refusal (battery under 40 % without the charger, a controller mode running, damaged files) is shown
  on the page.
- **Scheduled:** "The update installs at the next restart": **Restart now**, **Cancel update**.
- **Advanced:** the channel (Stable / Testing; switching cancels a downloaded update; packages from
  testing stay until stable catches up), the release kept for going back, and what `recovery.txt` can do.
- **Another update is waiting:** a different program scheduled an offline update (`/system-update`); the
  app leaves it alone.

One window at a time (`$XDG_RUNTIME_DIR/rg35xxh-update.lock`).

## Taskbar badge

`image#update` in Waybar (`rg35xxh-update-badge`), left of the input-mode icon, only while there is
something to see; clicking it opens the app:

| Icon | When |
|---|---|
| `update` | an update is downloaded, or installs at the next restart |
| `update-failed` | the last update failed or was stopped, until the app has shown it (`~/.config/rg35xxh/update-seen`) |

It reads the worker's state files (no sudo) every 2 minutes; the app sends Waybar `SIGRTMIN+11` after
each change. The icons are theme slots (`icons/taskbar/update.png`, `update-failed.png`, optional; a theme
without them gets Handtop's).

## Icons

The app icon (`apps/update`) and both badges are drawn for every built-in theme: Handtop dark / light
(an open parcel with the accent arrow going in, `tools/icons/gen_update_icons.py`), Retro (an installer
window with a progress bar and a green arrow), Glass (line glyph: an arrow into a tray), Pocket (a
cartridge labelled with a parcel), Signal (a black tray, red arrow), Grayscale (from Handtop dark).
Debian and High contrast use Handtop's.

## Testing

- `src/update/tests` (pytest): what the pages show, from the worker's JSON.
- `HANDTOP_UPDATE_FAKE=<scenario> rg35xxh-update [--page results|list|advanced]`: canned worker answers
  (`idle`, `updates`, `uptodate`, `newimage`, `offline`, `ready`, `scheduled`, `failed`, `done`, `advanced`,
  `battery`, `clock`). `tools/update-app-shots.sh` takes them in all nine themes.
- The real path: [../services/update.md](../services/update.md), "Tests".
