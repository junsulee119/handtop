# Flashing and First Boot

## You need
- A microSD card, **16 GB or larger** (the image is ~3.3 GB; the system grows to fill the card on first boot). Keep the stock firmware card separately to go back any time.
- A card reader and **balenaEtcher** (or Rufus) on Windows.
- The image: `handtop-<date>-<version>.img.xz` and its `.sha256` file. Most units use this one; boards with DDR3 RAM need `handtop-<date>-<version>-DDR3.img.xz` (see below).

## Flash
1. (Optional) Check the download: in PowerShell, `Get-FileHash .\handtop-….img.xz` and compare with the `.sha256` file.
2. balenaEtcher → **Flash from file** → the `.img.xz` (no need to unpack) → select the SD card → **Flash**.
3. Windows may then say the card needs formatting — choose **Cancel** (the second partition is Linux; Windows cannot read it).

## Before the first boot (from Windows)
The card shows a drive named **RG35XXHBOOT**:
- `wifi.txt` — fill in `SSID=` and `PASSWORD=` now, or later (any time, then reboot).
- `rg35xxh-input.conf` — controls; defaults match `input-mapping.md`.
- `README.txt` — short version of this page.
Use **Eject** before removing the card.

## First boot
1. Card into the **TF1** (left) slot, power on.
2. First boot takes longer: the system partition is expanded and SSH keys are generated.
3. Expected: labwc desktop with the bottom panel (`☰ Apps`, clock, `⏻`).
4. **Garbled or black screen** → rev6 panel board: on the PC, copy `device_trees\sun50i-h700-anbernic-rg35xx-h-rev6-panel.dtb` over `dtb.img` on RG35XXHBOOT, eject, boot again.
5. Login (sudo): user `rg`, password `rg35xxh`. **SSH is off** until you turn it on with Apps → **Enable SSH**, which first asks you to choose your own password.

## If something is wrong
- **No LED / completely unresponsive:** RG35XX H units shipped with either DDR4 or DDR3 RAM. If the standard image does nothing at all, flash the `-DDR3` image instead (or build with `RAM_TYPE=DDR3`).
- Logs: `logs\boot-NNNN.txt` on RG35XXHBOOT (written 60 s and 3 min after boot).
- No picture at all: a USB-to-serial adapter on the UART header (115200 baud) shows the boot messages.
- Back to stock: power off, put the stock card back.
