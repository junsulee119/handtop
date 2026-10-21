#!/bin/bash
# Install build-host dependencies (Debian/Ubuntu host, run as root).
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq || true
apt-get install -y -qq --no-install-recommends \
  debootstrap qemu-user-static binfmt-support \
  parted fdisk dosfstools e2fsprogs mtools squashfs-tools device-tree-compiler \
  qemu-system-arm rsync xz-utils cpio lz4 zstd gzip file curl ca-certificates \
  debian-archive-keyring u-boot-tools \
  gcc-aarch64-linux-gnu pkg-config git libwayland-bin make \
  bc bison flex libelf-dev libssl-dev kmod   # kernel module build (06b-cedrus.sh)

# Register ARM64 emulation (needed to run package scripts inside the arm64 rootfs).
mountpoint -q /proc/sys/fs/binfmt_misc || mount -t binfmt_misc binfmt_misc /proc/sys/fs/binfmt_misc
if [ ! -e /proc/sys/fs/binfmt_misc/qemu-aarch64 ]; then
  if ! update-binfmts --enable qemu-aarch64 2>/dev/null; then
    cat /usr/lib/binfmt.d/qemu-aarch64.conf > /proc/sys/fs/binfmt_misc/register
  fi
fi
grep -q enabled /proc/sys/fs/binfmt_misc/qemu-aarch64 && echo "qemu-aarch64 binfmt: enabled"

# Go toolchain (>= 1.25) for cross-compiling nwg-drawer; Ubuntu/Debian packaged Go may be too old.
# Downloads the release pinned in config.sh (SHA-256 checked) unless GO_TOOLCHAIN points to your own Go.
source "$(dirname "$(realpath "$0")")/config.sh"
if [ ! -x "$GO_TOOLCHAIN" ]; then
  [ "$GO_TOOLCHAIN" = "$GO_DEFAULT" ] || die "GO_TOOLCHAIN is set but not executable: $GO_TOOLCHAIN"
  case "$(uname -m)" in
    x86_64)  GO_ARCH=amd64; GO_SHA="$GO_SHA256_AMD64" ;;
    aarch64) GO_ARCH=arm64; GO_SHA="$GO_SHA256_ARM64" ;;
    *) die "no pinned Go download for host '$(uname -m)'; install Go >= 1.25 and set GO_TOOLCHAIN" ;;
  esac
  GO_TGZ="$WORK/tools/go${GO_VERSION}.linux-${GO_ARCH}.tar.gz"
  mkdir -p "$WORK/tools"
  echo "Downloading Go ${GO_VERSION} (${GO_ARCH}) ..."
  curl -fL --retry 3 -o "$GO_TGZ" "https://go.dev/dl/go${GO_VERSION}.linux-${GO_ARCH}.tar.gz"
  echo "$GO_SHA  $GO_TGZ" | sha256sum -c - || { safe_rm "$GO_TGZ"; die "Go download checksum mismatch"; }
  [ -e "$WORK/tools/go" ] && safe_rm -r "$WORK/tools/go"
  tar -xzf "$GO_TGZ" -C "$WORK/tools"
  safe_rm "$GO_TGZ"
fi
"$GO_TOOLCHAIN" version
