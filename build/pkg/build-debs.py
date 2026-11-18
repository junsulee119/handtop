#!/usr/bin/env python3
"""Build Handtop's own packages from a finished root filesystem (project doc update-system.md, step 2).

Every file classes.txt assigns to a package, plus that package's diversions (diversions.txt), is
copied out of <rootfs> into a package tree and built with dpkg-deb. So a package carries exactly
the bytes the image build produced, and installing it back into the image changes no file.

    sudo python3 build/pkg/build-debs.py <rootfs> <outdir> <version> [package ...]

Packages built by default: handtop-core, handtop-desktop and handtop-video (the VA driver; it
depends on the exact FFmpeg packages of the same build, version in HANDTOP_FFMPEG_VERSION). FFmpeg
itself is packaged under Debian's names by build-ffmpeg-debs.py (04c). Writes <outdir>/<name>_<version>_arm64.deb and a manifest.
"""
import fnmatch
import hashlib
import os
import shutil
import stat
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TOP = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
import importlib.util  # noqa: E402

_spec = importlib.util.spec_from_file_location("audit", os.path.join(HERE, "audit-unowned.py"))
audit = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(audit)

MAINTAINER = "Handtop <https://github.com/junsulee119/handtop>"
DESCRIPTIONS = {
    "handtop-core": ("Handtop: input daemon, Controls, system services and helpers",
                     "Hardware-facing part of Handtop for H700 handhelds: the input daemon and its\n"
                     " Controls app, hardware set-up, panel and Bluetooth checks, External Controller\n"
                     " services, session scripts, udev rules, sudoers and polkit rules."),
    "handtop-desktop": ("Handtop: desktop look, themes and apps",
                        "The Handtop desktop: labwc, Waybar, drawer and power-menu configuration, the theme\n"
                        " system and nine built-in themes, icons and cursors, the media apps, the\n"
                        " volume and brightness bar, the boot screen and nwg-drawer."),
    "handtop-video": ("Handtop: hardware video decoding",
                      "The VA-API driver for Allwinner's video engine (v4l2-request) and the exact\n"
                      " FFmpeg build with the V4L2 request API decoders that Handtop was tested with."),
}
LISTS = {"handtop-core": "base.list", "handtop-desktop": "desktop.list"}
FFMPEG_FAMILY = ("libavcodec61", "libavdevice61", "libavfilter10", "libavformat61", "libavutil59",
                 "libpostproc58", "libswresample5", "libswscale8", "ffmpeg")


def list_depends(name):
    if name == "handtop-video":
        ffv = os.environ.get("HANDTOP_FFMPEG_VERSION")
        if not ffv:
            raise SystemExit("HANDTOP_FFMPEG_VERSION is not set (build/config.sh FFMPEG_HANDTOP_VERSION)")
        return ["libva2"] + ["%s (= %s)" % (p, ffv) for p in FFMPEG_FAMILY]
    deps = []
    path = os.path.join(TOP, "build", "packages", LISTS[name])
    with open(path) as f:
        for line in f:
            word = line.split("#", 1)[0].split()
            if word:
                deps.append(word[0])
    return deps


def units():
    out = {}
    with open(os.path.join(HERE, "units.txt")) as f:
        for line in f:
            w = line.split("#", 1)[0].split()
            if w:
                out[w[0]] = w[1]
    return out


def collect(root):
    """{package: [paths]} for every unowned file classes.txt gives to a Handtop package."""
    owned = audit.owned_paths(root, ignore_prefix="handtop-")   # a reused rootfs has them already
    rules = audit.classes()
    files = {}
    for dp, dns, fns in os.walk(root):
        rel = dp[len(root):] or "/"
        if rel.startswith(audit.SKIP):
            dns[:] = []
            continue
        for name in fns + [d for d in dns if os.path.islink(os.path.join(dp, d))]:
            p = rel.rstrip("/") + "/" + name
            if p in owned or name.endswith(".pyc") or "/__pycache__/" in p + "/":
                continue
            cls = next((c for c, pat, _ in rules if fnmatch.fnmatchcase(p, pat)), None)
            if cls is None:
                raise SystemExit("unclassified file %s: run audit-unowned.py" % p)
            files.setdefault(cls, []).append(p)
    for path, pkg in audit.diversions().items():
        files.setdefault(pkg, []).append(path)
    return files


def script(body):
    return "#!/bin/sh\nset -e\n" + body


def maintainer_scripts(pkg, paths, unit_policy):
    divs = [(p, k) for p, k in audit.diversions().items() if k == pkg]
    # No --rename when adding: the file on disk stays where it is, so dpkg compares it with ours
    # like any conffile (identical: taken over; edited by the user: kept, ours saved as .dpkg-dist).
    # Debian's own later versions of that path go to <path>.debian. Removing Handtop's package
    # moves a .debian file back, if there is one.
    add = "".join("    dpkg-divert --package %s --add --no-rename --divert '%s.debian' '%s'\n" % (pkg, p, p)
                  for p, _ in divs)
    rem = "".join("    dpkg-divert --package %s --rename --remove '%s'\n" % (pkg, p) for p, _ in divs)
    out = {}
    if divs:
        out["preinst"] = script('case "$1" in install|upgrade)\n%s    ;;\nesac\n' % add)
        out["postrm"] = script('case "$1" in remove|abort-install|disappear)\n%s    ;;\nesac\n' % rem)
    mine = [u for u, pol in unit_policy.items() if pol == "enable" and "/etc/systemd/system/" + u in paths]
    sudoers = [p for p in paths if p.startswith("/etc/sudoers.d/")]
    body = 'if [ "$1" = configure ]; then\n'
    for s in sudoers:
        body += "    visudo -cf '%s' >/dev/null\n" % s
    if mine:
        # Enable each unit once: on a fresh install, or the first time a version brings it.
        # Units the user disabled later stay disabled. Never start, stop or restart anything:
        # hardware owners must not be restarted behind their back (docs/hardware-safety.md).
        body += "    mkdir -p /var/lib/handtop\n    seen=/var/lib/handtop/units-enabled\n    touch \"$seen\"\n"
        body += "    for u in %s; do\n" % " ".join(mine)
        body += '        grep -qx "$u" "$seen" && continue\n'
        body += '        systemctl enable "$u" >/dev/null 2>&1 || echo "handtop: could not enable $u" >&2\n'
        body += '        echo "$u" >> "$seen"\n    done\n'
    if any(p.startswith("/etc/systemd/") for p in paths):
        body += "    [ -d /run/systemd/system ] && systemctl daemon-reload || true\n"
    if any(p.startswith("/etc/udev/") for p in paths):
        body += "    [ -d /run/udev ] && udevadm control --reload || true\n"
    if any(p.startswith("/usr/local/share/applications/") for p in paths):
        body += "    command -v update-desktop-database >/dev/null && update-desktop-database -q /usr/local/share/applications || true\n"
    body += "    :\nfi\n"
    out["postinst"] = script(body)
    return out


def build(root, outdir, version, pkg, paths, unit_policy):
    tree = os.path.join(outdir, "tree", pkg)
    if os.path.exists(tree):
        shutil.rmtree(tree)
    os.makedirs(os.path.join(tree, "DEBIAN"))
    conffiles, md5, size = [], [], 0
    for p in sorted(paths):
        src = root + p
        dst = tree + p
        os.makedirs(os.path.dirname(dst), mode=0o755, exist_ok=True)
        st = os.lstat(src)
        if st.st_uid != 0 or st.st_gid != 0:
            raise SystemExit("%s is not owned by root:root in the rootfs" % p)
        if stat.S_ISLNK(st.st_mode):
            os.symlink(os.readlink(src), dst)
            continue
        if not stat.S_ISREG(st.st_mode):
            raise SystemExit("%s is not a regular file or link" % p)
        shutil.copyfile(src, dst)
        os.chmod(dst, stat.S_IMODE(st.st_mode))
        size += st.st_size
        with open(src, "rb") as f:
            md5.append("%s  %s" % (hashlib.md5(f.read()).hexdigest(), p.lstrip("/")))
        if p.startswith("/etc/"):
            conffiles.append(p)
    for dp, dns, _ in os.walk(tree):
        for d in dns:
            os.chmod(os.path.join(dp, d), 0o755)
    deps = list_depends(pkg)
    if pkg == "handtop-desktop":
        deps.insert(0, "handtop-core (= %s)" % version)
    short, long_ = DESCRIPTIONS[pkg]
    control = ("Package: %s\nVersion: %s\nArchitecture: arm64\nMaintainer: %s\nSection: misc\n"
               "Priority: optional\nInstalled-Size: %d\nDepends: %s\nHomepage: https://github.com/junsulee119/handtop\n"
               "Description: %s\n %s\n") % (pkg, version, MAINTAINER, size // 1024 + 1, ", ".join(deps), short, long_)
    d = os.path.join(tree, "DEBIAN")
    with open(os.path.join(d, "control"), "w") as f:
        f.write(control)
    with open(os.path.join(d, "md5sums"), "w") as f:
        f.write("\n".join(md5) + "\n")
    if conffiles:
        with open(os.path.join(d, "conffiles"), "w") as f:
            f.write("\n".join(conffiles) + "\n")
    for name, body in maintainer_scripts(pkg, paths, unit_policy).items():
        with open(os.path.join(d, name), "w") as f:
            f.write(body)
        os.chmod(os.path.join(d, name), 0o755)
    deb = os.path.join(outdir, "%s_%s_arm64.deb" % (pkg, version))
    subprocess.run(["dpkg-deb", "--root-owner-group", "-Zxz", "--build", tree, deb], check=True,
                   stdout=subprocess.DEVNULL, timeout=600)
    with open(os.path.join(outdir, "%s.manifest" % pkg), "w") as f:
        f.write("\n".join(sorted(paths)) + "\n")
    print("%s: %d files, %d conffiles, %d diversions -> %s" % (
        pkg, len(paths), len(conffiles), sum(1 for p, k in audit.diversions().items() if k == pkg), deb))


def main():
    if len(sys.argv) < 4:
        raise SystemExit(__doc__)
    root, outdir, version = sys.argv[1].rstrip("/"), sys.argv[2], sys.argv[3]
    want = sys.argv[4:] or ["handtop-core", "handtop-desktop", "handtop-video"]
    os.makedirs(outdir, exist_ok=True)
    files = collect(root)
    # Every tracked overlay file a package gets must be in it: an empty or partial package would
    # make dpkg delete the missing files from the card on upgrade.
    import subprocess as sp
    tracked = sp.run(["git", "-C", TOP, "ls-files", "overlay"], capture_output=True, text=True,
                     timeout=60).stdout.split()
    if tracked:
        rules, divs = audit.classes(), audit.diversions()
        for f in tracked:
            p = f[len("overlay"):]
            pkg = divs.get(p) or next((c for c, pat, _ in rules if fnmatch.fnmatchcase(p, pat)), None)
            if pkg in want and p not in files.get(pkg, []):
                raise SystemExit("%s would lack %s (from overlay/): refusing to build it" % (pkg, p))
    else:
        print("build-debs: not a git checkout, overlay completeness not checked", file=sys.stderr)
    unit_policy = units()
    for pkg in want:
        build(root, outdir, version, pkg, files.get(pkg, []), unit_policy)


if __name__ == "__main__":
    main()
