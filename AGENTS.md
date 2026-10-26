# AGENTS.md

Guide for coding agents and contributors working on Handtop. Read it before you change anything. It also applies to pull requests written by hand.

Handtop is a Debian 13 (arm64) desktop for the Anbernic RG35XX H: ROCKNIX's kernel, U-Boot, device trees and firmware, a Debian userspace, labwc + Waybar + nwg-drawer + wlogout at 640×480, and a custom input daemon that turns the gamepad into a mouse and keyboard. Start with [README.md](README.md) and [docs/README.md](docs/README.md).

## Read this first: hardware safety

Code here runs on a handheld with a fragile kernel driver stack. A careless change to anything that **holds hardware** (gamepad, vibration motor, power button, USB gadget, Bluetooth / Wi-Fi radio, framebuffer, backlight, CPU cores), **changes power states**, or **starts and stops the processes that do** can freeze the whole device. It has happened. After a forced power-off, the power chip can then stay latched until the battery is physically disconnected.

- Follow **[docs/hardware-safety.md](docs/hardware-safety.md)** and go through its checklist for every such change. Copy the checklist into the PR description with your answers.
- Read the per-component rules before editing a component, for example "Stopping, restarting, one instance" in [docs/services/input-daemon.md](docs/services/input-daemon.md).
- Never write to the power chip, regulators or charging limits (`axp*`, `regulator`, `input_current_limit`, `/dev/mem`, `i2cset`).
- Never run the input daemon, or anything that opens `/dev/input` or `/dev/uinput`, inside the build chroot or on the build host.

## Trade-offs: ask before you implement

When a fix or a design choice works against intended behaviour or makes the experience worse, **stop before implementing it**: describe the trade-off to the user or maintainer and let them decide. This covers, for example:

- a feature that is lost or limited;
- an extra step, a slower path or a new confirmation;
- a changed default;
- something on screen that gets hidden or covered;
- a cost in battery life, memory or speed.

A safety fix is no exception: it is still their call how much experience to give up for it. Lay out the options, including keeping the current behaviour, with what each costs, and recommend one. In a PR, list every trade-off under its own heading in the description, with the decision and who made it; never let one slip in silently. Record accepted trade-offs in the component's doc (for example: with both open, the on-screen keyboard covers the launcher's bottom rows).

## Repository layout

| Path | What |
|---|---|
| `build/` | Image build: numbered steps `00`–`10`, run by `build-rootfs.sh` then `10-image.sh`; settings in `config.sh`; package lists in `packages/`; helpers in `lib/` (`safety.sh`) |
| `overlay/` | Files copied as-is into the root filesystem (`/etc`, `/usr/local/bin`, `/usr/local/sbin`, systemd units, udev rules, icons) |
| `src/inputd/` | Input daemon (Python): `core.py` (pure logic, unit-tested), `daemon.py` (devices, motor, modes), `ui.py` + `osk.py` (on-screen keyboard and other windows, in a separate process), `config.py`, `tests/` |
| `src/osd/`, `src/bootsplash/` | Small C programs (volume / brightness bar, boot screen), cross-compiled by the build |
| `tools/` | Test helpers (QEMU, headless screenshots); `tools/icons/`: generators for all pixel-art icons, cursors, logo and wallpapers |
| `docs/` | One document per app or background service, plus general topics |
| `boot-files/`, `media/` | Boot partition files; logo and README images |
| `CHANGELOG.md` | User-facing changes, newest first, under `## Unreleased` |

## Build and test

- Build (Debian/Ubuntu host, root, about 20 GB free): `sudo bash build/build-rootfs.sh && sudo bash build/10-image.sh`. For DDR3 units, re-run `01`, `02` and `10` with `RAM_TYPE=DDR3`. Details: [docs/building.md](docs/building.md). Windows cannot build the image.
- Input daemon unit tests (no hardware needed): `cd src/inputd && python3 -m pytest -q tests`. All must pass.
- Without the device: `tools/qemu-test.sh`, `tools/headless-test.sh`, `tools/waybar-test.sh`, `tools/osk-test.sh`.
- Shell scripts that run as `/bin/sh` run under **dash**: check them with `dash -n` and test them with `dash`, not bash (`kill -- -PGID` fails there, for example).
- Python: `python3 -m py_compile` on every file you touch.
- **On the device:** anything that touches hardware, power, the session or controller modes must be tested on a real RG35XX H before it is merged. Say in the PR what you tested, on which unit (DDR4 or DDR3) and how. Test the stop and start paths by hand first, run `sync` before a test that may freeze the device, and if it does freeze, keep the card and read its journal (`/var/log/journal`) before re-flashing.

## Conventions

**Files on the device**
- Install with explicit modes (`install -m644` / `-m755`). Copies that keep modes (`tar`, `cp -p`) from a Windows checkout can make configs unreadable.
- `.gitattributes` enforces LF line endings. New executable scripts need the executable bit in git (`git add --chmod=+x`).
- System-wide defaults go in `/etc/xdg/` or `/etc/rg35xxh/`; users override in `~/.config/`. Boot-partition files (FAT, editable from Windows) override `/etc` copies where documented.
- Runtime flags and sockets go in `$XDG_RUNTIME_DIR` (session) or `/run` (system); logs in `~/.local/state/session/`.

**Session and processes**
- The labwc autostart (`overlay/etc/xdg/labwc/autostart`) starts every session helper. Read its comments before adding one, and make sure a log-out can stop it (see the hardware safety rules).
- Signal Waybar (`SIGRTMIN+N`) only when it has been running for at least 3 s, as the existing senders do.
- Find processes by exact command line, PID file or lock, never by a loose `pkill -f` prefix.
- Python GUI code uses `GLib.MainLoop`, never `Gtk.main()`. Keep GTK out of processes that hold hardware.

**Look and feel**
- Every user-facing app and icon has a **dark and a light** version (`rg35xxh-theme`, `~/.config/rg35xxh/theme`).
- Icons are **pixel art generated by scripts** in `tools/icons/`, never hand-edited PNGs. Change the generator, re-run it, and commit both. Document new generators in `tools/icons/README.md`.
- Screen size is 640×480; every UI must be usable with the D-pad and A alone.

**Docs and changelog**
- Each app or service has its own doc under `docs/apps/` or `docs/services/`; add one for a new component and link it from `docs/README.md`.
- Update the docs in the same PR as the code. Record why a choice was made and what was tried and rejected, not only what the code does.
- User-visible changes get a line under `## Unreleased` in `CHANGELOG.md`.
- Never put credentials (Wi-Fi passwords, SSH keys, tokens) in the repo, the docs or logs.

**Commits and PRs**
- Commit subject: `Area: what changed` (for example `Input daemon: …`, `Session: …`, `build: …`, `Docs: …`), under about 90 characters.
- Commit body: the problem, the cause, the fix (one bullet per change), and **how it was tested** (on the device or not).
- One topic per PR. Don't mix a refactor with a behaviour change.
- The PR description includes: what and why; **trade-offs** and who decided them (see "Trade-offs: ask before you implement"); how it was tested (unit tests, QEMU or headless, device model); the hardware-safety checklist with answers, if the change touches anything listed under "Read this first".

## Do not

- Do not delete files outside `work/` from build scripts (use `safe_rm`); no `rm` inside chroot commands.
- Do not add endless or rapidly re-uploaded vibration effects; all vibration goes through the input daemon's motor gate.
- Do not start a second instance of something that owns a device, and do not kill a hardware owner without waiting for it to exit.
- Do not merge hardware-facing changes that were only tested in QEMU or headless.
- Do not implement a trade-off against intended behaviour or the user experience without the user's or maintainer's decision.
