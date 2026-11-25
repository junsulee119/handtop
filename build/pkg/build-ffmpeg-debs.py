#!/usr/bin/env python3
"""Package Handtop's FFmpeg build under Debian's own binary package names (update-system.md, step 3).

Takes the files `make install` put into <stage> and splits them into the packages Debian's ffmpeg
source builds, using Debian's .debs of the same version as the reference for which file belongs
to which package, and for each package's control fields, shlibs, symbols, triggers, copyright and
changelogs. Our version is Debian's plus "+handtop<rev>" (FFMPEG_HANDTOP_REV), so apt treats ours as the newer one.

    python3 build/pkg/build-ffmpeg-debs.py <stage> <reference-debs dir> <rootfs> <outdir> <version>

Depends: entries naming another package of this family are Debian's, with Debian's version
replaced by ours where it was exact; every other dependency is computed from the ELF files we
actually built (their DT_NEEDED libraries, mapped to the rootfs packages that own them and those
packages' shlibs), because our configure enables fewer external libraries than Debian's.
Files Debian has that we don't build (ffplay, qt-faststart, static libraries, extra manpages) are
left out; files we build that Debian doesn't ship (examples) are left out too and listed.
"""
import glob
import hashlib
import os
import re
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile

SKIP_STAGE = ("/usr/share/ffmpeg/examples/",)           # Debian ships no examples in these packages
FAMILY_RE = re.compile(r"^(libav(codec|device|filter|format|util)|libpostproc|libsw(resample|scale))")


def run(*cmd, **kw):
    return subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=300, **kw).stdout


def deb_control(deb):
    fields, cur = {}, None
    for line in run("dpkg-deb", "-f", deb).splitlines():
        if line[:1] in (" ", "\t") and cur:
            fields[cur] += "\n" + line
        elif ":" in line:
            cur, val = line.split(":", 1)
            fields[cur] = val.strip()
    return fields


def deb_files(deb):
    out = []
    for line in run("dpkg-deb", "-c", deb).splitlines():
        parts = line.split(None, 5)
        if parts[0][0] in "-l":
            out.append(parts[5].split(" -> ")[0].lstrip("."))
    return out


def ctrl_member(deb, name):
    data = subprocess.run(["dpkg-deb", "--ctrl-tarfile", deb], check=True, capture_output=True, timeout=60).stdout
    with tempfile.TemporaryFile() as f:
        f.write(data)
        f.seek(0)
        with tarfile.open(fileobj=f) as t:
            for m in t.getmembers():
                if m.name.lstrip("./") == name:
                    return t.extractfile(m).read()
    return None


def split_deps(value):
    return [d.strip() for d in value.split(",") if d.strip()] if value else []


def dep_name(dep):
    return re.split(r"[\s(:]", dep.split("|")[0].strip(), 1)[0]


class Rootfs:
    """Maps a soname to the dependency the owning package's shlibs give (dpkg-shlibdeps' job)."""

    DIRS = ("/usr/lib/aarch64-linux-gnu", "/lib/aarch64-linux-gnu", "/usr/lib", "/lib")

    def __init__(self, root):
        self.root = root.rstrip("/")
        self.owner = {}
        for lst in glob.glob(self.root + "/var/lib/dpkg/info/*.list"):
            pkg = os.path.basename(lst)[:-5].split(":")[0]
            with open(lst, errors="replace") as f:
                for line in f:
                    p = line.rstrip("\n")
                    for a, b in (("/lib/", "/usr/lib/"),):
                        if p.startswith(a):
                            self.owner.setdefault(b + p[len(a):], pkg)
                    self.owner.setdefault(p, pkg)

    def shlib_dep(self, soname):
        for d in self.DIRS:
            path = d + "/" + soname
            if os.path.lexists(self.root + path):
                pkg = self.owner.get(path) or self.owner.get(os.path.realpath(self.root + path)[len(self.root):])
                if not pkg:
                    raise SystemExit("no package owns %s in the rootfs" % path)
                m = re.match(r"^(.*)\.so\.(\S+)$", soname)
                for info in glob.glob(self.root + "/var/lib/dpkg/info/%s*.shlibs" % pkg):
                    for line in open(info):
                        w = line.split(None, 2)
                        if len(w) == 3 and m and w[0] == m.group(1) and w[1] == m.group(2):
                            return w[2].strip()
                return pkg
        raise SystemExit("library %s not found in the rootfs" % soname)


def needed(path):
    out = run("readelf", "-d", path)
    return re.findall(r"\(NEEDED\)\s+Shared library: \[([^\]]+)\]", out)


def main():
    stage, refdir, root, outdir, version = sys.argv[1:6]
    stage = stage.rstrip("/")
    debian_version = None
    refs = {}
    for deb in sorted(glob.glob(os.path.join(refdir, "*.deb"))):
        c = deb_control(deb)
        refs[c["Package"]] = (deb, c, deb_files(deb))
        debian_version = debian_version or c["Version"]
    owner = {}
    for pkg, (_, _, files) in refs.items():
        for f in files:
            owner[f] = pkg
    family = set(refs)
    rfs = Rootfs(root)

    staged, skipped = {}, []
    for dp, dns, fns in os.walk(stage):
        for name in fns + [d for d in dns if os.path.islink(os.path.join(dp, d))]:
            p = os.path.join(dp, name)[len(stage):]
            if p.startswith(SKIP_STAGE):
                skipped.append(p)
                continue
            pkg = owner.get(p)
            if not pkg and p.startswith("/usr/share/doc/handtop-ffmpeg/"):
                pkg = "libavutil59"
            m = re.match(r"^/usr/include/aarch64-linux-gnu/(lib[a-z]+)/[^/]+\.h$", p)
            if not pkg and m and m.group(1) + "-dev" in refs:
                pkg = m.group(1) + "-dev"      # a header Debian's FFmpeg lacks (Kwiboo's v4l2request)
            if not pkg:
                raise SystemExit("built file %s is in none of Debian's packages" % p)
            staged.setdefault(pkg, []).append(p)

    extract = tempfile.mkdtemp()
    built = []
    for pkg, (deb, ctrl, files) in sorted(refs.items()):
        if pkg not in staged:
            print("%s: nothing built for it, skipped" % pkg)
            continue
        tree = os.path.join(outdir, "tree", pkg)
        if os.path.exists(tree):
            shutil.rmtree(tree)
        os.makedirs(tree + "/DEBIAN")
        ref = os.path.join(extract, pkg)
        run("dpkg-deb", "-x", deb, ref)
        paths = list(staged[pkg])
        # Debian's documentation and lintian overrides for this package, and the manpages of the
        # programs we do build.
        for f in files:
            if f.startswith(("/usr/share/doc/%s/" % pkg, "/usr/share/lintian/overrides/")) or (
                    f.startswith("/usr/share/man/man1/") and
                    re.match(r"(ffmpeg|ffprobe)", os.path.basename(f))):
                src = ref + f
                dst = tree + f
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                if os.path.islink(src):
                    os.symlink(os.readlink(src), dst)
                else:
                    shutil.copy2(src, dst)
        size, md5 = 0, []
        elf_needed = set()
        for p in paths:
            src, dst = stage + p, tree + p
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            st = os.lstat(src)
            if stat.S_ISLNK(st.st_mode):
                os.symlink(os.readlink(src), dst)
                continue
            shutil.copyfile(src, dst)
            os.chmod(dst, stat.S_IMODE(st.st_mode))
            with open(src, "rb") as f:
                head = f.read(4)
            if head == b"\x7fELF":
                elf_needed.update(needed(src))
        for dp, dns, fns in os.walk(tree):
            if "/DEBIAN" in dp + "/":
                continue
            for d in dns:
                if d != "DEBIAN":
                    os.chmod(os.path.join(dp, d), 0o755)
            for fn in fns:
                fp = os.path.join(dp, fn)
                if not os.path.islink(fp):
                    size += os.path.getsize(fp)
                    with open(fp, "rb") as f:
                        md5.append("%s  %s" % (hashlib.md5(f.read()).hexdigest(), fp[len(tree) + 1:]))
        # Depends: Debian's family entries (exact versions turned into ours) + computed externals.
        deps = []
        for d in split_deps(ctrl.get("Depends", "")):
            if dep_name(d) in family:
                deps.append(d.replace("(= %s)" % debian_version, "(= %s)" % version))
        for so in sorted(elf_needed):
            if FAMILY_RE.match(so):
                continue
            d = rfs.shlib_dep(so)
            if dep_name(d) not in [dep_name(x) for x in deps]:
                deps.append(d)
        fields = ["Package", "Source", "Version", "Architecture", "Maintainer", "Installed-Size",
                  "Pre-Depends", "Depends", "Recommends", "Suggests", "Breaks", "Replaces", "Conflicts",
                  "Provides", "Section", "Priority", "Multi-Arch", "Homepage", "Description"]
        ctrl = dict(ctrl)
        ctrl["Version"] = version
        ctrl["Source"] = "ffmpeg (%s)" % version
        ctrl["Maintainer"] = "Handtop <https://github.com/junsulee119/handtop>"
        ctrl["Installed-Size"] = str(size // 1024 + 1)
        ctrl["Depends"] = ", ".join(deps)
        ctrl["Description"] = ctrl["Description"] + "\n .\n Handtop build: Debian's ffmpeg %s plus the V4L2 request API\n hardware decoders for Allwinner's video engine (Cedrus)." % debian_version
        for k in ("Recommends", "Suggests"):
            ctrl.pop(k, None)     # Debian's recommend packages we don't build (ffplay's, extras)
        with open(tree + "/DEBIAN/control", "w") as f:
            for k in fields:
                if ctrl.get(k):
                    f.write("%s: %s\n" % (k, ctrl[k]))
        with open(tree + "/DEBIAN/md5sums", "w") as f:
            f.write("\n".join(sorted(md5)) + "\n")
        for member in ("shlibs", "symbols", "triggers"):
            data = ctrl_member(deb, member)
            if data is not None:
                if member == "symbols":
                    data = data.replace(("(= %s)" % debian_version).encode(), ("(= %s)" % version).encode())
                with open(tree + "/DEBIAN/" + member, "wb") as f:
                    f.write(data)
        arch = ctrl.get("Architecture", "arm64")
        out = os.path.join(outdir, "%s_%s_%s.deb" % (pkg, version.split(":")[-1], arch))
        run("dpkg-deb", "--root-owner-group", "-Zxz", "--build", tree, out)
        built.append(out)
        print("%s: %d files -> %s" % (pkg, len(paths), out))
    shutil.rmtree(extract)
    if skipped:
        print("not packaged (Debian ships none): %d files under /usr/share/ffmpeg/examples" % len(skipped))
    with open(os.path.join(outdir, "ffmpeg-debs.list"), "w") as f:
        f.write("\n".join(built) + "\n")


if __name__ == "__main__":
    main()
