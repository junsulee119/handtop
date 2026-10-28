# Kernel layer: what Handtop changes compared with ROCKNIX

Handtop takes its whole hardware layer from ROCKNIX (release `ROCKNIX_VERSION` in `build/config.sh`, currently **20261001**, H700, DDR4 or DDR3): U-Boot, the kernel image (`KERNEL`, Linux 7.2.0 with its built-in initramfs), the device trees, every kernel module and the firmware files. `build/02-extract-rocknix.sh` extracts them from ROCKNIX's release image (SHA-256 pinned) and `build/06-hardware.sh` copies the modules and firmware unchanged.

This page lists **every** place where Handtop differs at kernel level: the boot command line, the device tree, and four kernel modules (two added, one new, one replaced). Anything not listed here is ROCKNIX's file, byte for byte. Keep this list complete: a change to the kernel, a module, the device tree or the boot command line goes here in the same PR.

All modules are built against an exact rebuild of ROCKNIX's kernel tree (`build/06b-cedrus.sh`: linux 7.2 + ROCKNIX's patches at the release tag + ROCKNIX's own `.config` read out of `KERNEL`, built with GCC 15 like ROCKNIX), and each build step checks that every symbol version a module imports matches ROCKNIX's modules, and that `vermagic` matches. The kernel image itself is never rebuilt.

## Summary

| What | ROCKNIX | Handtop | Why | Where |
|---|---|---|---|---|
| Boot: initramfs | `KERNEL`'s built-in initramfs starts ROCKNIX's SYSTEM squashfs | Skipped with `rdinit=/nonexistent`; `rootfix.cpio` adds the `/root` directory the kernel needs to mount `root=` | Boot a normal Debian root filesystem with ROCKNIX's unmodified kernel | [boot-method.md](boot-method.md), `build/10-image.sh` |
| Boot: command line | ROCKNIX's | `root=PARTUUID=… rootwait rootfstype=ext4 ro rdinit=/nonexistent console=ttyS0,115200 console=tty0 loglevel=4 cma=256M` | Debian root; `cma=256M` contiguous memory for the video decoder (no IOMMU) | `build/10-image.sh`, `CMA_SIZE` |
| Device tree | `sun50i-h700-anbernic-rg35xx-h.dtb` / `…-rev6-panel.dtb` | Same + a **video engine node** (overlay, no `iommus`); the matching panel's file is picked at every boot | Hardware video decoding; rev6 screens | `build/dts/rg35xxh-video-engine.dtso`, [video-decode.md](video-decode.md), [services/panel.md](services/panel.md) |
| `sunxi-cedrus.ko` | Not built | **Added**: upstream Cedrus driver + 2 patches | Hardware video decoding (Moonlight) | `build/06b-cedrus.sh`, `build/kernel/000*.patch` |
| `usb_f_fs_xinput.ko` | Doesn't exist | **New**: generated copy of FunctionFS that accepts vendor class descriptors | Wired Xbox 360 controller mode | `build/06c-ffs-xinput.sh` |
| `uhid.ko` | Not built (`# CONFIG_UHID is not set`) | **Added**: the kernel's own uhid driver, unchanged | Bluetooth LE keyboards, mice and gamepads (HID over GATT) | `build/06e-uhid.sh` |
| `rocknix-singleadc-joypad.ko` | ROCKNIX's build of rocknix-joypad `d02ed13` | **Replaced**: same source + a locking fix in the rumble path | A change of vibration strength could freeze the whole handheld | `build/06d-joypad.sh`, `build/kernel/rocknix-joypad/` |
| U-Boot, `KERNEL`, all other modules, firmware | ROCKNIX's | Unchanged | | `build/02-extract-rocknix.sh`, `build/06-hardware.sh` |

Not kernel changes, for completeness: runtime settings written by `rg35xxh-hwinit` at boot (CPU and GPU governors, rfkill unblock, `rumble_enable`, LEDs, audio mixer; ported from ROCKNIX's quirk scripts, [rocknix-quirks.md](rocknix-quirks.md)), udev permission rules (`overlay/etc/udev/rules.d/`: uinput and LED for the input daemon, backlight, dma-buf heaps for video decoding), and the panel check that copies one of the two device trees ([services/panel.md](services/panel.md)).

## Details

### Boot and command line

ROCKNIX's `KERNEL` carries a built-in initramfs whose `/init` only knows ROCKNIX's own system image. `rdinit=/nonexistent` makes the kernel skip it and mount `root=` itself; ROCKNIX's initramfs has no `/root` directory to mount it on, so a 512-byte `rootfix.cpio` containing only that directory is loaded on top. Everything needed to mount the root is built into ROCKNIX's kernel, so no rebuild is needed. Cost: the unused initramfs stays in RAM (~7 MB). Full story: [boot-method.md](boot-method.md).

### Device tree: video engine overlay

`build/dts/rg35xxh-video-engine.dtso` adds the H616 video engine node (from Chen-Yu Tsai's upstream series) to ROCKNIX's DTB with `fdtoverlay` at image build time, for both screen panels (`dtb-regular.img`, `dtb-rev6.img`; `dtb-rocknix.img` keeps ROCKNIX's original as a fallback). One deliberate difference from upstream: **no `iommus` property**: with the IOMMU on for the video engine, the display engine faulted and the screen stayed black; the decoder uses contiguous CMA memory instead (`cma=256M`). [video-decode.md](video-decode.md).

### `sunxi-cedrus.ko` (added)

ROCKNIX's kernel has everything Cedrus needs built in but not the driver itself. `06b-cedrus.sh` enables `VIDEO_SUNXI_CEDRUS=m` on ROCKNIX's `.config` and builds it with:
- `0001-cedrus-add-h616-variant.patch`: the H616 compatible string (backported unchanged from the upstream series);
- `0002-cedrus-64-byte-stride.patch`: 64-byte aligned output stride, so the GPU (panfrost) imports decoded frames instead of rejecting them ("the blue video").

Installed as `/usr/lib/modules/7.2.0/extra/sunxi-cedrus.ko`.

### `usb_f_fs_xinput.ko` (new)

The wired Xbox 360 controller interface needs a 17-byte class descriptor (type 0x21) that the kernel's FunctionFS rejects (it only knows 0x21 as the 9-byte HID descriptor). `06c-ffs-xinput.sh` generates a renamed copy of the kernel's own `f_fs.c` (filesystem `functionfs_xinput`, USB function `ffsxi`, exports dropped so it sits next to the built-in FunctionFS) that also accepts class descriptors on vendor-specific interfaces. The generator stops if `f_fs.c` changes upstream. Installed as `extra/usb_f_fs_xinput.ko`; used only by Wired Controller mode and Switch Controller mode over USB. [apps/external-controller.md](apps/external-controller.md).

### `uhid.ko` (added)

BlueZ hands Bluetooth LE input devices (HID over GATT, "HoG": most current Bluetooth mice and keyboards, many gamepads) to the kernel through `/dev/uhid`. ROCKNIX's kernel is built without it (`# CONFIG_UHID is not set`), so such a device paired and connected but no input device ever appeared; bluetoothd logged `input-hog profile accept failed` on every connection. Classic Bluetooth HID goes through `hidp` (a module ROCKNIX does build), which is why classic mice, keyboards and the Xbox controller worked.

`06e-uhid.sh` builds the kernel's own `drivers/hid/uhid.c`, unchanged, out of tree against the ROCKNIX tree (ROCKNIX's `.config` stays untouched; the HID core it needs is built into ROCKNIX's kernel). It stops if ROCKNIX's config changes for UHID. Installed as `extra/uhid.ko`; loaded on demand: depmod lists its `devname:uhid` alias, systemd creates `/dev/uhid` at boot and bluetoothd's first open loads it. Three of the symbols it imports (`stream_open`, `hid_safe_input_report`, `__task_pid_nr_ns`) are used by no ROCKNIX module, so the build can't compare their versions; the kernel checks them when loading (it accepted the module on the device).

Tested 2026-10-28 (DDR4): a Bluetooth LE mouse works, as a mouse and its keyboard part; before, it connected but did nothing. After a restart, `/dev/uhid` existed, the module was loaded on demand and the paired mouse reconnected by itself.

### `rocknix-singleadc-joypad.ko` (replaced, rumble fix)

The gamepad and vibration motor driver comes from ROCKNIX's separate [rocknix-joypad](https://github.com/ROCKNIX/rocknix-joypad) package; `06d-joypad.sh` downloads the exact commit ROCKNIX 20261001 builds (`JOYPAD_COMMIT`, checksum from ROCKNIX's `package.mk`), applies `build/kernel/rocknix-joypad/0001-rumble-no-mutex-in-atomic-context.patch`, builds it for H700 and installs it **over ROCKNIX's file** (same path, `rocknix-joypad/rocknix-singleadc-joypad.ko`). Its imports are identical to ROCKNIX's build of the same source.

**The bug.** The kernel's memoryless force-feedback layer (`ff-memless`) calls the driver's play callback in atomic context: with the input device's event lock held and interrupts off, both when a program starts or stops an effect and from its own effect timer. The callback took the driver's mutex, which the driver's work item holds while it programs the PWM (`pwm_apply_might_sleep`). Usually nobody waits and nothing happens; but when the two meet, the callback sleeps in atomic context and the CPU deadlocks with the PWM still on: the motor keeps buzzing, input, Wi-Fi and SSH are dead, only a 10 s power cut helps, and the power chip can stay latched afterwards. A change of vibration strength is a "stop" and a "play" back to back, the most likely moment for the two to meet, so games whose vibration changes all the time hit it within minutes.

History: two freezes on 2026-10-28 (Mario Kart in Switch Controller mode over Bluetooth, then the stress test that pinned it down). It very likely also caused the earlier "infinite vibration" freezes in Wired Controller mode, which led to the input daemon's motor gate (fixed-length effects, ≤10 updates/s): the gate made it rarer but could not prevent it. The log-out freeze (2026-10-26) happened while the motor changed owners and may be the same bug; its cause was only inferred ([services/input-daemon.md](services/input-daemon.md)).

**The fix.** The callback only stores the new strength (`WRITE_ONCE`) and schedules the work item; the work item applies it under the mutex, as before. Also fixed: writing 0 to `rumble_enable` waited for the work item (`cancel_work_sync`) while holding the mutex that the work item takes.

**Tested** (2026-10-28, DDR4 RG35XX H, `tools/motor-stress.py` through the input daemon's normal path, with a 1 s heartbeat on the boot partition): with ROCKNIX's module the "randomslow" pattern (a new random strength every 0.5 s) froze the handheld after about 60 s. With the fixed module it ran all four patterns back to back without a problem: randomslow 5 min (599 changes), random 5 min (a new strength every 50 ms, 5953 requests; the daemon's gate turns that into ~10 changes/s), flip 3 min (two strengths alternating every 0.1 s) and on/off 3 min (motor on and off every 0.1 s): about 16 minutes, system idle throughout, no kernel warnings.

Worth reporting upstream to ROCKNIX (the same driver is used on their other devices with a motor).

## Updating to a new ROCKNIX release

1. Set `ROCKNIX_VERSION` (and the image checksums) in `build/config.sh`, and `JOYPAD_COMMIT` / `JOYPAD_SHA256` from that release's `projects/ROCKNIX/packages/linux-drivers/rocknix-joypad/package.mk`.
2. Check whether ROCKNIX fixed the rumble locking upstream; if so, drop `06d-joypad.sh` and its patch.
3. `06b`–`06e` stop if a patch no longer applies, `f_fs.c` changed, ROCKNIX's UHID setting changed, or a symbol version differs; fix those before building an image.
4. Re-test on a device: video decoding, Wired Controller mode, vibration (`tools/motor-stress.py random 300`) and a Bluetooth LE mouse or keyboard.
