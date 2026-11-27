# Helpers to run commands inside the arm64 rootfs. Source after config.sh.
# shellcheck shell=bash

chroot_test_lock() {
  local lock_fd
  assert_build_paths
  WORK=$(realpath -m -- "$WORK")
  mkdir -p "$WORK"
  # Keep the directory lock open through EXIT, even before the first mount.
  exec {lock_fd}<"$WORK"
  flock -n "$lock_fd" || die "cannot lock WORK $WORK (another test may be running)"
  assert_no_mounts "$ROOTFS" "$WORK/migrate-mnt"
}

chroot_mount() {
  assert_rootfs
  mountpoint -q "$ROOTFS/proc"    || mount -t proc proc "$ROOTFS/proc"
  mountpoint -q "$ROOTFS/sys"     || mount -t sysfs sysfs "$ROOTFS/sys"
  mount --make-rslave "$ROOTFS/sys" 2>/dev/null || true
  # Slave mounts: the host's /dev reaches the chroot, but nothing mounted or unmounted there reaches
  # the host. With the host's shared propagation, a plain bind made each chroot's /dev/pts mount and
  # unmount the host's too; parallel test runs once left the server without /dev/pts (2026-11-25).
  # Also an existing bind (a run stopped half-way) is made slave before anything is mounted below it.
  mountpoint -q "$ROOTFS/dev" || mount --bind /dev "$ROOTFS/dev"
  mount --make-rslave "$ROOTFS/dev"
  mountpoint -q "$ROOTFS/dev/pts" || mount --bind /dev/pts "$ROOTFS/dev/pts"
  mount --make-rslave "$ROOTFS/dev/pts"
  chroot_dev_private || die "chroot /dev mounts still propagate to the host"
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

# True when the chroot's /dev and /dev/pts binds can't pass mounts or unmounts to the host (#97).
chroot_dev_private() {
  local m p e
  for m in dev dev/pts; do
    local rc=0
    if ! e=$(LC_ALL=C stat -c %n -- "$ROOTFS/$m" 2>&1 >/dev/null); then
      case "$e" in *"No such file or directory"*) continue ;; *) return 1 ;; esac   # only "absent" is absent
    fi
    mountpoint -q "$ROOTFS/$m" || rc=$?
    [ "$rc" = 32 ] && continue                   # not a mount point; any other failure: unknown (#119)
    [ "$rc" = 0 ] || return 1
    p=$(findmnt -n -o PROPAGATION "$ROOTFS/$m" 2>/dev/null) || return 1
    case "$p" in ""|*shared*) return 1 ;; esac
  done
}
chroot_umount() {
  [ -n "${ROOTFS:-}" ] || return 0
  assert_build_paths
  # Tests discard their private copy after unmounting, so leave its files alone here.
  if [ "${1:-}" != --mounts-only ]; then
    for f in usr/sbin/policy-rc.d etc/ssl/build-extra-ca.crt etc/apt/apt.conf.d/99build-extra-ca \
             etc/dpkg/dpkg.cfg.d/99build-unsafe-io etc/apt/apt.conf.d/99build-fast; do
      [ -e "$ROOTFS/$f" ] && safe_rm "$ROOTFS/$f"
    done
  fi
  sync -f "$ROOTFS" 2>/dev/null || sync
  for m in dev dev/pts sys; do                   # never let an unmount reach the host (#97)
    mountpoint -q "$ROOTFS/$m" && mount --make-rslave "$ROOTFS/$m" 2>/dev/null || true
  done
  if ! chroot_dev_private; then
    echo "SAFETY: $ROOTFS/dev still propagates to the host: not unmounting below it (umount -l it by hand after making it rslave)" >&2
    for m in run sys proc; do mountpoint -q "$ROOTFS/$m" && umount -l "$ROOTFS/$m" || true; done
    return 0
  fi
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
