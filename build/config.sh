# Shared build configuration. Sourced by build scripts.
# shellcheck shell=bash
# shellcheck disable=SC2034  # every variable here is read by the scripts that source this file
TOP="$(cd "$(dirname "$(realpath "${BASH_SOURCE[0]}")")/.." && pwd)"   # absolute, independent of $HOME/sudo
WORK="${WORK:-$TOP/work}"

RELEASE_VERSION="0.3.7"            # used in the image name when not building from a git checkout
RAM_TYPE="${RAM_TYPE:-DDR4}"          # DDR4 (default) or DDR3 depending on board revision

ROCKNIX_VERSION="20261001"
ROCKNIX_IMAGE="ROCKNIX-H700.aarch64-${ROCKNIX_VERSION}-${RAM_TYPE}.img.gz"
ROCKNIX_URL="https://github.com/ROCKNIX/distribution/releases/download/${ROCKNIX_VERSION}/${ROCKNIX_IMAGE}"

ROCKNIX_DL="$WORK/download"        # downloaded image + checksum
ROCKNIX_EX="$WORK/rocknix"         # extracted hardware layer

DEBIAN_SUITE="trixie"
DEBIAN_MIRROR="https://deb.debian.org/debian"

ROOTFS="$WORK/rootfs"              # Debian root filesystem being built
KVER="7.2.0"                       # ROCKNIX kernel version (must match modules/)
# Hardware video decoder module (06b-cedrus.sh): same kernel source + compiler as ROCKNIX
LINUX_VERSION="7.2"
LINUX_URL="https://cdn.kernel.org/pub/linux/kernel/v7.x/linux-${LINUX_VERSION}.tar.xz"
LINUX_SHA256="f9fef3d14c0df53819026f4be74459835c2a0b0dcbf5b5bbd9ea19f0829402b3"
# Kernel compiler: Arm's GCC release ROCKNIX uses, in the build for this host (x86_64 or arm64;
# both checksums from Arm's .sha256asc files). Same compiler version either way.
KTOOLCHAIN_VERSION="15.2.rel1"
KTOOLCHAIN_SHA256_X86_64="9a685b335bd709d683a8c782253c37e8c36c10e6924e59e39d4769b02132eb43"
KTOOLCHAIN_SHA256_AARCH64="97e3f600c00413088bb21109475443f9a1c57b4f75336a6e820acd43b065f875"
KTOOLCHAIN_HOST="$(uname -m)"
case "$KTOOLCHAIN_HOST" in
  x86_64)  KTOOLCHAIN_SHA256="$KTOOLCHAIN_SHA256_X86_64" ;;
  aarch64) KTOOLCHAIN_SHA256="$KTOOLCHAIN_SHA256_AARCH64" ;;
  *)       KTOOLCHAIN_SHA256="" ;;   # 06b-cedrus.sh stops with a message
esac
KTOOLCHAIN_URL="https://developer.arm.com/-/media/Files/downloads/gnu/${KTOOLCHAIN_VERSION}/binrel/arm-gnu-toolchain-${KTOOLCHAIN_VERSION}-${KTOOLCHAIN_HOST}-aarch64-none-linux-gnu.tar.xz"
# Cedrus VP9 series in build/kernel/libreelec/: the LibreELEC.tv commit its files were copied
# from. The patches are in this repo, so the build never fetches it; it only tells the weekly
# upstream check (git-path, build/upstreams.conf) where to look for newer changes.
LIBREELEC_CEDRUS_COMMIT="f59641eb70c727cc81e33508177ac700abac81ab"
# Gamepad / motor driver rebuilt with our fix (06d-joypad.sh): the rocknix-joypad version ROCKNIX
# $ROCKNIX_VERSION ships (its package.mk: PKG_VERSION / PKG_SHA256)
JOYPAD_COMMIT="d02ed13aae08113f6f9e0e9d699cb29bb3450fa2"
JOYPAD_URL="https://github.com/ROCKNIX/rocknix-joypad/archive/${JOYPAD_COMMIT}.tar.gz"
JOYPAD_SHA256="89ade1769d6eb7b4f37265f26407a422cdbcf517487f80eb1c29964904ca138e"
CMA_SIZE="256M"                    # contiguous memory for the decoder (no IOMMU, see docs/video-decode.md)

# FFmpeg with the V4L2 request-API hwaccels (04c-v4l2-ffmpeg.sh) = FFmpeg release + Kwiboo's
# patchset (the one Moonlight embeds), applied as a diff.
# - Base: the FFmpeg release Debian ships (trixie: 7.1.5), so the security fixes Debian has are
#   in ours too and the libav ABI matches the one mpv, Chromium and VLC were built against.
#   When Debian moves on (7.1.6, ...), bump FFMPEG_VERSION / FFMPEG_COMMIT to the same release:
#   docs/video-decode.md, "Updating FFmpeg".
# - Patchset: branch v4l2-request-n7.1.3 is KWIBOO_COMMITS commits on top of n7.1.3
#   (KWIBOO_BASE); the build applies diff KWIBOO_BASE..KWIBOO_PIN onto the base.
FFMPEG_URL="https://github.com/FFmpeg/FFmpeg"
FFMPEG_VERSION="7.1.5"
FFMPEG_COMMIT="3a0867c2bfda4a4d4309ca1a8cbdc6175e67f587"   # tag n7.1.5
KWIBOO_URL="https://github.com/Kwiboo/FFmpeg"
KWIBOO_BASE="f46e514491172d15bd74b4abb1814cd2f05a763e"     # tag n7.1.3
KWIBOO_PIN="fad85d9c76611c09b561167ab405c667a0dcdeb7"      # head of v4l2-request-n7.1.3
KWIBOO_COMMITS=14

# Target system identity
HOSTNAME_TARGET="rg35xxh"
USER_NAME="rg"
USER_DEFAULT_PASSWORD="rg35xxh"    # documented default; SSH stays off until the user sets their own (Apps -> Enable SSH)
LOCALE="en_US.UTF-8"
TIMEZONE="Etc/UTC"                 # change on the device: sudo timedatectl set-timezone <Area/City>

ROOT_LABEL="rg35xxh-root"
BOOT_LABEL="RG35XXHBOOT"           # FAT label, max 11 chars

# Optional extra CA for TLS-inspecting proxies (used only during the build, never shipped).
BUILD_EXTRA_CA="${BUILD_EXTRA_CA:-}"

# nwg-drawer (not packaged in trixie; cross-compiled from source)
NWG_DRAWER_VERSION="v0.7.5"
GO_VERSION="1.27.3"                # pinned Go release, downloaded by 00-host-deps.sh (SHA-256 checked)
GO_SHA256_AMD64="65efbc80fdc1fa2cd2631cad5b481777a68e8725f34e89f50fc6ac714e379b40"
GO_SHA256_ARM64="a06e99309dbcbdca1a8ccd2282c3ee146e55930886e26b4f1193269587165f49"
GO_DEFAULT="$WORK/tools/go/bin/go"
GO_TOOLCHAIN="${GO_TOOLCHAIN:-$GO_DEFAULT}"   # or set to your own Go >= 1.25

source "$TOP/build/lib/safety.sh"

# Image layout
IMAGE_NAME="handtop"
DISK_ID="0x52473335"               # MBR disk id ("RG35"); root=PARTUUID=52473335-02
BOOT_START_MIB=16                  # U-Boot lives in the first 16 MiB (SPL at 8 KiB)
BOOT_SIZE_MIB=256
DEFAULT_DTB="sun50i-h700-anbernic-rg35xx-h.dtb"
REV6_DTB="sun50i-h700-anbernic-rg35xx-h-rev6-panel.dtb"   # newer screen panel; picked at boot (docs/services/panel.md)
