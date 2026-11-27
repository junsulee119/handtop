# Release checklist

Before tagging a release and publishing its images and packages. Copy the list into the release PR or
issue and tick it off. The order matters: the packages tested are the packages published (same bytes),
and they only carry the release version when the build runs on the tagged commit.

## Code and upstreams
- [ ] CI is green on the commit being released ([ci.md](ci.md)).
- [ ] The **"Upstream drift"** issue is closed, or every open line in it is decided: updated, or waived in `build/upstreams.conf` with a reason ([upstreams.md](upstreams.md)). Run the workflow by hand (Actions → Upstream drift → Run workflow) if the last weekly run is old.
- [ ] `CHANGELOG.md`: everything user-visible is under the new version's heading. Its first paragraph and the bold lead of each line become the Update app's release notes (`Handtop-Changes`). **Say so when a release carries security fixes.**
- [ ] `RELEASE_VERSION` in `build/config.sh` is the new version.
- [ ] FFmpeg build changed (patch, patchset pin, `04c`, packaging) without a new Debian version: `FFMPEG_HANDTOP_REV` raised and recorded with `tools/ffmpeg-inputs.sh --update` (CI checks this). Never record changed inputs under a released rev.
- [ ] A Handtop package drops a file on purpose: it is listed in `build/pkg/removed-files.txt` (`tools/apt/repo.sh add` refuses unlisted drops).
- [ ] Regenerate `releases.tsv` when a release moves files out of Handtop's packages or accepts migrations from v0.4.x. Use the release images' manifests (`tools/image-manifest.sh`) and the build's `/etc/handtop/boot-abi` with `tools/release-data.py`. The script uses `build/pkg/modules.txt` to include the stock module hashes.
- [ ] The release commit pushed to `main`; **tag it locally on the build server's checkout** (`git tag v<version>`), not yet on GitHub.

## Build (build server, on the tagged commit)
- [ ] Clean build from an empty `work/` (no reused rootfs), with `HANDTOP_RELEASE=1`: `09b` refuses an untagged commit, checks every Handtop package carries the version, and writes `work/pkg/packages.txt` (package, version, architecture, SHA-256 of Handtop's and Handtop's FFmpeg packages).
- [ ] DDR4 image, then DDR3 (steps 01, 02, 10 only: the same rootfs and packages); `.sha256` files next to them; keep `packages.txt` with them.
- [ ] The build's own gates passed (every step stops on a failed check; read the end of the log). `09b` checked each diverted file's Debian copy (`<path>.debian`).
- [ ] Root test round on the release commit: `tools/update-device-archive.sh`, `tools/migrate-test.sh` (v0.4.0, v0.4.1), `tools/update-test.sh` (includes `divert-test.sh`); `tools/apt/repo-test.sh`.

## Testing suite
- [ ] `repo.sh add` the packages in `packages.txt` (the image's own files), `repo.sh snapshot`, `repo.sh publish <snapshot> trixie-testing`; Jason signs (`sign.sh`); `export.sh --nonempty trixie-testing <checkout>`; Jason pushes; wait for Pages.
- [ ] `client-test.sh <url> trixie-testing work/pkg/packages.txt`: every package downloads from testing and is the tested bytes.
- [ ] Record the snapshot name and the handtop-apt commit.

## On the device (from testing)
- [ ] Flash the DDR4 image: first boot (desktop, Wi-Fi import, Bluetooth), the tests each merged PR listed for the device ([hardware-safety.md](hardware-safety.md)), Apps → Update → "up to date" on stable.
- [ ] DDR3 too when the release touches anything memory- or boot-related (or a community tester; say so in the notes if not tested).
- [ ] An update from the previous release on a card (flashed and, while v0.4.x cards migrate, migrated), then `handtop=previous` back to it and forward again.
- [ ] `joypad=previous` alone, then `joypad=current` alone: each restarts once and the expected driver is loaded.

## Stable suite
- [ ] `repo.sh publish <same snapshot> trixie-stable`; Jason signs; `export.sh --nonempty trixie-stable [--with-migrate] <checkout>`; Jason pushes; wait for Pages.
- [ ] `client-test.sh <url> trixie-stable work/pkg/packages.txt`.

## Migration command (while v0.4.x cards migrate)
- [ ] `repo.sh migrate`, Jason signs, `export.sh --with-migrate --nonempty trixie-stable <checkout>` (the published script must be this commit's), push.
- [ ] The literal one-line command from `docs/migrate.md`, unchanged, on a stock v0.4.0 and a stock v0.4.1 card: expected fingerprint, versions from stable, data kept, recovery works afterwards. Keep the card logs.

## Publish
- [ ] Push the tag; GitHub release with both images, their `.sha256` and `packages.txt`; release notes from the CHANGELOG (with the migration command and the archive fingerprint while v0.4.x cards migrate).
- [ ] The next re-sign date: 7 days before the deployed `Valid-Until` ([apt-repository.md](apt-repository.md#monthly-re-sign)).

## If a release has to be withdrawn
- Don't switch `trixie-stable` back to an older snapshot: that drops the withdrawn version's index entries (cards that installed it then can't stage it as their kept release), and apt's pin never downgrades cards that already have it.
- Instead publish a **corrective higher version** (the last good code, rebuilt as the next patch release), into a snapshot that still has every earlier version (retention: all released versions stay indexed), through testing to stable as usual; `client-test.sh` confirms cards pick it.
- Until then, cards can go back with `handtop=previous` (not a just-migrated card: it has no packaged predecessor until its first update). Say so in the release notes and the issue.
