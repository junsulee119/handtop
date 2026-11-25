# Release checklist

Before tagging a release and publishing its images. Copy the list into the release PR or issue and tick it off.

## Code and upstreams
- [ ] CI is green on the commit being released ([ci.md](ci.md)).
- [ ] The **"Upstream drift"** issue is closed, or every open line in it is decided: updated, or waived in `build/upstreams.conf` with a reason ([upstreams.md](upstreams.md)). Run the workflow by hand (Actions → Upstream drift → Run workflow) if the last weekly run is old.
- [ ] `CHANGELOG.md`: everything user-visible is under `## Unreleased`, then renamed to the version. **Say so when a release carries security fixes** (for example a newer FFmpeg base), because today handhelds only get them by reflashing.
- [ ] `RELEASE_VERSION` in `build/config.sh` is the new version.
- [ ] FFmpeg build changed (patch, patchset pin, `04c`, packaging) without a new Debian version: `FFMPEG_HANDTOP_REV` raised and recorded with `tools/ffmpeg-inputs.sh --update` (CI checks this).
- [ ] A Handtop package drops a file on purpose: it is listed in `build/pkg/removed-files.txt` (`tools/apt/repo.sh add` refuses unlisted drops).
- [ ] A release that moves files out of Handtop's packages, or that v0.4.x cards migrate to: `releases.tsv` regenerated from the release images' manifests (`tools/image-manifest.sh`, `tools/release-data.py`).

## Images
- [ ] DDR4 and DDR3 images built from the release commit ([building.md](building.md)); `.sha256` files next to them.
- [ ] The build's own gates passed (every step stops on a failed check; read the end of the log).

## On the device
- [ ] Flashed and booted on a DDR4 unit; DDR3 too when the release touches anything memory- or boot-related.
- [ ] The tests each merged PR listed for the device, repeated on the release image where they touch hardware, power, the session or controller modes ([hardware-safety.md](hardware-safety.md)).
- [ ] First boot after flashing: desktop, Wi-Fi import, Bluetooth (note the known first-boot issue if it shows).

## Publish
- [ ] Packages: `tools/apt/repo.sh add` + publish to `trixie-testing`, device test, promote to `trixie-stable`; `tools/apt/export.sh` (checks the remote, every signature and index hash before it copies).
- [ ] Tag, GitHub release with both images and their `.sha256`, release notes from the CHANGELOG.
