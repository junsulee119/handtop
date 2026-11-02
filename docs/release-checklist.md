# Release checklist

Before tagging a release and publishing its images. Copy the list into the release PR or issue and tick it off.

## Code and upstreams
- [ ] CI is green on the commit being released ([ci.md](ci.md)).
- [ ] The **"Upstream drift"** issue is closed, or every open line in it is decided: updated, or waived in `build/upstreams.conf` with a reason ([upstreams.md](upstreams.md)). Run the workflow by hand (Actions → Upstream drift → Run workflow) if the last weekly run is old.
- [ ] `CHANGELOG.md`: everything user-visible is under `## Unreleased`, then renamed to the version. **Say so when a release carries security fixes** (for example a newer FFmpeg base), because today handhelds only get them by reflashing.
- [ ] `RELEASE_VERSION` in `build/config.sh` is the new version.

## Images
- [ ] DDR4 and DDR3 images built from the release commit ([building.md](building.md)); `.sha256` files next to them.
- [ ] The build's own gates passed (every step stops on a failed check; read the end of the log).

## On the device
- [ ] Flashed and booted on a DDR4 unit; DDR3 too when the release touches anything memory- or boot-related.
- [ ] The tests each merged PR listed for the device, repeated on the release image where they touch hardware, power, the session or controller modes ([hardware-safety.md](hardware-safety.md)).
- [ ] First boot after flashing: desktop, Wi-Fi import, Bluetooth (note the known first-boot issue if it shows).

## Publish
- [ ] Tag, GitHub release with both images and their `.sha256`, release notes from the CHANGELOG.
