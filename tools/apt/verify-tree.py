#!/usr/bin/env python3
"""Checks a Handtop apt tree before (and after) it goes to GitHub Pages (review 2026-11-26 #77).

    verify-tree.py TREE --fpr FINGERPRINT --gnupghome DIR [--suite S ...] [--nonempty S ...]
                   [--migrate FILE] [--min-valid-days N]

Per suite (default: trixie-stable, trixie-testing; all must be there):
  - InRelease and Release.gpg verify (gpg exit status and VALIDSIG) with the archive key's primary
    fingerprint; InRelease carries exactly Release;
  - Origin / Label "Handtop", Suite and Codename = the suite's folder, Date not in the future,
    Valid-Until at least --min-valid-days ahead (default 7);
  - every index form Release lists (Packages, .gz, .bz2, .xz) is there with the listed size and SHA-256,
    and with Acquire-By-Hash its SHA256 and SHA512 by-hash objects; nothing else in the suite's folder but the
    signature files, the listed indexes and by-hash objects whose name is their own checksum (older
    generations stay for apt's cache window), aptly's current-index copies (identical to the index) and
    its <index>.old copies (identical to a by-hash object next to them);
  - every package the indexes list is in pool/ with its Size and SHA256; --nonempty suites list some.
The pool holds only files some index lists. Top level: dists/, pool/, migrate/ and README.md,
handtop-archive.asc, .nojekyll, .gitattributes. --migrate FILE: migrate/ must hold exactly that file
(byte for byte: this checkout's handtop-migrate), its signature by the archive key and the key.
Without --migrate, a migrate/ folder is still checked as a complete signed set.
"""
import argparse
import bz2
import datetime
import email.utils
import gzip
import hashlib
import lzma
import os
import re
import subprocess
import sys

ALGS = {"MD5Sum": "md5", "SHA1": "sha1", "SHA256": "sha256", "SHA512": "sha512"}
TOP_FILES = {"README.md", "handtop-archive.asc", ".nojekyll", ".gitattributes"}
TOP_DIRS = {"dists", "pool", "migrate"}
SIGS = {"Release", "InRelease", "Release.gpg"}
errors = []


def bad(msg):
    errors.append(msg)


def digest(path, alg="sha256"):
    h = hashlib.new(alg)
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def signer(gnupghome, *args):
    """The primary fingerprint of a good signature, or None (gpg's exit status counts)."""
    p = subprocess.run(["gpg", "--homedir", gnupghome, "--batch", "--status-fd", "1", "--verify"] + list(args),
                       stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, timeout=60)
    if p.returncode != 0:
        return None
    fprs = [l.split()[-1] for l in p.stdout.splitlines() if l.startswith("[GNUPG:] VALIDSIG ")]
    return fprs[0] if len(fprs) == 1 else None


def cleartext(gnupghome, path):
    p = subprocess.run(["gpg", "--homedir", gnupghome, "--batch", "-q", "--decrypt", path],
                       stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=60)
    return p.stdout if p.returncode == 0 else None


def fields(text):
    out, key = {}, None
    for line in text.splitlines():
        if line.startswith(" ") and key:
            out[key] += "\n" + line[1:]
        elif ":" in line:
            key, _, v = line.partition(":")
            out[key] = v.strip()
    return out


def listed(rel_fields):
    """{alg: {name: (hash, size)}} from Release's checksum blocks."""
    res = {}
    for alg in ALGS:
        for line in rel_fields.get(alg, "").splitlines():
            parts = line.split()
            if len(parts) == 3:
                res.setdefault(alg, {})[parts[2]] = (parts[0], int(parts[1]))
    return res


def read_index(path):
    opener = {".gz": gzip.open, ".bz2": bz2.open, ".xz": lzma.open}.get(os.path.splitext(path)[1], open)
    with opener(path, "rb") as f:
        return f.read().decode("utf-8")


def contents(name):
    """Contents-* (apt-file's, never fetched by apt update; aptly lists empty ones it doesn't write)."""
    return os.path.basename(base(name)).startswith("Contents-")


def base(name):
    return re.sub(r"\.(gz|bz2|xz)$", "", name)


def check_suite(tree, suite, a, now, pool_refs):
    d = os.path.join(tree, "dists", suite)
    for f in SIGS:
        if not os.path.isfile(os.path.join(d, f)):
            bad("%s: %s missing" % (suite, f))
            return
    rel = os.path.join(d, "Release")
    if signer(a.gnupghome, os.path.join(d, "InRelease")) != a.fpr:
        bad("%s/InRelease: not a good signature by %s" % (suite, a.fpr))
    if signer(a.gnupghome, os.path.join(d, "Release.gpg"), rel) != a.fpr:
        bad("%s/Release.gpg: not a good signature by %s" % (suite, a.fpr))
    if cleartext(a.gnupghome, os.path.join(d, "InRelease")) != open(rel, "rb").read():
        bad("%s/InRelease doesn't carry Release (signed before the last publish?)" % suite)
    f = fields(open(rel).read())
    for k, want in (("Origin", "Handtop"), ("Label", "Handtop"), ("Suite", suite), ("Codename", suite)):
        if f.get(k) != want:
            bad("%s/Release: %s is %r, expected %r" % (suite, k, f.get(k), want))
    try:
        date = email.utils.parsedate_to_datetime(f["Date"])
        until = email.utils.parsedate_to_datetime(f["Valid-Until"])
    except (KeyError, TypeError, ValueError):
        bad("%s/Release: Date or Valid-Until missing or unreadable" % suite)
    else:
        if date > now + datetime.timedelta(minutes=10):
            bad("%s/Release: Date %s is in the future" % (suite, f["Date"]))
        if until < now + datetime.timedelta(days=a.min_valid_days):
            bad("%s/Release: Valid-Until %s is less than %d days away: sign again" % (suite, f["Valid-Until"], a.min_valid_days))
    lst = listed(f)
    sha = lst.get("SHA256", {})
    if not sha:
        bad("%s/Release: no SHA256 list" % suite)
    present = {}
    for name, (h, size) in sha.items():
        p = os.path.join(d, name)
        if os.path.isfile(p):
            present.setdefault(base(name), []).append(name)
            if os.path.getsize(p) != size or digest(p) != h:
                bad("%s/%s: size or SHA-256 differs from Release" % (suite, name))
        elif not contents(name):
            # apt may fetch any form Release lists (it picks by its own compression order): a listed
            # but missing form is a failed update on some cards (#120).
            bad("%s/%s: listed in Release but not published" % (suite, name))
    # Every architecture and component the Release names has its Packages index (#77).
    for comp in f.get("Components", "").split():
        for arch in f.get("Architectures", "").split():
            if "%s/binary-%s/Packages" % (comp, arch) not in present:
                bad("%s: %s/binary-%s/Packages is missing" % (suite, comp, arch))
    # Acquire-By-Hash: each published index's current object is there under its SHA256 name.
    for arch in ("arm64", "all"):                  # what Handtop's cards ask for, whatever Release says
        if "main/binary-%s/Packages" % arch not in present:
            bad("%s: main/binary-%s/Packages is missing" % (suite, arch))
    if f.get("Acquire-By-Hash", "").lower() == "yes":
        # apt asks for the strongest hash's object first (SHA512): every strong one must be there (#109)
        for alg in ("SHA256", "SHA512"):
            if alg not in lst:
                continue
            for name, (h, size) in lst[alg].items():   # every listed form (#120)
                if contents(name) and not os.path.isfile(os.path.join(d, name)):
                    continue
                bh = os.path.join(d, os.path.dirname(name), "by-hash", alg, h)
                if not os.path.isfile(bh):
                    bad("%s: %s by-hash object of %s is missing" % (suite, alg, name))
                elif os.path.getsize(bh) != size:
                    bad("%s: %s by-hash object of %s has the wrong size" % (suite, alg, name))
    # Nothing unlisted in the suite's folder.
    for root, dirs, files in os.walk(d):
        for fn in files:
            p = os.path.join(root, fn)
            r = os.path.relpath(p, d)
            if r in SIGS or r in sha:
                continue
            parts = r.split(os.sep)
            if len(parts) >= 3 and parts[-3] == "by-hash" and parts[-2] in ALGS:
                alg = parts[-2]
                if re.fullmatch(r"[0-9a-f]+", fn):
                    if digest(p, ALGS[alg]) != fn:
                        bad("%s/%s: by-hash object doesn't match its name" % (suite, r))
                    continue
                if fn.endswith(".old") and os.path.isfile(os.path.join(root, digest(p, ALGS[alg]))):
                    continue                     # aptly's link to the previous generation's object
                twin = os.path.join(*parts[:-3], fn) if len(parts) > 3 else fn
                if twin in sha and os.path.isfile(os.path.join(d, twin)) and \
                        digest(p) == digest(os.path.join(d, twin)):
                    continue                     # aptly's copy of the current index
                bad("%s/%s: by-hash entry that isn't the current %s" % (suite, r, twin))
                continue
            bad("%s/%s: not listed in Release" % (suite, r))
    # Every package the indexes list is in the pool with its size and checksum.
    count = 0
    for b, names in present.items():
        if os.path.basename(b) != "Packages":
            continue
        forms = {n: read_index(os.path.join(d, n)) for n in names}
        if len(set(forms.values())) > 1:          # every compressed form is the same index (#77)
            bad("%s: the forms of %s differ" % (suite, b))
        text = forms[sorted(names, key=len)[0]]
        for stanza in text.split("\n\n"):
            s = fields(stanza)
            if not s.get("Filename"):
                continue
            count += 1
            p = os.path.join(tree, s["Filename"])
            pool_refs.add(os.path.normpath(s["Filename"]))
            if not os.path.isfile(p):
                bad("%s: %s (%s %s) is not in the pool" % (suite, s["Filename"], s.get("Package"), s.get("Version")))
            elif os.path.getsize(p) != int(s.get("Size", -1)) or digest(p) != s.get("SHA256"):
                bad("%s: %s doesn't match its index entry" % (suite, s["Filename"]))
    if suite in a.nonempty and count == 0:
        bad("%s: no packages listed (expected some)" % suite)


def check_migrate(tree, a):
    m = os.path.join(tree, "migrate")
    want = {"handtop-migrate", "handtop-migrate.asc", "handtop-archive.asc"}
    if not os.path.isdir(m):
        if a.migrate:
            bad("migrate/ missing (repo.sh migrate, then sign.sh)")
        return
    have = set(os.listdir(m))
    if have != want:
        bad("migrate/ holds %s, expected exactly %s" % (sorted(have), sorted(want)))
        return
    if a.key and open(os.path.join(m, "handtop-archive.asc"), "rb").read() != open(a.key, "rb").read():
        bad("migrate/handtop-archive.asc is not the archive's public key")
    if signer(a.gnupghome, os.path.join(m, "handtop-migrate.asc"), os.path.join(m, "handtop-migrate")) != a.fpr:
        bad("migrate/handtop-migrate: signature missing, stale or not by the archive key (sign.sh)")
    if a.migrate and open(os.path.join(m, "handtop-migrate"), "rb").read() != open(a.migrate, "rb").read():
        bad("migrate/handtop-migrate is not %s (an older signed script?)" % a.migrate)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("tree")
    ap.add_argument("--fpr", required=True)
    ap.add_argument("--gnupghome", required=True)
    ap.add_argument("--key", help="the archive's public key file (compared with migrate/)")
    ap.add_argument("--suite", action="append")
    ap.add_argument("--nonempty", action="append", default=[])
    ap.add_argument("--migrate")
    ap.add_argument("--min-valid-days", type=int, default=7)
    a = ap.parse_args()
    suites = a.suite or ["trixie-stable", "trixie-testing"]
    now = datetime.datetime.now(datetime.timezone.utc)
    tree = a.tree
    for e in os.listdir(tree):
        if e == ".git":
            continue
        p = os.path.join(tree, e)
        if os.path.islink(p) or not ((os.path.isdir(p) and e in TOP_DIRS) or (os.path.isfile(p) and e in TOP_FILES)):
            bad("unexpected top-level entry: %s" % e)
    dd = os.path.join(tree, "dists")
    have = set(os.listdir(dd)) if os.path.isdir(dd) else set()
    for s in sorted(have - set(suites)):
        bad("dists/%s: not an expected suite" % s)
    refs = set()
    for s in suites:
        if s not in have:
            bad("dists/%s missing" % s)
        else:
            check_suite(tree, s, a, now, refs)
    for root, dirs, files in os.walk(os.path.join(tree, "pool")):
        for fn in files:
            r = os.path.relpath(os.path.join(root, fn), tree)
            if os.path.normpath(r) not in refs:
                bad("%s: in the pool but in no index" % r)
    check_migrate(tree, a)
    if errors:
        for e in errors:
            print("verify-tree: " + e, file=sys.stderr)
        sys.exit(1)
    print("verify-tree: %s OK (%s)" % (tree, ", ".join(suites)))


if __name__ == "__main__":
    main()
