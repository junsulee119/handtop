# Updates: worker, maintenance boot and recovery

Design and reasons: project doc `update-system.md`. Archive and keys: [apt-repository.md](../apt-repository.md).

## Pieces

| File | Package | What it does |
|---|---|---|
| `/usr/local/sbin/handtop-update` | handtop-core | The worker. Every privileged step of an update. |
| `/etc/sudoers.d/rg35xxh-update` | handtop-core | Lets the Update app run `status`, `check`, `download`, `schedule`, `cancel` without a password. |
| `handtop-update-apply.service` | handtop-core | Runs `handtop-update apply` in the maintenance boot. |
| `handtop-recovery.service` | handtop-core | Runs `handtop-update recovery` early in every boot when `recovery.txt` exists. |
| `/usr/share/keyrings/handtop-archive.asc` | handtop-keyring | The archive's public key. |
| `/etc/apt/sources.list.d/handtop.sources` | handtop-keyring | `https://junsulee119.github.io/handtop-apt`, suite `trixie-stable`. Never edited on the card. |
| `/etc/apt/sources.list.d/handtop-testing.sources` | none | Written by `handtop-update channel testing`, removed by `channel stable`. |
| `/etc/apt/preferences.d/handtop.pref` | handtop-keyring | Handtop's packages and FFmpeg build at 995, Debian's FFmpeg at -1. With the pin in place the worker (`check`, `download`, after an install) and 09b release the FFmpeg holds of v0.4.x and 04c; a package script can't, dpkg holds the lock. |
| `recovery.txt` on the boot partition | image | Recovery without screen or buttons (below). |

State: `/var/lib/handtop-update/` (`plan.json`, `cache/`, `previous/` (release before the last update),
`attempts`, `after`, `last-result.json`).
Logs: `/var/log/handtop-update/`, and a short copy on the boot partition as `logs\update-NNNN.txt` /
`logs\recovery-NNNN.txt` (5 kept).

## Worker commands

All print JSON and take a lock (`/run/handtop-update.lock`); apt's own locks still apply.

- `check`: `apt-get update`, then a simulated `dist-upgrade`. Lists Handtop's and Debian's updates and
  `new_image_needed` (a modules package for another kernel than this card's: only reflashing helps).
- `download`: refuses an upgrade that would remove any package, or that needs a new image, or when
  free space is under about three times the download plus 300 MB. Downloads into `cache/`, checks every
  planned file is there, downloads the installed Handtop packages again into `previous/` (for
  `handtop=previous`), and saves the exact plan (package = version).
- `schedule [restart|poweroff]`: the plan's files are all there; battery at least 40 % or the charger connected (no battery
  reading counts as mains); no controller mode running. Then the `/system-update` link: the next start is
  the maintenance boot. `poweroff` ("Install and power off") switches the handheld off after the install,
  whether it worked or not (the Update app shows the result at the next start); `restart` (default) starts
  the desktop.
- `cancel`: removes the link, the plan and the cache.
- `channel stable|testing`: testing adds `handtop-testing.sources` (same archive, suite `trixie-testing`);
  stable removes it. Packages from testing stay until stable has the same or newer versions.
- `status`: downloaded / scheduled / last result / whether the joypad override is active.

## Maintenance boot

systemd sees `/system-update` and boots into `system-update.target` instead of the desktop: no session,
no input daemon, no controller modes, no Wi-Fi. `handtop-update-apply.service` then:

1. stops at once if the plan is missing or already failed 3 times (the card then starts normally);
2. under 10 % battery without the charger: powers off and keeps the link (the next start continues);
3. counts the attempt (before the work, so a power cut counts too);
4. installs a `policy-rc.d` that refuses service starts (the next normal boot starts everything);
5. `dpkg --configure -a` (allowed to fail: after a power cut it can't configure packages whose siblings are
   still old), then `apt-get install --no-download` of exactly the planned versions from `cache/`, keeping
   edited config files (`--force-confdef --force-confold`), then `dpkg --configure -a` again (must pass);
   a failure is retried once in place;
6. checks every package is at the planned version, records the result, removes the link and restarts or
   powers off, as chosen.

On a failure the link is removed too and the card starts normally (or powers off, if chosen) on whatever
is installed; the Update app shows the result. Text goes to the screen (tty1) and the journal. Holding Power still shuts down.
If the unit ends without restarting, systemd's own `system-update-cleanup.service` removes the link and
restarts.

## recovery.txt

On the boot partition, editable from any PC. Read early in every boot; each request is acted on once and
the file is set back to `none` *before* anything happens, so a mistake can't loop.

| Line | Effect |
|---|---|
| `joypad=previous` | The patched joypad driver from before the last modules update (kept by the modules package in `/var/lib/handtop/modules/`) goes to `/usr/lib/modules/<kernel>/updates/handtop-recovery/`, which depmod prefers; one restart. ROCKNIX's unpatched driver is never used. |
| `joypad=current` | Removes that override; one restart. A later modules update does not remove it by itself. |
| `handtop=previous` | Schedules a maintenance boot that reinstalls the Handtop packages kept in `previous/` (the release before the last update) with `dpkg -i`; one restart. Debian's packages are not taken back. |

## Tests

- `tools/update-test.sh` (root, on the build server, in a second checkout): a chroot copy of a finished
  rootfs, a local archive with a newer build of every Handtop package, then check / download / schedule /
  apply, `recovery.txt` both ways, a broken download and the attempt limit.
- QEMU (build server, Debian kernel, no root once the disk is made): first boot → check, download, schedule
  → maintenance boot → power cut while installing → resume (attempt 2) → `recovery.txt` `handtop=previous`
  → install and power off.
- The device: the same with real power cuts, plus the regression list.
