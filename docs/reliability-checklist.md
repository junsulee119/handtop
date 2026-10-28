# Reliability checklist: scenarios to think through before a PR

Handtop runs on a handheld that people switch off by holding Power, move between cards, and edit from Windows. Code that works on the happy path can still leave a unit that doesn't boot, a file half-written, or a restart loop. Before opening a PR, go through the scenarios below for every piece the change touches, and **write the relevant ones with your answers in the PR description** (a line each is enough: "power cut during X → Y").

This is about software reliability in general. Changes that hold hardware, change power states, or start/stop those processes also need the [hardware-safety checklist](hardware-safety.md).

Where these come from: the log-out freeze (2026-10-26), the hardware review that followed, and the final sweep of the screen panel check (`rg35xxh-panel`, 2026-10-28), which found four error paths that the tests had not covered.

## 1. Interrupted at the worst moment

- [ ] **Power cut** (battery, hold Power) at every step that writes. What is on the card afterwards? Write to a temporary file, `fsync`, check it, then rename over the target, then sync the directory. Never edit a file the boot depends on in place. A leftover temporary file from an earlier cut must not break the next run.
- [ ] **Stopped mid-way** by `SIGTERM`: a shutdown, a log-out, a restart started by something else, a systemd timeout. Does the next run pick up cleanly?
- [ ] **A restart you trigger** must not cut off other jobs that are running at that moment: first-boot jobs (root resize, swap file, SSH keys), the Wi-Fi import, anything writing to the same partition. Order after them, or wait for them.

## 2. Running more than once

- [ ] **Run twice, or after a partial run**: same result, no duplicates, no growing files (idempotent).
- [ ] **Two at the same time** (session restart, user runs it by hand): lock, or prove it can't happen.
- [ ] **Anything that restarts the device, the session or a service**: what if the condition that triggered it is still there afterwards? There must be a **loop guard** (act once, then log and stop until things look normal again). A detection that flips between boots must not restart the device forever.

## 3. First boot, every boot, upgrades

- [ ] **First boot vs later boots**: what has not happened yet on the first boot (root not resized, no SSH keys, Wi-Fi not imported, no `~/.config`)?
- [ ] **Boot time and session start**: does it delay the desktop? Measure it (`journalctl -o short-monotonic`). If users pay for it (seconds, an extra restart), it's a trade-off: tell Jason before implementing (see `AGENTS.md`).
- [ ] **Older installs and images**: files from an earlier version, missing new files, user settings in the old format. It must do nothing harmful when its own files are absent.

## 4. Inputs you don't control

- [ ] **Files missing, empty, unreadable or corrupt**: each must lead to "nothing changed, and it says so", never to a crash halfway through.
- [ ] **Files edited on Windows** (boot partition): CRLF, a UTF-8 BOM, odd capitals, extra spaces, comments, an unknown value. Fall back to the default and log it.
- [ ] **Files the user changed by hand**: if you can't recognise a file, leave it alone; don't overwrite the user's choice.
- [ ] **Disk full**: the boot partition is 256 MB FAT; the root can fill up too.
- [ ] **No time yet**: the clock may be wrong early in boot or without network; don't rely on it for decisions.

## 5. Hardware and units differ

- [ ] **Other units**: DDR3 vs DDR4 images, the regular vs rev6 screen panel, other H700 models if it could run there. Don't assume your unit is the only kind.
- [ ] **A card moved to another handheld**: anything decided once on the first boot may be wrong on the next unit. Prefer checking on every boot, cheaply.
- [ ] **A reading that fails, or isn't stable** (GPIO, sysfs, a sensor): read more than once, and treat "can't tell" as "change nothing".
- [ ] **Devices that appear late or not at all**: Bluetooth adapter, monitor, USB device, D-Bus service, NetworkManager. Check when you use it, with a timeout.

## 6. The system around it

- [ ] **Every subprocess and blocking call has a timeout**, and its failure is caught (`OSError`, `SubprocessError`, non-zero exit).
- [ ] **Unexpected exceptions**: catch at the top, log where a user can see it, and leave the system as it was.
- [ ] **Session events**: log-out, suspend and resume, Screen off, HDMI plugged or unplugged, low battery (20 % warning, 5 % shutdown) while your code runs.
- [ ] **SD-card wear**: nothing written on every boot or every few seconds when nothing changed.

## 7. Seeing and fixing failures

- [ ] **Where does a user see that it failed?** Without SSH, `logs\` on the boot partition is the only place readable from Windows. Log the decisions that matter there (short, size-capped, CRLF), everything else to the journal.
- [ ] **Recovery from a PC**: if this goes wrong and the unit doesn't boot or shows nothing, what does the user copy or edit on `RG35XXHBOOT` to fix it? Document it.
- [ ] **An override**: if automatic detection can be wrong, the user needs a simple way to force the answer (e.g. `panel.txt`).

## 8. Proving it

- [ ] **Tests for each scenario above that applies**, with test hooks (environment variables for paths, fake readings, dry run) so they run without hardware: see `tools/test-*.sh`.
- [ ] **On the device, both directions**: switch and switch back, start and stop, plug and unplug. Not only the path you expect users to take.
- [ ] **A last sweep before the PR**: read the code once more only for failure paths (what if this line raises?). That pass found real bugs where the tests were green.
