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
    # The folder it is in is resolved, not the name itself: a symlink is deleted as a link, never
    # followed to where it points (which may be outside $WORK).
    rp="$(realpath -m -- "$(dirname -- "$p")")/$(basename -- "$p")"
    case "$rp" in
      "$w"/?*) ;;
      *) die "safe_rm: refusing to delete outside the build directory ($w): $rp" ;;
    esac
    # Never cross into mounted filesystems (e.g. /proc, /dev bind mounts in a chroot).
    rm -f $rec --one-file-system -- "$rp"
  done
}

# assert_no_mounts DIR...   refuse when anything is mounted at or below DIR. A chroot left mounted by a
# killed run (its EXIT trap never ran) binds the host's /dev, /proc, ... into the rootfs: copying from
# it or deleting into it (rsync --delete) would reach the host (external review 2026-11-19, #11).
assert_no_mounts() {
  local d r
  for d in "$@"; do
    r="$(realpath -m -- "$d")"
    if awk -v r="$r" '{ m = $2; gsub(/\\040/, " ", m); if (m == r || index(m, r "/") == 1) { print "  " m; f = 1 } }
                      END { exit !f }' /proc/self/mounts; then
      die "something is still mounted under $r (a chroot left by a killed run?); unmount it first"
    fi
  done
}

# assert_scratch_copy SRC   before a test copies SRC (a finished build's work directory or rootfs)
# into this checkout's $WORK: WORK and ROOTFS are inside this project, and SRC and WORK don't overlap
# in either direction (rsync --delete into the wrong tree; external review 2026-11-24, #55).
assert_scratch_copy() {
  assert_build_paths
  local s w
  s="$(realpath -m -- "${1:?assert_scratch_copy: no source}")"; w="$(realpath -m -- "$WORK")"
  case "$s/" in "$w"/*) die "the source ($s) is inside this checkout's WORK ($w)";; esac
  case "$w/" in "$s"/*) die "WORK ($w) is inside the source ($s)";; esac
}
