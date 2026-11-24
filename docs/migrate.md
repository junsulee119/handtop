# Moving a v0.4.0 or v0.4.1 card onto updates

Cards flashed with Handtop v0.4.0 or v0.4.1 were made before Handtop had packages: apt and the Update
app don't know their Handtop files. This one-time step moves such a card onto Handtop's packages, so
it gets updates from **Apps → Update** from then on, without reflashing. Cards flashed with v0.5.0 or
later don't need it.

**Kept:** Wi-Fi networks and passwords, the home folder, the apps' settings (themes, Controls profiles,
media), SSH keys and the SSH choice, Tailscale, the services you turned on or off, your own packages and
holds.

## Before you start

- **Charge** the handheld (or plug in the charger). The install itself takes a few minutes.
- **Wi-Fi** connected; about 20–40 MB is downloaded (more when Debian has updates waiting).
- A **Terminal** on the handheld (Apps → Terminal, with the on-screen keyboard), or **SSH** from a PC
  (power menu → Enable SSH; set a password first, `passwd`).

## The command

Copy it from the release notes, or type it as is (one line):

```sh
cd ~ && if curl -fsSL --remote-name-all https://junsulee119.github.io/handtop-apt/migrate/{handtop-migrate,handtop-migrate.asc,handtop-archive.asc} && sqv --keyring handtop-archive.asc handtop-migrate.asc handtop-migrate | grep -qx EF04B02F6569FB6FC8EAF9C5F5962C429E9C69FF; then sudo bash handtop-migrate; else echo "Download or signature check failed: nothing was changed."; fi
```

It downloads the script, its signature and Handtop's public key, and runs the script only if it is
signed by Handtop's archive key (fingerprint `EF04B02F6569FB6FC8EAF9C5F5962C429E9C69FF`, also in the
README). `sqv` is the signature checker apt itself uses; it prints the key that made the signature.
`sudo` asks for your password.

## What happens

1. **Checks** that this is an RG35XX H with Debian 13 and Handtop v0.4.x, not moved yet. Anything else:
   it stops and changes nothing.
2. **Adds** Handtop's archive key, package source and FFmpeg pin (the files the `handtop-keyring`
   package ships), and takes the update helper out of the release's `handtop-core` package.
3. **Plans and downloads** everything and checks each file's SHA-256 against the signed indexes. It
   names the card it found (release and DDR3 / DDR4) and lists what you changed:
   - a **config file** you edited (in `/etc`) stays as you made it; Handtop's new version goes next to
     it as `.dpkg-dist`;
   - **another Handtop file** you changed is replaced by Handtop's version; your copy is saved in
     `/var/backups/handtop-migrate`.
   Files that are as v0.4.0 or v0.4.1 shipped them are simply updated.
4. **Asks** before going on. Saying no cancels the download; nothing was installed.
5. **Restarts** into the maintenance boot: text on the screen, no desktop, a few minutes. A power cut
   resumes at the next start. Then the desktop starts as usual, and Apps → Update shows the result.

During the install it also writes `/etc/handtop/boot-abi` and `/etc/handtop/model`, adds
`recovery.txt` to the boot partition, and on a v0.4.0 card turns the old active
`rg35xxh-input.conf` into the commented-out rescue file of v0.4.1 (the old one is kept as
`rg35xxh-input.conf.v0.4.0`; a file you edited stays as it is).

`handtop=previous` in `recovery.txt` can't go back to v0.4.x (it had no packages): it goes back to the
release the move installed, from the first update after the move on (tested on a real v0.4.1 card).

## If something goes wrong

- Before the restart nothing on the card has changed except Handtop's key, source and pin, and the
  update helper's files. Run the command again.
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
