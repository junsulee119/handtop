# Safety rules for every build/test script (sourced by config.sh).
# shellcheck shell=bash
# 1. All paths must resolve inside this project; an empty or wrong ROOTFS aborts.
# 2. Deleting files: only through safe_rm, and only inside $WORK (build outputs:
#    rootfs, downloads, temp). Anything outside $WORK is refused.
#    (Background: a test script run with sudo once resolved ~ to /root, got an empty
#    path variable and deleted files outside the project. These checks prevent that.)
# 3. No rm inside chroot commands (bind mounts reach the host); in_chroot rejects them.

die() { echo "SAFETY: $*" >&2; exit 1; }

assert_build_paths() {
  [ -n "${TOP:-}" ] && [ -f "$TOP/build/config.sh" ] || die "TOP is not the project directory: '${TOP:-}'"
  local w r
  w="$(realpath -m -- "${WORK:-}")"; r="$(realpath -m -- "${ROOTFS:-}")"
  case "$w" in "$(realpath -m "$TOP")"/?*) ;; *) die "WORK outside project: '$w'";; esac
  case "$r" in "$w"/?*) ;; *) die "ROOTFS outside WORK: '$r'";; esac
}

assert_rootfs() {
  assert_build_paths
  [ -f "$ROOTFS/etc/debian_version" ] || die "ROOTFS is not a Debian root filesystem: '$ROOTFS'"
}

# safe_rm [-r] PATH...   (no options other than -r; globs are expanded by the caller)
safe_rm() {
  local rec="" p rp w
  [ "${1:-}" = "-r" ] && { rec="-r"; shift; }
  assert_build_paths
  w="$(realpath -m -- "$WORK")"
  for p in "$@"; do
    [ -n "$p" ] || die "safe_rm: empty path"
    rp="$(realpath -m -- "$p")"
    case "$rp" in
      "$w"/?*) ;;
      *) die "safe_rm: refusing to delete outside the build directory ($w): $rp" ;;
    esac
    # Never cross into mounted filesystems (e.g. /proc, /dev bind mounts in a chroot).
    rm -f $rec --one-file-system -- "$rp"
  done
}
