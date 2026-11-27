#!/bin/bash
# Test the migration and update harnesses without root, mounts, a release image, or a build.
set -euo pipefail
source "$(dirname "$(realpath "$0")")/../build/config.sh"
assert_build_paths
mkdir -p "$WORK"
FIXTURE=$(mktemp -d "$WORK/test-harness-cleanup.XXXXXX")
trap 'safe_rm -r "$FIXTURE"' EXIT
export FIXTURE
W="$FIXTURE/with space"
ARCHIVE="$FIXTURE/archive"
SRC="$FIXTURE/source"
IMG="$FIXTURE/handtop-v0.4.1.img.xz"
CONF="$W/rootfs/etc/dpkg/dpkg.cfg.d/99build-unsafe-io"
mkdir -p "$ARCHIVE" "$SRC/rootfs/usr" "$SRC/pkg-ffmpeg" "$(dirname "$CONF")" "$W/rootfs/boot/firmware"
touch "$ARCHIVE/Packages" "$SRC/pkg-ffmpeg/test.deb" "$IMG"
echo other-run > "$CONF"
echo other-image > "$W/migrate.img"
: > "$FIXTURE/calls"
: > "$FIXTURE/mounts"

# Feed the real assert_no_mounts a fixture mount table. Log every attempted resource change.
add_mount() { printf 'none %s tmpfs rw 0 0\n' "${1// /\\040}" >> "$FIXTURE/mounts"; }
awk() {
  if [ "${*: -1}" = /proc/self/mounts ]; then
    command awk "${@:1:$#-1}" "$FIXTURE/mounts"
  else
    command awk "$@"
  fi
}
mountpoint() { awk -v "p=${2// /\\\\040}" '$2 == p { found = 1 } END { exit !found }' "$FIXTURE/mounts"; }
mount() { echo mount >> "$FIXTURE/calls"; add_mount "${@: -1}"; }
umount() { echo unmount >> "$FIXTURE/calls"; : > "$FIXTURE/mounts"; }
sync() { echo sync >> "$FIXTURE/calls"; }
xz() { echo decompress >> "$FIXTURE/calls"; echo test-image; }
chroot() { echo chroot >> "$FIXTURE/calls"; return 99; }
rsync() {
  echo copy >> "$FIXTURE/calls"
  printf '%s\n' "${@: -1}" > "$FIXTURE/copy-target"
  return 42
}
losetup() {
  case "$1" in
    -j) if [ -f "$FIXTURE/old-loop" ]; then echo '/dev/loop90: other image'; fi ;;
    -P) echo attach >> "$FIXTURE/calls"; printf '%s\n' "${@: -1}" > "$FIXTURE/loop"; echo /dev/loop91 ;;
    -l) if [ -f "$FIXTURE/loop" ]; then echo /dev/loop91; fi ;;
    -d)
      echo detach >> "$FIXTURE/calls"
      [ "$2" = /dev/loop91 ] || return 99
      mv "$FIXTURE/loop" "$FIXTURE/detached"
      ;;
    *) return 99 ;;
  esac
}
export -f add_mount awk mountpoint mount umount sync xz chroot rsync losetup

migrate() { WORK="$W" HANDTOP_TEST_ARCHIVE="$ARCHIVE" bash "$TOP/tools/migrate-test.sh" "$IMG"; }
update() { WORK="$W" SRC_WORK="$SRC" bash "$TOP/tools/update-test.sh"; }
refused() {
  local reason=$1
  shift
  if "$@" > "$FIXTURE/output" 2>&1 || ! grep -Fq "$reason" "$FIXTURE/output"; then
    cat "$FIXTURE/output" >&2
    die "expected $* to refuse with $reason"
  fi
}
original_intact() {
  [ "$(cat "$CONF")" = other-run ] && [ "$(cat "$W/migrate.img")" = other-image ] ||
    die "original files changed"
}

(
  source "$TOP/build/lib/chroot.sh"
  WORK=$W ROOTFS="$W/rootfs"
  chroot_test_lock
  refused "cannot lock WORK" migrate
  refused "cannot lock WORK" update
)
echo "PASS: both harnesses refuse a locked WORK"

add_mount "$W/rootfs/boot/firmware"
refused "something is still mounted" migrate
refused "something is still mounted" update
mountpoint -q "$W/rootfs/boot/firmware" || die "original mount disappeared"
: > "$FIXTURE/mounts"
add_mount "$SRC/rootfs/usr"
refused "something is still mounted" update
mountpoint -q "$SRC/rootfs/usr" || die "source mount disappeared"
: > "$FIXTURE/mounts"
touch "$FIXTURE/old-loop"
refused "is still attached to a loop device" migrate
[ -f "$FIXTURE/old-loop" ] && [ ! -s "$FIXTURE/calls" ] || die "refusal started setup or cleanup"
original_intact
safe_rm "$FIXTURE/old-loop"
echo "PASS: preflight refusal leaves the original mount, image and config alone"

status=0
migrate > "$FIXTURE/output" 2>&1 || status=$?
[ "$status" = 42 ] || { cat "$FIXTURE/output" >&2; die "migration fixture did not fail at rsync"; }
diff -u <(printf '%s\n' decompress attach mount copy unmount detach) "$FIXTURE/calls"
image=$(cat "$FIXTURE/detached")
[[ "$image" == "$W"/migrate-test.*/migrate.img && ! -e "${image%/*}" ]] || die "migration scratch copy was not cleaned up"
[ ! -s "$FIXTURE/mounts" ] || die "owned mount was left behind"
: > "$FIXTURE/calls"
status=0
update > "$FIXTURE/output" 2>&1 || status=$?
[ "$status" = 42 ] || { cat "$FIXTURE/output" >&2; die "update fixture did not fail at rsync"; }
diff -u <(echo copy) "$FIXTURE/calls"
root=$(cat "$FIXTURE/copy-target")
[[ "$root" == "$W"/update-test.*/rootfs/ && ! -e "${root%/rootfs/}" ]] || die "update scratch copy was not cleaned up"
original_intact
echo "PASS: copy failures clean up each run's scratch paths and release the owned mount and loop in order"

(
  source "$TOP/build/lib/chroot.sh"
  WORK=$W ROOTFS="$W/rootfs"
  chroot_umount --mounts-only
)
original_intact
echo "PASS: mounts-only cleanup preserves build config"
