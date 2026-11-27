# Updates: internals and invariants

For anyone changing the update system: the worker, recovery, the migration, the packages, the archive or their tests.

- **[update.md](update.md)** describes what the pieces do.
- **This file** says what must stay true, why, where the code enforces it, and which test covers it.
- **What users see:** [../apps/update.md](../apps/update.md) and [../migrate.md](../migrate.md).
- **Archive and release steps:** [../apt-repository.md](../apt-repository.md) and [../release-checklist.md](../release-checklist.md).

The update system is the one part of Handtop that must not break. A broken app is fixed by the next update. A broken update path can only be fixed by reflashing, and v0.4.x cards had no update path at all. Every rule below comes from a real bug: found in review (seven external review rounds, findings #1–#125), in the chroot tests, or on the handheld.

## Contents

1. [Rules for any change](#rules-for-any-change)
2. [State on the card](#state-on-the-card)
3. [Invariants](#invariants)
4. [Power cuts: where each step can stop](#power-cuts-where-each-step-can-stop)
5. [Going back (`handtop=previous`)](#going-back)
6. [The migration from v0.4.x](#the-migration-from-v04x)
7. [Packages, archive and releases](#packages-archive-and-releases)
8. [Tests](#tests)
9. [Decisions and their reasons](#decisions-and-their-reasons)
10. [Known limits](#known-limits)
11. [Bug patterns that came back more than once](#bug-patterns-that-came-back-more-than-once)

## Rules for any change

1. **Assume a power cut between any two writes.** The battery can die, and a long press of the power button is a hard cut by the power chip. Every state change is one of these:
   - a `write_json` (temp file, fsync, rename, fsync of the folder);
   - a rename;
   - a journal written *before* the change it describes.

   Go through [../reliability-checklist.md](../reliability-checklist.md) for every write you add.
2. **Before the first package change, refuse; after it, finish.** Anything that can go wrong is checked before the plan's first change is recorded (`mark_changed`, `plan-changed.json`). After that point, only resuming the same plan is allowed: no new decisions, no re-planning.
3. **A state file belongs to one plan and one scheduling.** Results, cleanup records and journals carry the plan `id`, and where it matters the schedule's `gen`. Never act on a file that belongs to another plan or an older scheduling. This went wrong four times (#34, #91, #104, #113).
4. **The worker never trusts the clock.** The card has no RTC battery worth trusting: match by `gen`, never by time.
5. **Never trust a path's spelling.**
   - `/lib` is a link to `usr/lib`: compare files by identity (`os.path.samefile`), and check diversions and ownership under every `/usr` alias (#70, #75).
   - The FAT boot partitions of all Handtop images share one serial number: check that the boot partition is on the same disk as `/` (#115).
6. **Unreadable is not absent.** A file that exists but can't be read, a query that fails, or a listing that fails means: wait, or refuse. Never treat it as "nothing there" (#105, #111, #116, #117).
7. **Run the affected root test suite** (see [Tests](#tests)) for any change to the worker, recovery, migration or packaging. CI alone doesn't cover them. Run the full round before every release.
8. **Raise trade-offs first** (`AGENTS.md`). The refusals below are deliberate trade-offs: don't remove one to make a case "work" without asking.

## State on the card

Everything is in `/var/lib/handtop-update/` unless noted. W = written by, R = read by.

| File | Contents | W | R | Notes |
|---|---|---|---|---|
| `plan.json` | the exact plan: `id`, `kind` (`update` / `recovery` / `migrate`), packages with old/new versions and SHA-256, `remove`, `rollback`, migration data | download, migrate, recovery | everything | frozen; never edited after it's made |
| `schedule.json` | `plan`, `after` (restart / poweroff), `attempts`, `deferrals`, `gen`, `first_scheduled` | schedule, recovery | apply, status | a new `gen` on every scheduling |
| `in-progress.json` | `plan`, `gen`, start | apply | boot-check | there = a maintenance boot was stopped |
| `plan-changed.json` | `plan` | apply (`mark_changed`) | dpkg checks, cancel | written right before the first package change; strict checks before it, plan-only after |
| `last-result.json` | `ok`, message, notes, `gen`, `final`, `migrated_from`, … | finish, boot-check | app, apply replay | written first, synced, before any cleanup |
| `cleanup.json` | `plan`, `gen`, `ok`, `keep_plan` | `complete` | `finish_cleanup` | deletes only what still belongs to that plan and gen (#91, #104, #113) |
| `cache/`, `lists/`, `prefs.d/` | the plan's archives, the frozen package lists, holds for a "new image needed" plan | download | apply | |
| `previous/` | the kept release for going back: `manifest.json` (`release`, `complete`, packages with hashes, `for_plan`) + .debs | promote | recovery | the keyring is never in it |
| `previous.next/` | the release staged at download for this plan | download | promote | becomes `previous/` only after the last check before the first change |
| `previous.old/` | the release kept before the promotion | promote | settle, recovery | kept until the update settles: a failed update that didn't change Handtop goes back to it (#102) |
| `previous.drop/` | a kept release being deleted | settle | repair | renamed first, deleted after: a cut never leaves neither |
| `later-edits.json` | migration: `files`, `recreated`, `deleted_done` | `later_edits` | install_migrate | user edits made after the plan was approved (#64, #114, #123) |
| `boot-files-pending.json` | `release`, `files`, `ident` (rootfix, kernel, uuid, plan) | migrate_boot_files | boot-check | FAT files a migration couldn't write yet |
| `migrate-holds.json` | the FFmpeg holds the migration released | migrate | cancel, abandon, finish | restored on cancel, abandon and terminal failure |
| `migrate-undo/` | the bootstrap's undo record: `orig/`, `ABSENT`, `share/` + `share-absent`, `share-new`, `dropin-*`, `apply-enabled`, `consented` | `handtop-migrate` | `handtop-migrate` | written complete before its first change; dropped once consented, scheduled or installed |
| `recovery-request.json` | `joypad`, `handtop`, `acked`, `src` (SHA-256 of the file it came from), `id` | handtop-recovery | handtop-recovery | saved before `recovery.txt` is reset |
| `no-predecessor` | marker: nothing can be kept to go back to | migrate | status | the first update after a migration |
| `lkg/` | the last worker and recovery copies that passed their self-test | boot-check | handtop-run | |
| `checked.json`, `fat-seq` | the last check's time; FAT log numbering | | | |

Also:

- `/system-update`: a link to `/var/lib/handtop-update`. It is ours only when it points exactly there. `/etc/system-update` is always another updater's.
- `/run/handtop-update.lock`: the worker's lock. Recovery takes it too.
- `/var/backups/handtop-migrate/`: files the migration replaced.
- `/var/log/handtop-update/`, plus short copies on the FAT under `logs/`.

## Invariants

Each one with where it's enforced. "Test" names a check in the root harnesses.

| # | Invariant | Where | Test |
|---|---|---|---|
| I1 | Only the planned versions get installed; nothing else, no removals (except recovery's planned ones) | `check_against_plan` (apt simulation incl. `Conf` lines), `--no-download --no-remove`, version check after | update-test |
| I2 | Every archive matches the SHA-256 from the signed index, checked at download, at schedule and again at apply | download / schedule / apply | update-test (damaged file) |
| I3 | Nothing unfinished in dpkg runs unchecked: before the first change, no pending work at all (error flags included); after a cut, only the plan's packages | `dpkg_state_check`, `pending_state` | update-test |
| I4 | An update that changes Handtop's packages or FFmpeg has a complete kept release, checked file by file, before it can be scheduled and before it starts | `check_kept_release`, `trial_rollback` | update-test |
| I5 | The kept release is replaced only after the last check before the first change | `install_update` (promotion moved there, #66) | update-test |
| I6 | The keyring is never taken back or kept for going back | `NEVER_ROLLED_BACK` in both tools, `settle_previous` | update-test |
| I7 | The maintenance boot never runs a service start (`policy-rc.d`); a user's own `policy-rc.d` is put back | `policy_rc` | update-test |
| I8 | At most 3 attempts per scheduling; battery deferrals capped at 3; then the card starts normally | `cmd_apply` | update-test |
| I9 | The result is recorded (synced) before the log copy, the cleanup and the restart; a replay with the same `gen` only finishes | `finish`, `cmd_apply` | update-test |
| I10 | A time-out stops apt, dpkg and every descendant (no PTY, process group plus the descendants found before signalling); a held lock is `Stuck`, never retried in place | `_stop_group`, `Stuck`, `APT_CONF` | update-test |
| I11 | Edited config files are kept (`--force-confold`); the package version goes next to them as `.dpkg-dist` and is listed | apt options, `kept_config` | update-test |
| I12 | Going back runs only from a healthy card, with no foreign architecture | `handtop_previous`, `install_recovery` | update-test |
| I13 | A request in `recovery.txt` is acted on once: saved, then reset on the mounted FAT, then acted on | `handtop-recovery:main` | update-test |
| I14 | The migration never runs unsigned or changes anything before consent that it can't put back | `docs/migrate.md` command, `migrate-undo/` | migrate-test |
| I15 | A kept migration plan is discarded only by `abandon-migration`; download and channel refuse meanwhile | `kept_migration`, `refuse_if_migration_kept` | migrate-test |
| I16 | FFmpeg's v0.4.x holds are released only while a migration is scheduled, and put back on cancel, abandon or terminal failure | `restore_legacy_holds` | migrate-test |
| I17 | Boot partition files are written only on this card's own mounted FAT (same disk as `/`, its rootfix and KERNEL); otherwise they wait | `migrate_boot_files`, `fat_on_root_disk` | migrate-test; device |
| I18 | `handtop-recovery` doesn't use the worker, and `handtop-run` falls back to the last copy that passed its self-test | `handtop-run`, `lkg/` | update-test |
| I19 | Published bytes are the tested bytes: one version, one set of bytes, forever | `09b` `packages.txt`, `client-test.sh`, `verify-tree.py` | repo-test, release checklist |
| I20 | Every released Handtop version stays in the archive's index | retention decision, `repo.sh` | release checklist |

## Power cuts: where each step can stop

How each part of an update ends when it's cut at each point.

**Download and schedule (in the desktop).**

- Nothing changes packages here. A cut leaves a partial `cache/` or `previous.next/`: download checks hashes and deletes damaged files, and schedule re-verifies everything.
- The `/system-update` link is created last, synced.

**Maintenance boot (`cmd_apply`).**

1. **Before `mark_changed`:** refusals leave the card unchanged, and the older kept release is still in `previous/`.
2. **After `mark_changed`:** each later boot resumes the same plan:
   - `dpkg --configure -a`; the first one may fail while siblings are old;
   - the same `apt` install with `--no-download`;
   - `--configure -a` again, which must pass.
3. **A cut after the result is written:** the next boot sees a final result with the same `gen` and only finishes.
4. **A cut during cleanup:** `cleanup.json` makes the next start (apply, schedule or boot-check) finish it, for that plan and gen only.
5. **Stopped (time-out, crash):** systemd's `system-update-cleanup.service` removes the link. Boot-check finds `in-progress.json` and records "stopped" with `dpkg --audit`.

**Kept release.** `promote_previous` and `settle_previous` use renames: `previous` → `previous.old` → `previous.drop`. `repair_previous` (worker and recovery) finishes a cut rename. Never two deletes in a row.

**Recovery.**

- The request is saved, then `recovery.txt` is reset, then the plan and schedule are written: a cut repeats only the missing step.
- An unacknowledged request whose `recovery.txt` changed on a PC uses the newer file. If the new file says `none`, the request is cancelled (#106).

**Migration.** See [the migration section](#the-migration-from-v04x).

## Going back

`handtop=previous` in `recovery.txt` → `handtop-recovery` (early boot) → a `recovery` plan → maintenance boot → `install_recovery`.

**Refused before anything changes**, all in `handtop_previous`:

- no complete kept release, or a damaged file in it;
- dpkg has unfinished work outside the packages going back replaces or removes, the keyring included;
- a foreign architecture is registered;
- another updater's marker is there;
- nothing would change.

**Which release it goes back to.** If the newer kept release equals what's installed (an update failed before changing Handtop) and `previous.old/` is complete, it uses `previous.old/`. That swap happens only after all refusals (#110).

**In the maintenance boot**, `install_recovery`:

1. checks dpkg's state again;
2. runs the live trial: dependencies, virtual names, Breaks / Conflicts, each kept package's Pre-Depends at install time (healthy packages only, versioned provides);
3. recomputes the removals and compares them with the plan;
4. checks that the kept packages the plan leaves alone are still at their kept version (#112);
5. runs one time-budget check;
6. records the first change;
7. `dpkg --configure -a` and the state check again;
8. `dpkg --remove --force-depends --force-remove-reinstreq` of the added packages, first, because one may Break the older ones;
9. `dpkg -i` of the kept files, then `--configure -a`, then `apt-get check`;
10. verifies the **whole** kept release.

**After a cut part-way:** the packages still to remove only need to be part of the planned list (#121).

**Known false refusal (#124):** an unchanged kept package can veto an OR alternative that's satisfied elsewhere. It's safe, but it refuses a rollback that would work.

**joypad.** `joypad=previous` / `joypad=current` put a copy of the driver into `updates/handtop-recovery/`, or take it out. `depmod`, then `modinfo -n` is checked by file identity. One restart. Tested by hand on every release.

## The migration from v0.4.x

**1. The signed one-liner** (`docs/migrate.md`):

- downloads `handtop-migrate`, its `.asc` and the key into a fresh folder under `/run`;
- requires `sqv`'s output to equal the fingerprint `EF04B02F6569FB6FC8EAF9C5F5962C429E9C69FF`;
- only then runs it.

The key apt trusts afterwards is the one inside the signed script.

**2. `tools/apt/handtop-migrate`:**

- `flock` on `/run/handtop-migrate.lock` (the log copier closes that fd);
- writes the undo record `migrate-undo/`, complete, in `.tmp` first, then renamed; the share-folder snapshot is staged, then published (#122);
- installs the key, the source and the pin; installs the worker from `handtop-core` (downloaded, not installed as a package); runs `handtop-update migrate`, which plans and downloads;
- shows the plan; on yes, writes `consented`, then `schedule restart <id>`.

Before `consented`, any stop puts everything back (`undo`), and the next run puts back a killed run's changes first. After `consented`, the record is only dropped, because the packages now own those files (#84).

**3. The worker's migrate plan:**

- **Identification (`identify`):**
  - at least 90 % of the release's files match;
  - no file only another release has;
  - at most 2 % of the release's own files missing;
  - `rootfix.cpio` matches one of its variants.

  Anything else is refused as "mixed".
- **`adoption`:** stock files, files the user changed (backed up to `/var/backups/handtop-migrate`), deleted config files, mode changes, legacy FFmpeg files (`x` rows).
- **`later_edits` before every attempt:** a stock file the user changed after approving keeps the user's version. A deleted config file stays deleted, and one the user made again stays.

**4. Terminal failure.**

- The plan is kept, FFmpeg is held again, and `download` / `channel` refuse.
- The same command resumes it: `repair` first, then schedule with the same id.
- `abandon-migration` (root) gives up: holds are put back first, and the plan is kept if that fails (#117).

**5. After the install:**

- the recovery units must be linked from `sysinit.target.wants` / `multi-user.target.wants` (#118, #125);
- the boot-partition files are written, or left pending;
- legacy FFmpeg files are removed: only unowned, unchanged ones, never through a symlinked folder (#75).

**Release data.** `overlay/usr/local/share/handtop/releases.tsv` comes from `tools/release-data.py`, from each released image's manifest (`tools/image-manifest.sh`). It must cover every file a Handtop package ships, or a stock file is reported as changed. v0.5.0 missed the kernel modules; fixed in v0.5.1.

## Packages, archive and releases

**Packages** (`build/09b-packages.sh`, `build/pkg/`):

- `handtop-core`, `-desktop`, `-video`, `-keyring`, `-modules-h700-<kernel>`, `-platform-h700`, the `handtop` metapackage, and FFmpeg's 17 Debian-named packages `+handtop<rev>` (`04c`).
- Every file the build adds outside Debian's packages is classified in `classes.txt`; 09b stops on an unclassified file. A **clean** build found the SSH host keys this way: they existed only on a fresh rootfs.
- Files Handtop replaces in Debian packages use `dpkg-divert --no-rename`, with Debian's copy kept as `<path>.debian` (`diversions.txt`; #8, #62). `tools/divert-test.sh` covers the transitions.
- A file dropped on purpose must be listed in `removed-files.txt`, or `repo.sh add` refuses.
- **Version:** `RELEASE_VERSION`, and only on a tagged HEAD with `HANDTOP_RELEASE=1`. Otherwise `+<date>.g<hash>` (#81).
- **FFmpeg:** a changed build needs a higher `FFMPEG_HANDTOP_REV`, recorded with `tools/ffmpeg-inputs.sh --update`. CI checks it. Never record changed inputs under a released revision.

**Archive** (`junsulee119/handtop-apt` on GitHub Pages; [../apt-repository.md](../apt-repository.md)):

- Suites `trixie-testing` and `trixie-stable`; promotion means publishing the same aptly snapshot to stable.
- `Valid-Until` is 30 days. **Re-sign 7 days before it** (missed, every card's checks fail).
- `verify-tree.py` checks the signed tree, and `export.sh` copies it into the Pages checkout and checks it again:
  - signatures, fields and validity;
  - every listed index form with its SHA256 and SHA512 by-hash objects;
  - every pool file, nothing extra, and the signed migration files.
- `client-test.sh` checks the live site with a cold apt: the bytes and the versions a card picks.
- Pages caches up to 10 minutes: a check right after a push can still see the old index.

**Withdrawal.** Never switch a suite back to an older snapshot. Cards that installed the version would lose its index entry and couldn't keep it for going back. Publish a corrective higher version instead.

**Release order** ([../release-checklist.md](../release-checklist.md)):

1. tag locally;
2. clean build;
3. root round on the release build;
4. testing;
5. device tests;
6. stable plus migration files;
7. the literal command on stock v0.4.0 and v0.4.1 cards;
8. push the tag, GitHub release.

## Tests

| Suite | Where | Covers | Run when |
|---|---|---|---|
| `tools/ci-checks.sh` | anywhere | syntax, shellcheck, py_compile, unit tests | every change |
| `tools/apt/repo-test.sh` | anywhere with aptly + gpg | sign, export, verify-tree, client-test (good and bad trees) | archive tools |
| `tools/update-test.sh` (+ `divert-test.sh`) | root, build server, a finished build's rootfs | the worker and recovery in a chroot: plans, damaged files, cuts, replays, rollback, joypad requests, channels | worker, recovery, packaging |
| `tools/migrate-test.sh` | root, build server, a released v0.4.x image | the bootstrap and the migration on each image: refusals, undo, killed runs, kept plans, repair, later edits, holds, units | migration |
| `tools/update-device-archive.sh` | root, build server | two releases (`r1`, `r2` = `+t2`) to serve on the LAN for a device test | device tests |
| Device | the handheld | everything the chroot can't: real maintenance boots and power cuts, the FAT, the screen, battery, joypad | every release |

**Facts about the harnesses:**

- **One build server runs them in parallel** (both migrate tests plus update-test, about 45 minutes). Each uses its own `WORK` folder. The round is done only when every suite has printed its result, not when the first one does.
- **Chroot binds** of `/dev`, `/dev/pts` and `/sys` must be `rslave`. With shared propagation, a test's unmount once took away the build server's own `/dev/pts`. `chroot_umount` refuses to unmount below a `/dev` that still propagates.
- **A run that finds mounts left by another refuses.** Wait for the other run's cleanup.
- **Kill only your own processes.** A test that kills processes must filter by `/proc/PID/root`: the parallel run executes the same script.
- **No `grep -q` at the end of a pipe under `pipefail`.** SIGPIPE upstream turns a match into a failure: use `grep … >/dev/null` or a herestring.

**Device test of a release** (v0.5.0, 2026-11-26):

1. Flash the image; check the first boot.
2. Update to `+t2` served from the LAN, with the release kept from testing.
3. `handtop=previous` back, then forward again.
4. `joypad=previous` on its own, then `joypad=current` on its own.
5. The literal migration command on a stock v0.4.1 and a stock v0.4.0 card.

## Decisions and their reasons

Jason's, with dates; don't re-argue without new facts.

- **2026-11-18, design.**
  - Applied at restart in a maintenance boot, never in the running desktop.
  - FFmpeg as Debian-named packages from Debian's source.
  - Offline primary key with a signing subkey.
  - Checks only when the app is opened.
  - The boot layer (kernel, U-Boot, DTB, `cma=`) stays reflash-only.
- **2026-11-23.**
  - Going back is required: an update is scheduled only with a complete kept release. The exception is the first update after a migration.
  - `recovery.txt` covers the joypad and Handtop's packages.
  - A broken apt or dpkg means reflashing.
- **2026-11-25.**
  - One release for images, stable and the migration (v0.5.0).
  - Keep the user's newest edit (#64).
  - A kept migration is discarded only by an explicit abandon (#63).
  - Keep every release indexed.
  - Re-sign 7 days ahead, by Jason only.
  - Root tests only for worker, migration or packaging changes; the full round per release.
  - Going back only from a healthy card, refusing the rest instead of handling it (round 5).
- **2026-11-26.**
  - No more external review rounds after batch M: the device tests were the final check.
  - #124 deferred.
  - The v0.5.0 release build resumed at 09b after the classes fix (same code otherwise).
  - The false module notice shipped as a known issue, fixed in v0.5.1.

## Known limits

In the v0.5.0 release notes.

- **Going back.**
  - It needs a healthy card and no foreign architecture.
  - An interrupted update that can't finish needs a reflash.
  - A just-migrated card has no packaged predecessor until its first update.
  - A slow card's maintenance boot can time out (100 minutes for the worker).
- **The app's result page** shows at most eight kept config files and six notes. The full result is in `last-result.json`.
- **Migration.**
  - Leave room for files edited after approving.
  - Finish other package work first.
  - Identification: a 90 % match, 2 % of the release's own files may be missing.
- **Custom changes** to how the recovery units start are undone by the migration.
- **Builders** need a clean, isolated environment, and must check the archive at every step in the checklist.

## Bug patterns that came back more than once

Check new code against these first.

1. **Acting on someone else's state.** A cleanup, result, replay or journal from another plan or an older scheduling (#34, #91, #104, #113). Bind to `plan` + `gen`.
2. **Deciding before refusing.** A side effect, like a swap, a hold release or a deletion, placed before a later refusal (#66, #110). Do every check first, then change.
3. **Treating "can't tell" as "no".** Failed queries, unreadable files, a FAT that isn't mounted (#71, #105, #111, #116, #117).
4. **One step of two.** A delete followed by a record, or a copy followed by a publish, cut in the middle (#102, #114, #122, #123). Record first, or rename first, then finish idempotently.
5. **Path and identity.** `/lib` vs `/usr/lib`, symlinked parents, diversion aliases, identical FAT serials (#70, #75, #115).
6. **Shell pipelines.** `grep -q` under `pipefail`, unchecked `find` in a process substitution, `pkill -f` matching your own command line (#80, #117).
7. **Fixes introducing the next bug.** Rounds 4–7 found mostly bugs in the previous round's fixes. Re-run the affected suite and read the changed lines once more only for failure paths.
