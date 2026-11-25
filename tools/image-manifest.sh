#!/bin/bash
# File list of a released Handtop image, for moving cards onto packages (step 7 of the update system):
# one line per file of the root filesystem and the boot partition (paths prefixed /boot/firmware):
#   path <TAB> type (f/l/d) <TAB> mode (octal) <TAB> sha256 or link target <TAB> o / u (a package owns
#   it in the image's dpkg database, or not)
# Unprivileged (debugfs and mtools read the partitions straight from the image).
#   tools/image-manifest.sh handtop-20261118-v0.4.1.img.xz out.tsv   (needs about 8 GB in $TMPDIR)
set -euo pipefail
IMG=$(realpath "$1"); OUT=$(realpath -m "$2")
T=$(mktemp -d "${TMPDIR:-/tmp}/image-manifest.XXXXXX")
trap 'rm -rf "$T"' EXIT
case "$IMG" in *.xz) xz -dc "$IMG" > "$T/img" ;; *) cp --sparse=always "$IMG" "$T/img" ;; esac
read -r BOOT_START BOOT_SIZE < <(sfdisk -d "$T/img" | awk -F'[=,]' '/img1 /{print $2+0, $4+0}')
read -r ROOT_START ROOT_SIZE < <(sfdisk -d "$T/img" | awk -F'[=,]' '/img2 /{print $2+0, $4+0}')
dd if="$T/img" of="$T/root.ext4" bs=512 skip="$ROOT_START" count="$ROOT_SIZE" status=none
dd if="$T/img" of="$T/boot.vfat" bs=512 skip="$BOOT_START" count="$BOOT_SIZE" status=none
rm "$T/img"
mkdir "$T/root" "$T/boot"
debugfs -R "rdump / $T/root" "$T/root.ext4" >/dev/null 2>"$T/debugfs.err" || { cat "$T/debugfs.err"; exit 1; }
rm "$T/root.ext4"
mcopy -s -n -i "$T/boot.vfat" ::/* "$T/boot/"
python3 - "$T" "$OUT" <<'P'
import hashlib, os, stat, sys
t, out = sys.argv[1:3]
owned = set()
info = t + "/root/var/lib/dpkg/info"
for n in os.listdir(info):
    if n.endswith(".list"):
        with open(os.path.join(info, n), errors="replace") as fh:
            owned.update(l.rstrip("\n") for l in fh)
rows = []
for top, prefix in ((t + "/root", ""), (t + "/boot", "/boot/firmware")):
    for dp, dns, fns in os.walk(top):
        for n in sorted(dns + fns):
            p = os.path.join(dp, n)
            rel = prefix + p[len(top):]
            st = os.lstat(p)
            if stat.S_ISLNK(st.st_mode):
                rows.append((rel, "l", "%o" % stat.S_IMODE(st.st_mode), os.readlink(p), "o" if rel in owned else "u"))
            elif stat.S_ISDIR(st.st_mode):
                rows.append((rel, "d", "%o" % stat.S_IMODE(st.st_mode), "", "o" if rel in owned else "u"))
            elif stat.S_ISREG(st.st_mode):
                h = hashlib.sha256()
                with open(p, "rb") as f:
                    for b in iter(lambda: f.read(1 << 20), b""):
                        h.update(b)
                rows.append((rel, "f", "%o" % stat.S_IMODE(st.st_mode), h.hexdigest(), "o" if rel in owned else "u"))
with open(out, "w") as f:
    for r in sorted(rows):
        f.write("\t".join(r) + "\n")
print("%d entries -> %s" % (len(rows), out))
P
