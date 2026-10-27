# Shared build configuration. Sourced by build scripts.
TOP="$(cd "$(dirname "$(realpath "${BASH_SOURCE[0]}")")/.." && pwd)"   # absolute, independent of $HOME/sudo
WORK="${WORK:-$TOP/work}"

RELEASE_VERSION="0.3.0"            # used in the image name when not building from a git checkout
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
KTOOLCHAIN_URL="https://developer.arm.com/-/media/Files/downloads/gnu/15.2.rel1/binrel/arm-gnu-toolchain-15.2.rel1-x86_64-aarch64-none-linux-gnu.tar.xz"
KTOOLCHAIN_SHA256="9a685b335bd709d683a8c782253c37e8c36c10e6924e59e39d4769b02132eb43"
CMA_SIZE="256M"                    # contiguous memory for the decoder (no IOMMU, see docs/video-decode.md)

# FFmpeg with the V4L2 request-API hwaccels (04c-v4l2-ffmpeg.sh): Kwiboo's tree, the same
# patchset Moonlight embeds. Pinned commit of branch v4l2-request-n7.1.3, which is rebased on
# FFmpeg n7.1.3 and reports the same libav ABI as Debian's ffmpeg 7.1.5, so nothing else is
# rebuilt (mpv keeps working against the replaced libs).
FFMPEG_V4L2REQ_URL="https://github.com/Kwiboo/FFmpeg"
FFMPEG_V4L2REQ_PIN="fad85d9c76611c09b561167ab405c667a0dcdeb7"

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
GO_VERSION="1.27.1"                # pinned Go release, downloaded by 00-host-deps.sh (SHA-256 checked)
GO_SHA256_AMD64="63d339f0da5ab53635a56f2490a7984dfe12dfcff22ad749f63edaf590168445"
GO_SHA256_ARM64="3450b45a3f9ee8568792736a5c5e70a1f2e9b36c35a8f74958c03e51d7d92bec"
GO_DEFAULT="$WORK/tools/go/bin/go"
GO_TOOLCHAIN="${GO_TOOLCHAIN:-$GO_DEFAULT}"   # or set to your own Go >= 1.25

source "$TOP/build/lib/safety.sh"

# Image layout
IMAGE_NAME="handtop"
DISK_ID="0x52473335"               # MBR disk id ("RG35"); root=PARTUUID=52473335-02
BOOT_START_MIB=16                  # U-Boot lives in the first 16 MiB (SPL at 8 KiB)
BOOT_SIZE_MIB=256
DEFAULT_DTB="sun50i-h700-anbernic-rg35xx-h.dtb"
