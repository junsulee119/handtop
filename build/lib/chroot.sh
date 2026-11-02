# Helpers to run commands inside the arm64 rootfs. Source after config.sh.
# shellcheck shell=bash

chroot_mount() {
  assert_rootfs
  mountpoint -q "$ROOTFS/proc"    || mount -t proc proc "$ROOTFS/proc"
  mountpoint -q "$ROOTFS/sys"     || mount -t sysfs sysfs "$ROOTFS/sys"
  mountpoint -q "$ROOTFS/dev"     || mount --bind /dev "$ROOTFS/dev"
  mountpoint -q "$ROOTFS/dev/pts" || mount --bind /dev/pts "$ROOTFS/dev/pts"
  mountpoint -q "$ROOTFS/dev/shm" || mount -t tmpfs -o mode=1777 shm "$ROOTFS/dev/shm"
  mountpoint -q "$ROOTFS/run"     || mount -t tmpfs tmpfs "$ROOTFS/run"
  cp -L /etc/resolv.conf "$ROOTFS/etc/resolv.conf"
  # Build hosts behind a TLS-inspecting proxy: trust its CA during the build only.
  if [ -n "${BUILD_EXTRA_CA:-}" ] && [ -f "$BUILD_EXTRA_CA" ]; then
    cp "$BUILD_EXTRA_CA" "$ROOTFS/etc/ssl/build-extra-ca.crt"
    echo 'Acquire::https::CAInfo "/etc/ssl/build-extra-ca.crt";' > "$ROOTFS/etc/apt/apt.conf.d/99build-extra-ca"
  fi
  # Faster package installs: skip fsync during the build (removed again on unmount).
  echo force-unsafe-io > "$ROOTFS/etc/dpkg/dpkg.cfg.d/99build-unsafe-io"
  printf 'Acquire::Queue-Mode "host";\nAcquire::http::Pipeline-Depth "10";\n' > "$ROOTFS/etc/apt/apt.conf.d/99build-fast"
  # Never start services while building.
  printf '#!/bin/sh\nexit 101\n' > "$ROOTFS/usr/sbin/policy-rc.d"
  chmod +x "$ROOTFS/usr/sbin/policy-rc.d"
}

chroot_umount() {
  [ -n "${ROOTFS:-}" ] || return 0
  assert_build_paths
  for f in usr/sbin/policy-rc.d etc/ssl/build-extra-ca.crt etc/apt/apt.conf.d/99build-extra-ca \
           etc/dpkg/dpkg.cfg.d/99build-unsafe-io etc/apt/apt.conf.d/99build-fast; do
    [ -e "$ROOTFS/$f" ] && safe_rm "$ROOTFS/$f"
  done
  sync -f "$ROOTFS" 2>/dev/null || sync
  for m in run dev/shm dev/pts dev sys proc; do
    mountpoint -q "$ROOTFS/$m" && umount -l "$ROOTFS/$m" || true
  done
}

in_chroot() {
  assert_rootfs
  case " $* " in *[\ \;\&\|]rm\ *|*rmdir*|*unlink*) die "in_chroot: use safe_rm on the host side, not rm in the chroot: $*";; esac
  local ca=""
  [ -f "$ROOTFS/etc/ssl/build-extra-ca.crt" ] && ca="/etc/ssl/build-extra-ca.crt"
  env DEBIAN_FRONTEND=noninteractive LC_ALL=C ${ca:+CURL_CA_BUNDLE=$ca} chroot "$ROOTFS" /bin/bash -euo pipefail -c "$*"
}
