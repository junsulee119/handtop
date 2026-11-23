#!/usr/bin/env python3
"""Kernel-modules package and the metapackages (project doc update-system.md, step 4).

    python3 build/pkg/build-platform-debs.py <rootfs> <outdir> <version> <kernel release> <KERNEL sha256>

handtop-modules-h700-<kernel>: the modules in modules.txt, copied from <rootfs>. They only work
with the exact kernel they were built against, which lives on the boot partition and changes
only by reflashing, so the package refuses to unpack unless /etc/handtop/boot-abi names the same
kernel (its SHA-256). On an upgrade the patched joypad driver being replaced is kept as
/var/lib/handtop/modules/rocknix-singleadc-joypad.ko.previous for the recovery path (never
ROCKNIX's original, which has the vibration deadlock, docs/kernel.md). The new modules take
effect at the next restart: the package asks for one and loads nothing.

handtop-platform-h700: depends on the modules package of the kernel the image has.
handtop: depends on every Handtop package of this version.
"""
import hashlib
import os
import shutil
import stat
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
MAINT = "Handtop <https://github.com/junsulee119/handtop>"
HOME = "https://github.com/junsulee119/handtop"
JOYPAD = "rocknix-joypad/rocknix-singleadc-joypad.ko"


def deb(outdir, name, version, arch, depends, short, long_, files=(), scripts=None, root=None, fields=None):
    tree = os.path.join(outdir, "tree", name)
    if os.path.exists(tree):
        shutil.rmtree(tree)
    os.makedirs(tree + "/DEBIAN")
    md5, size = [], 0
    for p in files:
        src, dst = root + p, tree + p
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        st = os.lstat(src)
        if not stat.S_ISREG(st.st_mode):
            raise SystemExit("%s is not a regular file" % p)
        shutil.copyfile(src, dst)
        os.chmod(dst, 0o644)
        size += st.st_size
        with open(src, "rb") as f:
            md5.append("%s  %s" % (hashlib.md5(f.read()).hexdigest(), p.lstrip("/")))
    for dp, dns, _ in os.walk(tree):
        for d in dns:
            if d != "DEBIAN":
                os.chmod(os.path.join(dp, d), 0o755)
    with open(tree + "/DEBIAN/control", "w") as f:
        f.write("Package: %s\nVersion: %s\nArchitecture: %s\nMaintainer: %s\nSection: %s\nPriority: optional\n"
                "Installed-Size: %d\n%s%sHomepage: %s\nDescription: %s\n %s\n" % (
                    name, version, arch, MAINT, "kernel" if files else "metapackages", size // 1024 + 1,
                    ("Depends: %s\n" % ", ".join(depends)) if depends else "",
                    "".join("%s: %s\n" % kv for kv in (fields or {}).items()), HOME, short, long_))
    if md5:
        with open(tree + "/DEBIAN/md5sums", "w") as f:
            f.write("\n".join(md5) + "\n")
    for n, body in (scripts or {}).items():
        with open(tree + "/DEBIAN/" + n, "w") as f:
            f.write(body)
        os.chmod(tree + "/DEBIAN/" + n, 0o755)
    out = os.path.join(outdir, "%s_%s_%s.deb" % (name, version, arch))
    subprocess.run(["dpkg-deb", "--root-owner-group", "-Zxz", "--build", tree, out], check=True,
                   stdout=subprocess.DEVNULL, timeout=600)
    print("%s: %d files -> %s" % (name, len(files), out))


def release_notes(changelog, release, limit=12):
    """Short lines for the Update app from CHANGELOG.md's "## v<release>" section: its summary line,
    then each top-level bullet's bold lead (else its start). None if there is no such section."""
    import re
    try:
        text = open(changelog, encoding="utf-8").read()
    except OSError:
        return None
    m = re.search(r"^## v%s\s*$(.*?)(?=^## |\Z)" % re.escape(release), text, re.M | re.S)
    if not m:
        return None

    def plain(s):
        s = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", s)          # links -> their text
        return re.sub(r"[`*]", "", s).strip()

    lines = []
    for line in m.group(1).splitlines():
        if not line.strip() or line.startswith(("  ", "\t")):
            continue
        if line.startswith("- "):
            b = re.match(r"- \*\*(.+?)\*\*", line)
            t = plain(b.group(1)) if b else plain(line[2:])
            t = t.rstrip(".:")
            if t.lower().startswith("for builders"):
                continue                                   # nothing to see on the handheld
        elif lines:
            continue                                       # only the first paragraph's summary
        else:
            t = plain(line)
        cap = 100 if lines else 200
        if len(t) > cap:
            t = t[:cap - 3].rsplit(" ", 1)[0] + "..."
        lines.append(t)
    return lines[:limit] or None


def meta_fields():
    rel = os.environ.get("HANDTOP_RELEASE_VERSION")
    if not rel:
        return {}
    f = {"Handtop-Release": rel}
    # HANDTOP_CHANGELOG: another changelog (tools/update-device-archive.sh's test release)
    notes = release_notes(os.environ.get("HANDTOP_CHANGELOG") or
                          os.path.join(os.path.dirname(os.path.dirname(HERE)), "CHANGELOG.md"), rel)
    if notes:
        f["Handtop-Changes"] = "\n " + "\n ".join(notes)
    return f


def main():
    root, outdir, version, kver, ksha = sys.argv[1:6]
    root = root.rstrip("/")
    import re
    if not re.fullmatch(r"[0-9a-f]{64}", ksha):
        raise SystemExit("not a SHA-256: %r" % ksha)
    os.makedirs(outdir, exist_ok=True)
    rel = [l.split("#", 1)[0].strip() for l in open(os.path.join(HERE, "modules.txt"))]
    files = ["/usr/lib/modules/%s/%s" % (kver, r) for r in rel if r]
    for p in files:
        if not os.path.isfile(root + p):
            raise SystemExit("module missing in the rootfs: %s" % p)
    mod = "handtop-modules-h700-%s" % kver
    joy = "/usr/lib/modules/%s/%s" % (kver, JOYPAD)
    preinst = """#!/bin/sh
set -e
# These modules only fit the exact kernel on the boot partition (it changes only by reflashing).
want=%s
have=$(sed -n 's/^kernel_sha256=//p' /etc/handtop/boot-abi 2>/dev/null || true)
if [ "$have" != "$want" ]; then
    echo "%s: this card's kernel (${have:-unknown}) is not the one these modules were built for ($want)." >&2
    echo "A new image is needed for this update; nothing was changed." >&2
    exit 1
fi
# Keep the patched joypad driver being replaced, for the recovery path (recovery.txt).
# Only when another version is replaced: reinstalling this one must not overwrite the kept driver.
if [ "$1" = upgrade ] && [ "$2" != "%s" ] && [ -f %s ]; then
    mkdir -p /var/lib/handtop/modules
    cp %s /var/lib/handtop/modules/rocknix-singleadc-joypad.ko.previous.new
    mv /var/lib/handtop/modules/rocknix-singleadc-joypad.ko.previous.new /var/lib/handtop/modules/rocknix-singleadc-joypad.ko.previous
fi
""" % (ksha, mod, version, joy, joy)
    postinst = """#!/bin/sh
set -e
if [ "$1" = configure ]; then
    # Index only; nothing is loaded now. The modules take effect at the next restart.
    [ -d /usr/lib/modules/%s ] && depmod -a %s
    if [ -n "$2" ] && [ -d /run ]; then
        touch /run/reboot-required
        grep -qx %s /run/reboot-required.pkgs 2>/dev/null || echo %s >> /run/reboot-required.pkgs
    fi
fi
""" % (kver, kver, mod, mod)
    deb(outdir, mod, version, "arm64", [], "Handtop: kernel modules for ROCKNIX's H700 kernel %s" % kver,
        "Video decoder (Cedrus, VP9 helper), wired Xbox 360 controller function, uhid for\n"
        " Bluetooth LE input, and the gamepad driver with Handtop's vibration fix, built for\n"
        " kernel %s (KERNEL sha256 %s)." % (kver, ksha), files, {"preinst": preinst, "postinst": postinst}, root,
        # The update worker reads it before scheduling: a card with another KERNEL needs a new image.
        fields={"Handtop-Kernel-SHA256": ksha, "Handtop-Kernel-Release": kver})
    deb(outdir, "handtop-platform-h700", version, "all", ["%s (= %s)" % (mod, version)],
        "Handtop: Allwinner H700 platform", "Pulls in the kernel modules for the kernel this image has.")
    deb(outdir, "handtop", version, "all",
        ["handtop-core (= %s)" % version, "handtop-desktop (= %s)" % version,
         "handtop-video (= %s)" % version,
         # Unversioned: the keyring is never taken back by handtop=previous (a newer one may carry the
         # current signing key), so an older metapackage must accept a newer keyring.
         "handtop-keyring",
         "handtop-platform-h700 (= %s)" % version],
        "Handtop desktop for handheld consoles", "Metapackage: everything Handtop installs on top of Debian.",
        # Read by the Update app before downloading: the release and its notes, from the signed index.
        fields=meta_fields())


if __name__ == "__main__":
    main()
