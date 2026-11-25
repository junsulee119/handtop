#!/usr/bin/env python3
"""Release data for moving cards onto packages (handtop-migrate, the update worker's migrate plan):
from file lists of released images (tools/image-manifest.sh), every file a Handtop package ships
(classes.txt, diversions.txt) and every file of the boot partition, with its checksum per release.
The worker uses it to name a card's release and RAM type, and to tell a file the user edited from
one an older release put there. Variants (DDR3, DDR4) of a release share a line where they agree.

    tools/release-data.py OUT.tsv BOOT-ABI v0.4.0:DDR4=v0.4.0.tsv v0.4.0:DDR3=v0.4.0-DDR3.tsv ...
Output lines: release <TAB> variant (* when all agree) <TAB> path <TAB> type <TAB> sha256 or link target
<TAB> mode (octal, files; "" for links). Types: f / l Handtop's files; x a file of v0.4.x's own FFmpeg
build that no package owned (removed after a migration when still unowned and unchanged); k per
release "@boot-abi": /etc/handtop/boot-abi for its kernel, lines joined with ";".
BOOT-ABI is a build's /etc/handtop/boot-abi; every release's KERNEL must be the one it names.
"""
import fnmatch
import importlib.util
import os
import re
import sys

# v0.4.x built FFmpeg itself and copied it in: the libraries were Debian's (held), but the CLI, the
# headers (old location), examples and BUILDINFO belonged to no package.
LEGACY_FFMPEG = re.compile(r"/(libav[a-z]*|libsw[a-z]*|libpostproc|ffmpeg|ffprobe|handtop-ffmpeg)(/|$|[._-])")

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("audit", os.path.join(HERE, "..", "build", "pkg", "audit-unowned.py"))
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


def wanted(path, rules, divs):
    if path.startswith("/boot/firmware/"):
        return True
    if path in divs:
        return True
    cls = next((c for c, pat, _ in rules if fnmatch.fnmatchcase(path, pat)), None)
    return bool(cls and cls.startswith("handtop-"))


def main():
    out, abi_file, specs = sys.argv[1], sys.argv[2], sys.argv[3:]
    abi = [l.strip() for l in open(abi_file) if l.strip()]
    ksha = next(l.split("=", 1)[1] for l in abi if l.startswith("kernel_sha256="))
    rules, divs = audit.classes(), audit.diversions()
    data = {}                                   # release -> variant -> {path: (type, value)}
    for s in specs:
        name, fn = s.split("=", 1)
        rel, var = name.split(":")
        files = {}
        with open(fn) as f:
            for line in f:
                cols = line.rstrip("\n").split("\t")
                p, t, mode, v = cols[:4]
                owner = cols[4] if len(cols) > 4 else "o"
                if t == "f" and owner == "u" and p.startswith("/usr/") and LEGACY_FFMPEG.search(p):
                    files[p] = ("x", v, mode)       # first: classes.txt gives these to handtop-video
                elif t in ("f", "l") and wanted(p, rules, divs):
                    files[p] = (t, v, mode if t == "f" else "")
        data.setdefault(rel, {})[var] = files
    rows = []
    for rel, variants in sorted(data.items()):
        for var, files in variants.items():
            if (files.get("/boot/firmware/KERNEL") or ())[:2] != ("f", ksha):
                sys.exit("%s %s: KERNEL is not the one %s names" % (rel, var, abi_file))
        rows.append((rel, "*", "@boot-abi", "k", ";".join(abi), ""))
        paths = sorted(set().union(*variants.values()))
        for p in paths:
            vals = {var: files.get(p) for var, files in variants.items()}
            if len(set(vals.values())) == 1 and None not in vals.values():
                t, v, m = next(iter(vals.values()))
                rows.append((rel, "*", p, t, v, m))
            else:
                for var, tv in sorted(vals.items()):
                    if tv:
                        rows.append((rel, var, p) + tv)
    with open(out, "w") as f:
        f.write("# Files Handtop put on cards of each release (tools/release-data.py); read by handtop-update.\n")
        for r in rows:
            f.write("\t".join(r) + "\n")
    print("%d lines -> %s" % (len(rows), out))


if __name__ == "__main__":
    main()
