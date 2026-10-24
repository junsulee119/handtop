# Files and drives

**Files** (Thunar) with click-to-mount for other drives: a card in the second slot (TF2) or USB sticks.

## Use

- Other drives appear under **Devices** in Thunar's sidebar. Tap one to mount it (no password), at `/media/<user>/<label>`. The ⏏ button unmounts it; then the card or stick can be pulled out.
- The kernel reads exFAT, FAT, ext4, NTFS and btrfs, so e.g. a Knulli card's SHARE partition works.
- Plugging a drive in shows a toast ("SD card inserted" / "USB drive inserted", size in GiB and volumes); tapping it opens Files. Pulling it out shows "SD card removed", or "removed without ejecting" with a warning if a volume was still mounted.
- Handtop's own card (boot and root partitions) is not listed, so it cannot be ejected by mistake.

## How it works

- **Packages:** `udisks2` (mounting, allowed for the active local session by polkit), `gvfs` (shows the drives in Thunar), `exfatprogs` + `dosfstools` (check / format exFAT and FAT), `eject` (USB sticks).
- **Hidden partitions:** `/etc/udev/rules.d/72-rg35xxh-udisks.rules` sets `UDISKS_IGNORE` for the labels `RG35XXHBOOT` and `rg35xxh-root`.
- **Toasts:** the same udev rule starts `rg35xxh-drive-notify@<disk>.service` when a disk appears and `rg35xxh-drive-removed@<disk>:<0|1>.service` when it goes (the rule itself checks whether a volume was still mounted, before udisks cleans the mount up). Both run `/usr/local/sbin/rg35xxh-drive-notify`, which notifies the active seat0 user; drive info is kept in `/run/rg35xxh-drives/` between the two. A remove + add bounce on insertion is ignored. Tapping the toast opens Thunar through the user's own service manager (`systemd-run --user`), so it is not closed with the short-lived service.
- **Eject on SD cards:** udisks marks SD cards ejectable, but an SD slot has nothing to eject: after a good unmount the real `eject` failed ("Failed to eject"). `/usr/local/sbin/eject` (before `/usr/bin` in udisksd's PATH) succeeds for `mmcblk*` and passes anything else to the real `eject`.
- **Memory:** ~15 MB (PSS) for udisksd and the gvfs daemons, and nothing until first used: udisks2 is not started at boot (`build/09-services.sh`) but D-Bus activated when Thunar or a file dialog first asks for drives.

Verified 2026-10-22 with a card in TF2.
