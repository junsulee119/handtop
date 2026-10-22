#!/bin/bash
# Base system configuration: identity, user, locale, timezone, fstab, services, overlay files.
set -euo pipefail
source "$(dirname "$0")/config.sh"
source "$(dirname "$0")/lib/chroot.sh"
trap chroot_umount EXIT
chroot_mount

# Files we ship verbatim.
rsync -a --chown=root:root --chmod=D755,F644 "$TOP/overlay/" "$ROOTFS/"

# Desktop entries and MIME types.
#
# The overlay adds entries under /usr/local/share/applications. GIO only maps a
# content type to an application when that directory has a mimeinfo.cache, and
# without it a fresh home has no handler for a video file at all: Thunar falls
# back to running a literal "%U" ("missing exec"). The shared-mime-info cache
# (the other half) is missing in some images, which leaves GIO guessing content
# types but unable to map them to applications.
in_chroot "update-mime-database /usr/share/mime"
in_chroot "update-desktop-database /usr/local/share/applications"
in_chroot "update-desktop-database /usr/share/applications"
# Executables in the overlay
chmod 755 "$ROOTFS"/usr/local/sbin/* "$ROOTFS"/usr/local/bin/* 2>/dev/null || true
chmod 0440 "$ROOTFS"/etc/sudoers.d/rg35xxh-* 2>/dev/null || true

# Hostname
echo "$HOSTNAME_TARGET" > "$ROOTFS/etc/hostname"
cat > "$ROOTFS/etc/hosts" <<H
127.0.0.1 localhost
127.0.1.1 $HOSTNAME_TARGET
::1       localhost ip6-localhost ip6-loopback
H

# Locale and timezone
echo "$LOCALE UTF-8" > "$ROOTFS/etc/locale.gen"
in_chroot "locale-gen && update-locale LANG=$LOCALE"
ln -sf "/usr/share/zoneinfo/$TIMEZONE" "$ROOTFS/etc/localtime"
echo "$TIMEZONE" > "$ROOTFS/etc/timezone"

# Filesystems (labels are set by the image builder)
mkdir -p "$ROOTFS/boot/firmware"
cat > "$ROOTFS/etc/fstab" <<F
LABEL=$ROOT_LABEL  /               ext4  defaults,noatime,commit=60     0 1
LABEL=$BOOT_LABEL  /boot/firmware  vfat  defaults,noatime,umask=0022,nofail  0 2
tmpfs              /tmp            tmpfs defaults,nosuid,nodev,size=256M  0 0
F

# User
if ! in_chroot "id $USER_NAME" >/dev/null 2>&1; then
  in_chroot "useradd -m -s /bin/bash $USER_NAME"
fi
for g in sudo video render audio input netdev plugdev bluetooth; do
  in_chroot "getent group $g >/dev/null && usermod -aG $g $USER_NAME || true"
done
in_chroot "echo '$USER_NAME:$USER_DEFAULT_PASSWORD' | chpasswd"
in_chroot "passwd -l root"

# Services
in_chroot "systemctl enable systemd-timesyncd NetworkManager bluetooth zramswap"
# SSH is off until the user picks their own password (Apps -> Enable SSH): the default one is public.
in_chroot "systemctl disable ssh.service ssh.socket 2>/dev/null || true"
in_chroot "systemctl set-default graphical.target"
in_chroot "systemctl mask systemd-networkd-wait-online.service NetworkManager-wait-online.service || true"

echo "Base configuration done."
