#!/usr/bin/env python3
"""Release data for moving cards onto packages (handtop-migrate, the update worker's migrate plan):
from file lists of released images (tools/image-manifest.sh), every file a Handtop package ships
(classes.txt, diversions.txt) and every file of the boot partition, with its checksum per release.
The worker uses it to name a card's release and RAM type, and to tell a file the user edited from
one an older release put there. Variants (DDR3, DDR4) of a release share a line where they agree.

    tools/release-data.py OUT.tsv BOOT-ABI v0.4.0:DDR4=v0.4.0.tsv v0.4.0:DDR3=v0.4.0-DDR3.tsv ...
Output lines: release <TAB> variant (* when all agree) <TAB> path <TAB> type (f/l) <TAB> sha256 or link,
and per release "@boot-abi" (type k): /etc/handtop/boot-abi for its kernel, lines joined with ";".
BOOT-ABI is a build's /etc/handtop/boot-abi; every release's KERNEL must be the one it names.
"""
import fnmatch
import importlib.util
import os
import sys

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
                p, t, _mode, v = line.rstrip("\n").split("\t")
                if t in ("f", "l") and wanted(p, rules, divs):
                    files[p] = (t, v)
        data.setdefault(rel, {})[var] = files
    rows = []
    for rel, variants in sorted(data.items()):
        for var, files in variants.items():
            if files.get("/boot/firmware/KERNEL") != ("f", ksha):
                sys.exit("%s %s: KERNEL is not the one %s names" % (rel, var, abi_file))
        rows.append((rel, "*", "@boot-abi", "k", ";".join(abi)))
        paths = sorted(set().union(*variants.values()))
        for p in paths:
            vals = {var: files.get(p) for var, files in variants.items()}
            if len(set(vals.values())) == 1 and None not in vals.values():
                t, v = next(iter(vals.values()))
                rows.append((rel, "*", p, t, v))
            else:
                for var, tv in sorted(vals.items()):
                    if tv:
                        rows.append((rel, var, p, tv[0], tv[1]))
    with open(out, "w") as f:
        f.write("# Files Handtop put on cards of each release (tools/release-data.py); read by handtop-update.\n")
        for r in rows:
            f.write("\t".join(r) + "\n")
    print("%d lines -> %s" % (len(rows), out))


if __name__ == "__main__":
    main()
