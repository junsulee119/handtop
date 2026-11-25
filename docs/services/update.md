# Updates: worker, maintenance boot and recovery

Design and reasons: project doc `update-system.md`; external review and its triage: `update-review-2026-11-19.md`.
Archive and keys: [apt-repository.md](../apt-repository.md). The app on top of it: [../apps/update.md](../apps/update.md).

## Pieces

| File | Package | What it does |
|---|---|---|
| `/usr/local/sbin/handtop-update` | handtop-core | The worker. Every privileged step of an update. |
| `/usr/local/sbin/handtop-recovery` | handtop-core | Acts on `recovery.txt`. Standalone: doesn't use the worker it may need to undo. |
| `/usr/local/sbin/handtop-run` | handtop-core | Runs either tool if it passes its `--self-test`, else the last copy that did (`/var/lib/handtop-update/lkg/`). |
| `/etc/sudoers.d/rg35xxh-update` | handtop-core | Lets the Update app run `status`, `check`, `download`, `schedule [restart\|poweroff]`, `cancel`, `channel stable\|testing`. |
| `handtop-update-apply.service` | handtop-core | `handtop-update apply` in the maintenance boot (`TimeoutStartSec=120min`; the worker keeps its own 100 min budget). |
| `handtop-recovery.service` | handtop-core | `handtop-recovery` early in every boot when `recovery.txt` exists. |
| `handtop-update-boot-check.service` | handtop-core | `handtop-update boot-check` in every normal boot (below). |
| `/usr/share/keyrings/handtop-archive.asc`, `/etc/apt/sources.list.d/handtop.sources`, `/etc/apt/preferences.d/handtop.pref` | handtop-keyring | Archive key, stable source (never edited on the card), pin: Handtop's packages and FFmpeg build at 995, Debian's FFmpeg at -1. Never taken back by `handtop=previous`. |
| `/etc/apt/sources.list.d/handtop-testing.sources` | none | Written by `channel testing`, removed by `channel stable`. |
| `recovery.txt` on the boot partition | image | Recovery without screen or buttons (below). |

The boot logo and the Bluetooth start-up check don't run in the maintenance boot
(`ConditionPathIsSymbolicLink=!/system-update`), so the text console with the progress stays visible.

State in `/var/lib/handtop-update/`: `plan.json` (the exact plan, with an id), `schedule.json` (plan id,
restart or power-off afterwards, attempts, battery deferrals), `in-progress.json` (during an install),
`last-result.json`, `checked.json`, `cache/` (the plan's archives), `lists/` (the package lists the plan was
made from, hard links), `prefs.d/` (Debian-only plan), `previous/` and `previous.next/` (below), `lkg/`.
Logs: `/var/log/handtop-update/` (command output is written as it comes), and a short copy on the boot
partition as `logs\update-NNNNNN.txt` / `logs\recovery-NNNNNN.txt` (5 kept, best effort).

## Worker commands

All print JSON (errors too) and take a lock (`/run/handtop-update.lock`); apt's own locks still apply.

- `check`: `apt-get update --error-on=any` (any list that can't be refreshed makes the check fail), then a
  simulated `dist-upgrade`. If the plan has a modules package whose `Handtop-Kernel-SHA256` is not this card's
  `KERNEL` (`/etc/handtop/boot-abi`; a missing stamp counts as different), Handtop's packages and FFmpeg build
  are held back (`prefs.d/`) and only Debian's updates are planned (checked: the plan may then contain none of
  them): `new_image_needed` lists why. Holds are never changed by a check or download; held FFmpeg packages
  are reported as held. (Only `migrate` releases v0.4.x's FFmpeg holds, see docs/migrate.md.)
- `download`: needs a successful check from the last 24 h, and no scheduled update. Freezes the package
  lists, plans with them, refuses any removal, records every archive's size and hash from the signed
  indexes, checks free space (3 x the archives + 300 MB, and inodes), deletes damaged cached files (apt would
  reuse them by size), downloads, verifies every hash. If the plan changes Handtop's packages or FFmpeg
  build, it downloads the installed ones (but the keyring) into `previous.next/` and checks, without
  changing anything, that going back to them would satisfy every dependency after the update (`rollback`).
- `schedule [restart|poweroff]`: same plan again: only the choice changes. Refused when going back would not
  be possible, the release kept for going back is missing, incomplete or damaged (checked file by file, again
  right before the install starts), a file is damaged, space is short, the battery is under 40 % without the
  charger (an unreadable level counts as too low, and on the handheld a battery that hasn't shown up yet is
  unreadable; only a machine without a battery skips this), a controller mode runs or systemd can't say, `handtop-update-apply.service` isn't enabled,
  or `/system-update` belongs to another updater. Then the link, synced: the next start is the maintenance boot.
- `cancel`: forgets the plan, its archives, lists and staged release; `previous/` stays.
- `channel stable|testing`: cancels a downloaded or scheduled update, then writes or removes
  `handtop-testing.sources` (a fixed stanza). Packages from testing stay until stable has the same or newer.
- `status`: plan, scheduled, after, going back possible, kept release, last result, joypad override, channel.

## Maintenance boot

systemd sees `/system-update` and boots into `system-update.target`: no session, no input daemon, no
controller modes, no Wi-Fi. `handtop-update-apply.service` (through `handtop-run`):

1. does nothing if the link isn't Handtop's; finishes a cut promotion of the kept release;
2. if a final result for this scheduling is already recorded (cut after it; matched by the schedule's
   `gen`, not by the clock): only finishes (link, files, restart);
3. stops if the plan and schedule don't match or 3 attempts were made (the card then starts normally);
4. battery under 10 % without the charger, or unreadable after 20 s: switches off and keeps the plan
   (counted as a deferral; after 3 in a row the update is cancelled so the card can be used);
5. counts the attempt, writes `in-progress.json`, verifies every archive's hash, the free space and the
   staged release for going back;
6. installs a `policy-rc.d` that refuses service starts (an administrator's own is set aside and put back);
7. checks dpkg's state: before this plan has changed anything (`plan-changed.json`), no unfinished work
   at all is allowed (it would run unchecked); after a cut, only the plan's own packages at their old or
   planned version, plus trigger states. Then, only after a cut, `dpkg --configure -a` (allowed to fail:
   it can't configure packages whose siblings are still old). A modules update: the boot partition's
   `KERNEL` must be the one `boot-abi` names and the package is built for. Checks that what apt would do
   is part of the plan (same versions, nothing else, no removals, no configure-only work outside it;
   anything else: "the card changed since the download"). Only now are the first change recorded and
   `previous.next/` made the kept release (`previous/`): a refusal before this keeps the older kept
   release, which is then still the right one to go back to. Installs the plan's versions from
   `cache/` with the frozen lists (`--no-download --no-remove`, edited config files kept), `dpkg --configure
   -a` again (must pass), gives back apt's automatic marks, checks every version. A failure is retried once
   in place (not a changed card, a damaged file, or a time-out that left processes or dpkg's lock behind).
   apt runs dpkg without a PTY (`Dpkg::Use-Pty=0`), so a time-out stops dpkg with apt: its process group
   and every process below it (found before signalling), TERM then KILL;
8. records the result first (synced), then copies the log to the FAT, then removes the plan's files and the
   link, then restarts or powers off. If systemd refuses that request, it is forced.

A maintenance boot that is stopped (time-out, crash) leaves `in-progress.json`; systemd's own
`system-update-cleanup.service` removes the link and restarts, and the next normal boot's `boot-check`
records the interruption (with `dpkg --audit`) and removes the stale service blocker.

Power button: a long press is a hard cut by the power chip, not a clean shutdown; the next start resumes.

## recovery.txt

On the boot partition, editable from any PC; read (at most 64 KiB) early in every boot. The request is saved
in `/var/lib/handtop-update/recovery-request.json` before the file is set back to `none`, and a saved request
is finished after a power cut. A read-only FAT means nothing is acted on (the file couldn't be reset); so
does a missing one (the request waits for a start with the boot partition mounted, never "set back" in
the empty folder under the mount point).

| Line | Effect |
|---|---|
| `joypad=previous` | The patched joypad driver from before the last modules update (kept by the modules package in `/var/lib/handtop/modules/`, only when another version replaced it) goes to `/usr/lib/modules/<kernel>/updates/handtop-recovery/`; re-indexed and checked with `modinfo -n` (by file identity: kmod prints `/lib/modules`, the same folder); one restart. ROCKNIX's unpatched driver is never used. |
| `joypad=current` | Removes that override, re-indexes (always), checks; one restart. A later modules update does not remove it by itself. |
| `handtop=previous` | Schedules a maintenance boot that removes the Handtop packages the kept release doesn't have (first: one may Break the older packages), then reinstalls the kept release (Handtop's packages and FFmpeg build, hashes checked; also packages at the same version a cut left unfinished) with `dpkg -i`, then `apt-get check`. The keyring stays. A downloaded update is dropped. One restart. Before an update is scheduled, a trial checks the end state (versioned and virtual dependencies, Breaks / Conflicts both ways, the same removals); a Debian-only update checks the release already kept and the app says when going back won't work after it. |

Not covered: a broken `apt` / `dpkg` or a card that doesn't boot to userspace: reflash.

## boot-check (every normal boot)

Reports an interrupted maintenance boot (above), finishes a cut promotion of the kept release, removes a
stale `policy-rc.d` of ours, and keeps copies of `handtop-update` and `handtop-recovery` that pass their
self-test in `lkg/`, so a release that breaks either can still be undone.

## Tests

- `tools/update-test.sh` (root, on the build server, in a second checkout): a chroot copy of a finished rootfs,
  a local archive with a newer build of every Handtop package and of the FFmpeg family; covers the list
  above (exact plans, FFmpeg going back, damaged files, cuts, interruption, foreign link, battery, new image,
  channel, last-known-good copies). `HANDTOP_UPDATE_NO_POWER_ACTION`, `HANDTOP_UPDATE_CHROOT` and
  `HANDTOP_UPDATE_SYSFS` exist for it.
- QEMU (build server, Debian kernel): real maintenance boots, a power cut while installing, resume,
  `handtop=previous`, install and power off.
- The device: the same with real power cuts, the screen during the maintenance boot, the charger and fuel
  gauge at early boot, the regression list.

### Device test

`tools/update-device-archive.sh` (root, build server, second checkout) builds two releases from the checkout
into `work/device-archive`: `r1` (what 09b builds) and `r2` (newer, one changed script, release notes from a
test changelog). Serve the folder unprivileged (`python3 -m http.server 8088`), add it to the card as a
separate source (`/etc/apt/sources.list.d/handtop-devtest.sources`: `URIs: http://<server>:8088/current/`,
`Suites: ./`, `Trusted: yes`; Handtop's own source stays as shipped), install release 1, restart, point
`current` at `r2` and use the Update app. Delete the test source afterwards.

First run (2026-11-23, RG35XX H, step-4 card with Debian's sources on): check, download (23.5 MB),
Restart and install, maintenance boot, Handtop + 21 Debian updates installed, no failed units, log on the
FAT, release 1 kept for going back. Found two worker bugs the chroot test can't see (its Debian sources are
off): apt 3.0's `--print-uris` gives no hash for Debian's security archive and only MD5 elsewhere (the plan
now takes each archive's SHA-256 from `apt-cache show`), and the FFmpeg pin check read source priorities
instead of the version's pin.

Step 8 run (2026-11-24/25, RG35XX H DDR4, stock v0.4.1 card, final code after both review rounds):
- Migration, power cut in attempts 1, 2 and 3: the fourth start gave up and booted to the desktop with
  the plan kept (no package changed: the cuts came while the plan was being checked); the same command
  resumed exactly that plan, which installed (7 packages + FFmpeg, holds released, recovery.txt added,
  recovery unit fine with `WantsMountsFor`).
- `sudo` takes `schedule restart <12 hex digits>` and refuses a bad id or an extra word; the app's
  Restart and install sent the plan id.
- Update through the app (Handtop + Debian), then `handtop=previous` with a power cut in the middle of
  `dpkg -i` (6 packages unpacked): attempt 2 finished going back; keyring stayed new.
- Install and power off: installed, switched off, result "switching off".
- Observed: one attempt's log lost its text after the first line on a hard cut despite the 2 s fsync
  (zeros; the state files written the same way were intact): likely the SD card's write cache.
- Not tested on hardware: a DDR3 unit (none available; the image test covers its identification).
