# Moving a v0.4.0 or v0.4.1 card onto updates

Cards flashed with Handtop v0.4.0 or v0.4.1 were made before Handtop had packages: apt and the Update
app don't know their Handtop files. This one-time step moves such a card onto Handtop's packages, so
it gets updates from **Apps → Update** from then on, without reflashing. Cards flashed with v0.5.0 or
later don't need it.

**Kept:** Wi-Fi networks and passwords, the home folder, the apps' settings (themes, Controls profiles,
media), SSH keys and the SSH choice, Tailscale, the services you turned on or off, your own packages and
holds. (The holds v0.4.x put on its FFmpeg libraries are released: Handtop's FFmpeg packages replace them.)

## Before you start

- **Charge** the handheld (or plug in the charger). The install itself takes a few minutes.
- **Wi-Fi** connected; about 20–40 MB is downloaded (more when Debian has updates waiting).
- A **Terminal** on the handheld (Apps → Terminal, with the on-screen keyboard), or **SSH** from a PC
  (power menu → Enable SSH; set a password first, `passwd`).

## The command

Copy it from the release notes, or type it as is (one line):

```sh
sudo bash -euc 'trap "echo Download or signature check failed: nothing was changed." ERR; d=$(mktemp -d /run/handtop-migrate.XXXXXX); cd "$d"; for f in handtop-migrate handtop-migrate.asc handtop-archive.asc; do curl -fsSL --proto =https -o "$f" "https://junsulee119.github.io/handtop-apt/migrate/$f"; done; s=$(sqv --keyring handtop-archive.asc handtop-migrate.asc handtop-migrate); [ "$s" = EF04B02F6569FB6FC8EAF9C5F5962C429E9C69FF ]; trap - ERR; bash ./handtop-migrate'
```

`sudo` asks for your password first. The rest runs as root in a new private folder under `/run`, so
nothing else on the handheld can change the files between the check and the run. It downloads the
script, its signature and Handtop's public key one at a time (a failed download stops it), and runs
the script only if `sqv`, the signature checker apt itself uses, says it was signed by Handtop's
archive key (fingerprint `EF04B02F6569FB6FC8EAF9C5F5962C429E9C69FF`, also in the README). If any
step fails it stops without changing anything. The key apt will trust from then on is the one inside
the signed script, not the downloaded key file.

## What happens

1. **Checks** that this is an RG35XX H with Debian 13 and Handtop v0.4.x, not moved yet. The release is
   recognised from Handtop's files: the files only that release has must be there (at most 2 % of them
   may be missing: deleted ones come back), not one file only the other release has may be, and the boot
   partition's `rootfix.cpio` must be there and be that release's (DDR3 or DDR4). A card that mixes releases is
   refused: changed files couldn't be told apart, so reflashing v0.5.0 is safer. Anything else: it stops
   and changes nothing.
2. **Adds** Handtop's archive key, package source and FFmpeg pin (the files the `handtop-keyring`
   package ships), and takes the update helper out of the release's `handtop-core` package.
3. **Plans and downloads** everything and checks each file's SHA-256 against the signed indexes. It
   names the card it found (release and DDR3 / DDR4) and lists what you changed:
   - a **config file** you edited (in `/etc`) stays as you made it; Handtop's new version goes next to
     it as `.dpkg-dist`;
   - **another Handtop file** you changed is replaced by Handtop's version; your copy is saved in
     `/var/backups/handtop-migrate`.
   Files that are as v0.4.0 or v0.4.1 shipped them are simply updated.
4. **Asks** before going on. Saying no (or stopping it, or any error up to here) puts back everything
   the script changed: the key, source and pin files as they were, the FFmpeg holds, and the update
   helper's files; nothing was installed.
5. **Restarts** into the maintenance boot: text on the screen, no desktop, a few minutes. A power cut
   resumes at the next start. Then the desktop starts as usual, and Apps → Update shows the result.

During the install it also writes `/etc/handtop/boot-abi` and `/etc/handtop/model`, adds
`recovery.txt` to the boot partition, and on a v0.4.0 card turns the old active
`rg35xxh-input.conf` into the commented-out rescue file of v0.4.1 (the old one is kept as
`rg35xxh-input.conf.v0.4.0`; a file you edited stays as it is).

`handtop=previous` in `recovery.txt` can't go back to v0.4.x (it had no packages): it goes back to the
release the move installed, from the first update after the move on (tested on a real v0.4.1 card).

## If something goes wrong

- Before the restart: anything the script changed is put back when it stops. Run the command again.
- If the install in the maintenance boot fails (twice in a row, or three power cuts), the card starts
  normally again and **the downloaded move is kept**: Apps → Update shows **Resume the move**, and running
  the same command again offers it too: that exact move (same packages, same decisions about your files;
  files that went missing or got damaged meanwhile are fetched again and checked against the plan).
  Until then the Update app doesn't download updates or switch channels, so nothing replaces the kept
  move. FFmpeg is held again meanwhile, as on v0.4.x.
- A file you change after answering yes (for example between two attempts) keeps your version: a config
  file stays as you made it (Handtop's next to it as `.dpkg-dist`), another file is saved in
  `/var/backups/handtop-migrate` as `<name>.changed-after-plan`. The result lists them.
- To give a kept move up instead: `sudo /usr/local/sbin/handtop-update abandon-migration` (the plan and
  downloads go, FFmpeg is held again as before). Packages it already installed stay; if the card doesn't
  work properly then, flash v0.5.0.
- A power cut before you answered: the next run of the command first puts back what the interrupted run
  changed, then starts over. What happened is in the log on the
  boot partition. If the boot partition couldn't be written during the install, `recovery.txt` (and on
  v0.4.0 the input file) are written at a later start.
- The log is `/var/log/handtop-migrate.log`; the maintenance boot's log is copied to the boot partition
  (`logs\update-NNNNNN.txt`, readable from a PC).
- If the desktop doesn't come back, `recovery.txt` on the boot partition offers `joypad=previous`;
  otherwise reflash v0.5.0 (`docs/flashing.md`).

## For maintainers

- The script is `tools/apt/handtop-migrate`; the work is the update worker's `migrate` plan
  (`overlay/usr/local/sbin/handtop-update`, docs/services/update.md). It identifies the card by
  comparing its Handtop files with `overlay/usr/local/share/handtop/releases.tsv`, made by
  `tools/release-data.py` from the release images' file lists (`tools/image-manifest.sh`). A new
  migratable release needs its images added there.
- Publishing: `tools/apt/repo.sh migrate` puts the script and the public key in `public/migrate/`,
  `tools/apt/sign.sh` signs it (detached), `tools/apt/export.sh` copies it to `handtop-apt`. The
  migration installs `handtop` from `trixie-stable`, so publish the release there first.
- Test: `tools/migrate-test.sh <image.img.xz>` (root, build server, second checkout, after
  `tools/update-device-archive.sh`) moves a chroot copy of a release image with one edited config
  file and one edited Handtop file; then the real thing on a freshly flashed card.
