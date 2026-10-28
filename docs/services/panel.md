# Screen panel check (`rg35xxh-panel`)

RG35XX H units ship with one of two screen panels. They use the same connector but need a different set-up sequence, so each has its own device tree in ROCKNIX: `sun50i-h700-anbernic-rg35xx-h.dtb` ("regular") and `sun50i-h700-anbernic-rg35xx-h-rev6-panel.dtb` ("rev6"; the two differ only in the panel's `compatible` and `rocknix-dt-id`). With the wrong one the screen shows garbled lines or stays black, while the rest of the system boots normally.

`rg35xxh-panel` picks the right one by itself at every boot.

## What it does

`rg35xxh-panel.service` (oneshot, `/usr/local/sbin/rg35xxh-panel`), every boot, before the desktop session starts:

1. **Which panel does the board have?** It reads pin **PE6** with its pull-up on: high = regular, low = rev6. `panel.txt` on the boot partition can override this (`regular` / `rev6`; default `auto`).
2. **Which one will U-Boot load?** It compares `dtb.img` on the boot partition with `dtb-regular.img` and `dtb-rev6.img` (both built from ROCKNIX's DTBs plus the video-engine overlay, [../video-decode.md](../video-decode.md)).
3. **Match** (almost every boot): nothing is written, a few ms.
4. **Mismatch:** it copies the right file over `dtb.img`, notes it in `logs/panel.txt` on the boot partition, and restarts once. The screen is garbled on that one boot; after the restart it is right. Moving a card to a unit with the other panel works the same way, in both directions.

| Situation | Result |
|---|---|
| `dtb.img` is neither `dtb-regular.img` nor `dtb-rev6.img` (changed by hand, e.g. without the video engine) | Left alone, logged to the journal |
| PE6 can't be read, or the reads disagree | Nothing changed |
| `dtb-regular.img` / `dtb-rev6.img` missing (older image) | Nothing changed |
| Switched on the last boot, and on this boot the pin says the other panel again (`auto`) | Not switched again: no restart loop. Logged in `logs/panel.txt`; resets once `dtb.img` matches. Use `panel.txt` to fix it |
| `panel.txt` says `regular` / `rev6` | That panel, whatever the pin says (no loop guard: the target can't flip) |

## Where PE6 comes from

Anbernic's stock firmware makes the same choice. Its U-Boot (Allwinner BSP) does it in `lcd_panel_uboot_fj035fhd05_v1_init`: it turns on PE6's pull-up, reads the pin, and sets `lcd_type = 1` when it is low, which selects a second panel set-up sequence; the stock kernel logs it as `allen_boe_lcd`. Found by reading a stock card read-only on 2026-10-28 (disassembly of its U-Boot; register details in the project notes). ROCKNIX and the mainline kernel don't use PE6: they ask the user to try both device trees ("impossible to know the difference without opening the device", ROCKNIX's H700 guide).

Measured: a regular-panel unit reads PE6 = 1 (with and without the pull-up, so the board probably has its own pull-up). A rev6 reading of 0 is expected from the stock code but **not measured yet**; if a rev6 unit reads 1, the script keeps the regular DTB and `panel.txt` (`rev6`) is the fix. Please report it.

Tested on a regular-panel RG35XX H (DDR4), 2026-10-28, with the service installed on v0.3.0:
`panel.txt` = `rev6` → switched, restarted once, came up with the rev6 device tree (`/proc/device-tree/rocknix-dt-id`); back to `auto` → PE6 = 1, switched back to regular, restarted once, normal; the next boot only said "matches". PE6 was back to "input bias disabled" afterwards and the input daemon started normally.

Only checked for the RG35XX H. Other H700 models may use PE6 differently.

## Safety ([../hardware-safety.md](../hardware-safety.md))

- **Owner:** PE6 is unclaimed in ROCKNIX's device tree (`pinmux-pins`: UNCLAIMED). The script requests it as an input through the GPIO character device, then requests it once more with the bias disabled, which is how ROCKNIX leaves it.
- **Restart:** it runs before `getty@tty1` (which starts the session), so the input daemon and other hardware owners aren't running yet, and after the first-boot jobs (root resize, swap file, SSH keys) so a restart never interrupts them. It also waits for a running Wi-Fi import (which rewrites `wifi.txt` on the same partition). Cost: on the very first boot the desktop starts after the root resize and swap file are done instead of alongside them, about 4 s later on a 64 GB card (measured: getty at 14.1 s, first-boot jobs done at 18.3 s); later boots skip those jobs.
- **Boot partition:** `dtb.img` is replaced with an fsync'ed copy that is read back before a rename, then the directory is synced. A power cut leaves the old or the new file, never half of one. On normal boots nothing is written.
- **Errors:** an unreadable pin, a missing or empty source file, a failed copy or a failed restart request change nothing (or leave the already-correct `dtb.img` for the next restart) and are logged; a leftover `dtb.img.new` from a power cut is overwritten. Any unexpected error is logged to `logs/panel.txt` and the boot continues.
- **Fallback:** the boot partition still has `dtb-rocknix.img` and `device_trees/`, so a unit can always be fixed from a PC.

## Options considered

- **Check only on the first boot:** rejected. A card moved to a unit with the other panel would stay garbled.
- **Choose in U-Boot** (a boot script reading PE6 before the kernel loads): no garbled boot at all, but it replaces ROCKNIX's plain `extlinux.conf` boot, and a mistake there stops every unit from booting. Kept as a possible later step.
- **Keep the manual tip** (copy the rev6 file over `dtb.img`): that is what ROCKNIX does. It also lost hardware video decoding, because ROCKNIX's file has no video-engine node.

## Files

| File | What |
|---|---|
| `overlay/usr/local/sbin/rg35xxh-panel` | The check (Python, GPIO uAPI v2 via `ioctl`; libgpiod tools aren't installed) |
| `overlay/etc/systemd/system/rg35xxh-panel.service` | Unit, enabled in `build/09-services.sh` |
| `build/10-image.sh` | Builds `dtb-regular.img` and `dtb-rev6.img` (`REV6_DTB` in `config.sh`); `dtb.img` starts as the regular one |
| `boot-files/panel.txt` | Override on the boot partition (CRLF) |
| `/var/lib/rg35xxh/panel-switched` | Set after an automatic switch; removed once `dtb.img` matches (loop guard) |
| `tools/test-panel.sh` | Tests with a fake boot partition and a fake pin reading (`RG35XXH_PANEL_BOOT`, `RG35XXH_PANEL_STATE`, `RG35XXH_PANEL_TEST_PE6`, `RG35XXH_PANEL_DRYRUN`) |
