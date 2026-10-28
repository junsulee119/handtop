#!/bin/bash
# Gamepad and vibration motor driver: rebuild ROCKNIX's rocknix-singleadc-joypad.ko (the exact
# rocknix-joypad version ROCKNIX $ROCKNIX_VERSION ships) with our fix and install it over
# ROCKNIX's copy. See docs/kernel.md and build/kernel/rocknix-joypad/*.patch.
#
# Why: its force-feedback callback took a mutex in atomic context; a change of vibration strength
# could then lock up the whole handheld with the motor running (2026-10-28).
# Needs the ROCKNIX kernel tree built by 06b-cedrus.sh (same tree, so symbol versions match).
set -euo pipefail
source "$(dirname "$0")/config.sh"
source "$(dirname "$0")/lib/chroot.sh"
trap chroot_umount EXIT
assert_rootfs

K="$WORK/kernel"
T="$K/linux-$LINUX_VERSION-rocknix-$ROCKNIX_VERSION"
export ARCH=arm64 CROSS_COMPILE="$K/gcc15/bin/aarch64-none-linux-gnu-"
[ -f "$T/Module.symvers" ] || die "kernel tree $T not built: run 06b-cedrus.sh first"
[ -f "$K/rocknix.versions" ] || die "$K/rocknix.versions missing: run 06b-cedrus.sh first"

# 1. Source at ROCKNIX's pinned commit
f="$K/rocknix-joypad-$JOYPAD_COMMIT.tar.gz"
[ -f "$f" ] || { curl -sSfL -o "$f.part" "$JOYPAD_URL"; mv "$f.part" "$f"; }
echo "$JOYPAD_SHA256  $f" | sha256sum -c --quiet - || die "checksum mismatch: $f"
M="$K/rocknix-joypad"
[ ! -e "$M" ] || safe_rm -r "$M"
mkdir -p "$M"
tar xf "$f" -C "$M" --strip-components=1

# 2. Our patches, then build (H700: only the single-ADC driver)
for p in "$TOP"/build/kernel/rocknix-joypad/*.patch; do patch -d "$M" -p1 -s --forward < "$p"; done
grep -q "Handtop: ff-memless calls this in atomic context" "$M/rocknix-singleadc-joypad.c" \
  || die "the rumble patch did not apply (build/kernel/rocknix-joypad/)"
make -C "$T" -s M="$M" DEVICE=H700 modules
KO="$M/rocknix-singleadc-joypad.ko"

# 3. Same kernel interface as ROCKNIX's own build of it: every imported symbol version must match
RK="$ROCKNIX_EX/modules/$KVER/rocknix-joypad/rocknix-singleadc-joypad.ko"
[ -f "$RK" ] || die "ROCKNIX's module not found at $RK"
bad=$(/sbin/modprobe --dump-modversions "$KO" | awk 'NR==FNR{r[$2]=$1; next} ($2 in r) && r[$2]!=$1' "$K/rocknix.versions" -)
[ -z "$bad" ] || die "symbol version mismatch against the ROCKNIX kernel:\n$bad"
[ "$(/sbin/modinfo -F vermagic "$KO")" = "$(/sbin/modinfo -F vermagic "$RK")" ] || die "vermagic mismatch"
diff <(/sbin/modprobe --dump-modversions "$RK" | sort -k2) <(/sbin/modprobe --dump-modversions "$KO" | sort -k2) >/dev/null \
  || echo "note: imports differ from ROCKNIX's module (expected only if a patch adds or drops a call)"

# 4. Install over ROCKNIX's copy (same path, so nothing else changes)
install -m644 "$KO" "$ROOTFS/usr/lib/modules/$KVER/rocknix-joypad/rocknix-singleadc-joypad.ko"
chroot_mount
in_chroot "depmod -a $KVER"
echo "Joypad driver with the rumble fix installed ($(/sbin/modinfo -F vermagic "$KO"))."
