#!/bin/bash
# System services for first boot, Wi-Fi import, boot logs and low-power mode.
set -euo pipefail
source "$(dirname "$(realpath "$0")")/config.sh"
source "$(dirname "$(realpath "$0")")/lib/chroot.sh"
trap chroot_umount EXIT
assert_rootfs
mkdir -p "$ROOTFS/var/log/journal"            # persistent journal (survives reboots)
chmod 0440 "$ROOTFS/etc/sudoers.d/rg35xxh-lowpower"
chroot_mount
in_chroot "visudo -cf /etc/sudoers.d/rg35xxh-lowpower"
in_chroot "systemctl enable rg35xxh-ssh-keygen.service rg35xxh-resize-root.service rg35xxh-swapfile.service rg35xxh-tailscale-operator.service tailscaled.service rg35xxh-wifi-import.service rg35xxh-bootlog.timer rg35xxh-bootlog-update.timer rg35xxh-bootlogo.service rg35xxh-bootlogo-done.service rg35xxh-panel.service"
# udisks2 (click-to-mount in Thunar) is D-Bus activated: it starts the first time Thunar or a
# file dialog asks for drives, instead of at every boot.
in_chroot "systemctl disable udisks2.service"
echo "Services configured."
