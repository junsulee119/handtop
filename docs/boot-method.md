# Boot Method

## Finding

ROCKNIX's `KERNEL` (Linux 7.2.0 arm64 `Image`) has a **built-in initramfs** (LibreELEC-style `/init`, ~7 MB). That `/init` mounts ROCKNIX's `SYSTEM` squashfs from `boot=LABEL=...` and a `STORAGE` overlay — it cannot start a normal Debian root filesystem.

## Decision: bypass the built-in initramfs with `rdinit=` (+ `rootfix.cpio`)

**Found on the first hardware boot:** the kernel then panicked with `VFS: Cannot open root device "PARTUUID=…" … error -2`. Cause: the kernel mounts `root=` onto `/root` inside the initramfs rootfs, and ROCKNIX's built-in initramfs has no `/root` directory. Fix: `INITRD /rootfix.cpio` in `extlinux.conf` — a 512-byte cpio containing only `root/`, unpacked on top of the built-in initramfs. (QEMU did not show this: its Debian kernel has no built-in initramfs.)

Kernel command line:

```
root=PARTUUID=<disk-id>-02 rootwait rootfstype=ext4 ro rdinit=/nonexistent console=ttyS0,115200 console=tty0
```

- When the `rdinit=` program does not exist, the kernel skips the initramfs `/init` and mounts `root=` directly (`kernel_init_freeable()` → `prepare_namespace()`). No kernel rebuild needed.
- Possible because everything needed to mount the root is **built in** (`CONFIG_MMC_SUNXI=y`, `CONFIG_EXT4_FS=y`, `CONFIG_DEVTMPFS_MOUNT=y`).
- `PARTUUID` instead of `/dev/mmcblk0p2`, because the device has two SD slots and numbering can change.
- `ro` so `systemd-fsck` can check the root partition before systemd remounts it read-write.
- Cost: the unused built-in initramfs stays in RAM (~7 MB). Acceptable; removable later with our own kernel build.

Debugging tip: `loglevel=5 fbcon=font:VGA8x8` shows the VFS error line and doubles the lines on screen.

## Kernel config checks (from the embedded `/proc/config.gz` data)

Everything Debian/systemd and our design need is present:

| Need | Config |
|---|---|
| systemd | cgroups, memcg, BPF, seccomp, namespaces, fhandle, autofs, inotify, tmpfs xattr/ACL — all `y` |
| Root on SD | `MMC_SUNXI=y`, `EXT4_FS=y`, `VFAT_FS=y` |
| Input daemon | `INPUT_UINPUT=y`, `INPUT_EVDEV=y`, `INPUT_FF_MEMLESS=y` |
| Power button | `INPUT_AXP20X_PEK=y` (driver built in; still verify it binds on the AXP717) |
| Gamepad | `rocknix-singleadc-joypad.ko` (module, auto-loaded from device tree) |
| GPU / display / HDMI | `DRM_PANFROST=y`, `DRM_SUN4I=y`, `DRM_SUN8I_DW_HDMI=y` |
| Wi-Fi | `RTW88_8821CS=y`, `CFG80211=y`, `MAC80211=y` |
| Bluetooth | `BT=m`, `BT_HCIUART=m` + `BT_HCIUART_RTL=y`, `BT_HIDP=m` (no `BT_RFCOMM` — fine, not needed) |
| zram | `ZRAM=m` (module present) |
| USB audio / USB Ethernet | `SND_USB_AUDIO=y`; `cdc_ether`, `r8152`, `asix` etc. as modules |
| Audit | not set — Debian works without it |

## Boot chain

1. Allwinner BROM loads U-Boot SPL from 8 KiB on the SD card (`u-boot-sunxi-with-spl.bin`, ROCKNIX DDR4 build).
2. U-Boot reads `extlinux/extlinux.conf` from the FAT partition, loads `/KERNEL` and `/dtb.img`.
3. Kernel mounts the Debian ext4 root partition and starts systemd.

## Charging while off (2026-10-09)

Plugging in the charger used to **switch the device on** (the AXP717 PMIC powers up on VBUS insertion and the old bootloader booted Linux).

Fixed by moving the hardware layer to **ROCKNIX 20261001**, whose DDR4 U-Boot has the charge-only boot patch ([ROCKNIX PR #3364](https://github.com/ROCKNIX/distribution/pull/3364), merged 2026-09-22; `CONFIG_AXP_DISABLE_BOOT_ON_POWERON=y` in `anbernic_rg35xx_h700_lpddr4_defconfig`). In early SPL it checks the AXP717: if the power-on was caused by plugging in USB power and a battery is present, it powers straight back off; the PMIC keeps charging while off. The power button still boots normally.

- Upstream tested on an RG34XX-SP (same H700/LPDDR4 U-Boot config). **Verified on the RG35XX H (2026-10-16, image `705c5ce`):** a charger plugged into a switched-off device keeps it off and charging; the power button boots it.
- DDR3 boards (v0.1.2+) use ROCKNIX's DDR3 U-Boot; whether it includes the charge-only boot change is not confirmed yet.
