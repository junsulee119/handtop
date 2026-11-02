#!/bin/bash
# Boot the built image's root filesystem in QEMU (arm64 "virt" machine, 640x480 virtio GPU)
# to test the whole boot: systemd, first-boot services (resize, SSH keys, Wi-Fi import,
# boot logs on the FAT partition), auto-login and the labwc desktop.
# The ROCKNIX kernel has no virtio support, so a Debian kernel (+ its modules, added to a
# test copy of the root filesystem only) is used. Hardware-specific parts are not tested here.
set -euo pipefail
source "$(dirname "$(realpath "$0")")/../build/config.sh"
assert_rootfs
WAIT="${WAIT:-330}"                       # seconds to run before screenshots/shutdown
Q="$WORK/qemu"; X="$Q/x"
MD="$X/usr/lib/modules"; [ -d "$MD" ] || MD="$X/lib/modules"
KV="$(ls "$MD")"
depmod -b "$(dirname "$(dirname "$MD")")" "$KV"   # modules.dep for resolving initramfs modules
IMG="$(ls -t "$WORK"/out/*.img | head -1)"
T="$Q/run"; [ -e "$T" ] && safe_rm -r "$T"; mkdir -p "$T"
echo "image: $IMG  kernel: $KV"

# --- test root filesystem = rootfs + Debian kernel modules
TR="$Q/rootfs-test"; [ -e "$TR" ] && safe_rm -r "$TR"
cp -a "$ROOTFS" "$TR"
mkdir -p "$TR/usr/lib/modules"; cp -a "$MD/$KV" "$TR/usr/lib/modules/"
depmod -b "$TR" "$KV"
ROOT_START_MIB=$(( BOOT_START_MIB + BOOT_SIZE_MIB ))
ROOT_SIZE_MIB=$(( $(sfdisk -d "$IMG" | awk -F'size=' '/img2/ {split($2,a,","); print a[1]}') / 2048 ))
cp --sparse=always "$IMG" "$T/test.img"
mkfs.ext4 -q -F -L "$ROOT_LABEL" -d "$TR" -E root_owner=0:0 "$T/root.ext4" "${ROOT_SIZE_MIB}M"
dd if="$T/root.ext4" of="$T/test.img" bs=1M seek="$ROOT_START_MIB" conv=notrunc,sparse status=none
safe_rm "$T/root.ext4"; safe_rm -r "$TR"
truncate -s +1G "$T/test.img"          # spare space: first-boot resize must claim it

# --- minimal initramfs: busybox + virtio_blk/ext4, then switch_root
I="$T/initrd"; mkdir -p "$I"/{bin,dev,proc,sys,root,m}
cp "$(find "$X" -path "*bin/busybox" -type f | head -1)" "$I/bin/busybox"
need="virtio_blk ext4"
# resolve dependencies with modprobe's own resolver against the test tree
for m in $need; do
  modprobe -d "$(dirname "$(dirname "$MD")")" -S "$KV" --show-depends "$m" 2>/dev/null | awk '/^insmod/ {print $2}'
done | awk '!seen[$0]++' > "$T/mods.txt"
while read -r f; do
  b=$(basename "$f"); cp "$f" "$I/m/$b"
  case "$b" in *.xz) xz -d "$I/m/$b";; *.zst) zstd -q -d --rm "$I/m/$b";; esac
done < "$T/mods.txt"
sed 's|.*/||; s/\.\(xz\|zst\)$//' "$T/mods.txt" > "$I/modules.list"
cat > "$I/init" <<'S'
#!/bin/busybox sh
/bin/busybox --install -s /bin
mount -t proc proc /proc; mount -t sysfs sys /sys; mount -t devtmpfs dev /dev
for m in $(cat /modules.list); do insmod /m/$m; done
for i in $(seq 1 50); do [ -b /dev/vda2 ] && break; sleep 0.2; done
mount -o ro /dev/vda2 /root || { echo "INITRD: cannot mount root"; exec sh; }
umount /proc /sys
exec switch_root /root /sbin/init
S
chmod +x "$I/init"
(cd "$I" && find . | cpio -o -H newc --quiet | gzip -1) > "$T/initrd.gz"
echo "initramfs modules: $(tr '\n' ' ' < "$I/modules.list")"

# --- run
qemu-system-aarch64 -M virt -cpu cortex-a53 -smp 4 -m 1024 \
  -kernel "$X/boot/vmlinuz-$KV" -initrd "$T/initrd.gz" \
  -append "console=ttyAMA0 loglevel=4" \
  -drive file="$T/test.img",format=raw,if=virtio \
  -device virtio-gpu-pci,xres=640,yres=480 \
  -netdev user,id=n0 -device virtio-net-pci,netdev=n0,romfile= \
  -display none -serial file:"$T/serial.log" \
  -monitor unix:"$T/mon.sock",server,nowait &
QPID=$!
mon() { python3 - "$T/mon.sock" "$1" <<'P'
import socket, sys, time
s = socket.socket(socket.AF_UNIX); s.connect(sys.argv[1]); time.sleep(0.3); s.recv(65536)
s.sendall((sys.argv[2] + "\n").encode()); time.sleep(1.5); s.close()
P
}
sleep "$WAIT"
mon "screendump $T/screen.ppm" || true
mon "quit" || true   # (Power key is ignored by logind by design, so no ACPI shutdown)
for _ in $(seq 1 30); do kill -0 $QPID 2>/dev/null || break; sleep 1; done
kill $QPID 2>/dev/null || true
python3 - "$T/screen.ppm" "$WORK/screens/7-qemu-desktop.png" <<'P' || true
import sys, zlib, struct
d = open(sys.argv[1], 'rb').read()
parts = d.split(b'\n', 3); w, h = map(int, parts[1].split()); px = parts[3]
raw = b''.join(b'\x00' + px[y*w*3:(y+1)*w*3] for y in range(h))
def chunk(t, b): return struct.pack('>I', len(b)) + t + b + struct.pack('>I', zlib.crc32(t + b) & 0xffffffff)
open(sys.argv[2], 'wb').write(b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0)) + chunk(b'IDAT', zlib.compress(raw)) + chunk(b'IEND', b''))
P
echo "== serial log (tail)"; tail -n 25 "$T/serial.log"
echo "== FAT partition after boot"
MTOOLS_SKIP_CHECK=1 mdir -/ -i "$T/test.img@@$(( BOOT_START_MIB * 1024 * 1024 ))" ::/logs 2>/dev/null | grep -i boot || true
MTOOLS_SKIP_CHECK=1 mcopy -o -i "$T/test.img@@$(( BOOT_START_MIB * 1024 * 1024 ))" '::/logs/boot-*.txt' "$T/" 2>/dev/null || true
ls "$T"/boot-*.txt 2>/dev/null
