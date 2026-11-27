"""Validate payloads and complete package sets while repo.sh holds the archive lock."""
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
from collections import defaultdict
from email.parser import Parser
from pathlib import Path, PurePosixPath
from typing import NamedTuple


class Ref(NamedTuple):
    name: str
    version: str
    arch: str
    sha256: str


class Payload(NamedTuple):
    paths: frozenset
    breaks: str
    replaces: str


class Refused(Exception):
    pass


REPO = "handtop"
INCOMING = "handtop-incoming"
SUITES = ("trixie-testing", "trixie-stable")
ARCHES = ("arm64", "all")
FIELDS = ("Package", "Version", "Architecture", "SHA256")
TOP = Path(__file__).resolve().parents[2]


def label(ref):
    return " ".join(ref[:3])


def ref_from(values):
    ref = Ref(*values)
    if (not re.fullmatch(r"[a-z0-9][a-z0-9+.-]+", ref.name)
            or not re.fullmatch(r"[0-9a-zA-Z.+:~-]+", ref.version)
            or ref.arch not in ARCHES or not re.fullmatch(r"[a-f0-9]{64}", ref.sha256)):
        raise Refused(f"invalid archive package identity: {ref}")
    return ref


def digest(data):
    return hashlib.sha256(data).hexdigest()


def atomic_write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as f:
        tmp = Path(f.name)
        try:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
            os.replace(tmp, path)
            fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(fd)
            finally:
                os.close(fd)
        finally:
            tmp.unlink(missing_ok=True)


def deb_payload(path):
    control = Parser().parsestr(subprocess.check_output(
        ["dpkg-deb", "-f", path], text=True, timeout=60))
    sha = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            sha.update(chunk)
    ref = ref_from([control[k] or "" for k in FIELDS[:3]] + [sha.hexdigest()])
    paths = set()
    with tempfile.TemporaryFile() as data:
        subprocess.run(["dpkg-deb", "--fsys-tarfile", path], stdout=data, check=True, timeout=600)
        data.seek(0)
        with tarfile.open(fileobj=data, mode="r|") as archive:
            for member in archive:
                if member.isdir():
                    continue
                name = PurePosixPath("/" + member.name.lstrip("/"))
                if name == PurePosixPath("/") or ".." in name.parts:
                    raise Refused(f"{path}: invalid payload path {member.name!r}")
                paths.add(str(name))
    return ref, Payload(frozenset(paths), control["Breaks"] or "", control["Replaces"] or "")


def compare(left, op, right):
    result = subprocess.run(["dpkg", "--compare-versions", left, op, right], timeout=60)
    if result.returncode != 1:
        result.check_returncode()
    return result.returncode == 0


def predecessor(ref, published, announce):
    versions = [p for p in published if (p.name, p.arch) == (ref.name, ref.arch)]
    if not versions:
        if announce:
            reason = "new architecture" if any(p.name == ref.name for p in published) else "new package"
            print(f"repo.sh: {label(ref)}: {reason}, no published baseline", flush=True)
        return None
    previous = None
    for p in versions:
        if compare(p.version, "lt", ref.version) and (
                previous is None or compare(p.version, "gt", previous.version)):
            previous = p
    if previous is None:
        raise Refused(f"{label(ref)}: no lower published version to use as a baseline")
    return previous


def transfer(payload, old):
    # Binary control fields use comma-separated relations. A split must cover the old version.
    def covers(relationships):
        for clause in relationships.split(","):
            match = re.fullmatch(rf"\s*{re.escape(old.name)}\s*\((<<|<=|=|>=|>>)\s*(\S+)\s*\)\s*", clause)
            if match and compare(old.version, match[1], match[2]):
                return True
        return False

    return covers(payload.breaks) and covers(payload.replaces)


def validate_payloads(payloads, published, announce=False):
    incoming = payloads.keys() - published
    if not incoming:
        return
    allowed = defaultdict(set)
    with Path(os.environ.get("HANDTOP_REMOVED_FILES", TOP / "build/pkg/removed-files.txt")).open() as f:
        for line in f:
            if line.strip() and not line.lstrip().startswith("#"):
                name, path = line.rstrip("\n").split(maxsplit=1)
                allowed[name].add(path)
    for ref in sorted(incoming):
        payload = payloads[ref]
        old = predecessor(ref, published, announce)
        if old:
            missing = payloads[old].paths - payload.paths - allowed[ref.name]
            if missing:
                paths = "\n".join(f"  {p!r}" for p in sorted(missing)[:20])
                raise Refused(f"{label(ref)} lacks files from published {label(old)}:\n{paths}\n"
                              "List intentional drops in build/pkg/removed-files.txt.")
        for other, previous in payloads.items():
            if other.name == ref.name:
                continue
            shared = payload.paths & previous.paths
            if shared and not (transfer(payload, other) or transfer(previous, ref)):
                raise Refused(f"{label(ref)} and {label(other)} both own {min(shared)!r}; "
                              "a file transfer needs versioned Breaks and Replaces")


class Archive:
    def __init__(self, home):
        self.home = home
        self.state = home / "manifests"

    def aptly(self, *args, capture=False, empty_ok=False):
        result = subprocess.run(["aptly", f"-config={self.home / 'aptly.conf'}", *args],
                                capture_output=capture, text=True, timeout=600)
        if result.returncode and capture:
            if empty_ok and not result.stdout and result.stderr.strip() == "ERROR: no results":
                return ""
            raise Refused(result.stderr.strip() or f"aptly {' '.join(args)} failed")
        result.check_returncode()
        return result.stdout

    def inventory(self, kind, name):
        fmt = " ".join("{{." + field + "}}" for field in FIELDS)
        rows = self.aptly(kind, "search", f"-format={fmt}", name, capture=True, empty_ok=True)
        return {ref_from(row.split()) for row in rows.splitlines()}

    def published(self):
        """Read the snapshots actually published at this endpoint and their pool paths."""
        entries = json.loads(self.aptly("publish", "list", "-json", capture=True))
        sources = {p["Distribution"]: p for p in entries
                   if p["Storage"] == "filesystem:pages" and p["Prefix"] == "."}
        public = self.home / "public"
        suites = {}
        for suite in SUITES:
            dist = public / "dists" / suite
            entry = sources.get(suite)
            if entry is None:
                if dist.exists():
                    raise Refused(f"{suite}: published files exist without an aptly publication")
                continue
            if (entry["SourceKind"] != "snapshot" or set(entry["Architectures"]) != set(ARCHES)
                    or [s["Component"] for s in entry["Sources"]] != ["main"]):
                raise Refused(f"{suite}: expected a main snapshot published for arm64 and all")
            snapshot = entry["Sources"][0]["Name"]
            files = {}
            for arch in ARCHES:
                index = dist / "main" / f"binary-{arch}" / "Packages"
                for stanza in index.read_text(encoding="utf-8").split("\n\n"):
                    if not stanza.strip():
                        continue
                    control = Parser().parsestr(stanza)
                    ref = ref_from([control[k] or "" for k in FIELDS])
                    filename = (public / control["Filename"]).resolve()
                    if not filename.is_relative_to(public / "pool"):
                        raise Refused(f"{suite}: {filename} is outside the published pool")
                    if files.setdefault(ref, filename) != filename:
                        raise Refused(f"{suite}: conflicting pool paths for {label(ref)}")
            if files.keys() != self.inventory("snapshot", snapshot):
                raise Refused(f"{suite}: published indexes differ from aptly snapshot {snapshot}")
            suites[suite] = files
        return suites

    def receipt(self, refs):
        return self.state / "validated" / (digest(json.dumps(sorted(refs)).encode()) + ".json")

    def manifest(self, ref):
        return self.state / (ref.sha256 + ".json")

    def load(self, refs):
        if not refs:
            return {}
        try:
            hashes = json.loads(self.receipt(refs).read_bytes())
        except FileNotFoundError:
            raise Refused("package set was not validated by repo.sh; for an existing publication run repo.sh baseline")
        if not isinstance(hashes, dict):
            raise Refused("invalid package-set record; restore the archive state or run repo.sh baseline")
        payloads = {}
        for ref in sorted(refs):
            try:
                data = self.manifest(ref).read_bytes()
            except FileNotFoundError:
                raise Refused(f"missing baseline for {label(ref)} ({ref.sha256}); restore it with repo.sh baseline")
            if hashes.get(ref.sha256) != digest(data):
                raise Refused(f"stale baseline for {label(ref)} ({ref.sha256}); restore it with repo.sh baseline")
            saved, paths, breaks, replaces = json.loads(data)
            if saved != list(ref):
                raise Refused(f"baseline identity differs from {label(ref)} ({ref.sha256})")
            payloads[ref] = Payload(frozenset(paths), breaks, replaces)
        return payloads

    def approve(self, payloads):
        hashes = {}
        for ref, payload in payloads.items():
            data = json.dumps([ref, sorted(payload.paths), payload.breaks, payload.replaces]).encode()
            path = self.manifest(ref)
            if not path.is_file() or path.read_bytes() != data:
                atomic_write(path, data)
            hashes[ref.sha256] = digest(data)
        atomic_write(self.receipt(payloads), json.dumps(hashes, sort_keys=True).encode())

    def baseline(self, suites):
        files = {ref: path for suite in suites.values() for ref, path in suite.items()}
        payloads = {}
        for expected, path in files.items():
            ref, payload = deb_payload(path)
            if ref != expected:
                raise Refused(f"{path}: expected published {label(expected)} ({expected.sha256})")
            payloads[ref] = payload
        self.approve(payloads)
        for suite in suites.values():
            self.approve({ref: payloads[ref] for ref in suite})
        print(f"verified baselines for {len(payloads)} published packages")

    @staticmethod
    def retain(refs, required):
        missing = required - refs
        if missing:
            raise Refused(f"package set would lose published {label(min(missing))}")

    def add(self, paths, published):
        # Inspect and import the same bytes even if a build overwrites its output during add.
        with tempfile.TemporaryDirectory(prefix="handtop-debs-") as temp:
            incoming = []
            for i, path in enumerate(paths):
                copy = Path(temp) / str(i) / path.name
                copy.parent.mkdir()
                shutil.copyfile(path, copy)
                incoming.append(copy)
            self.add_batch(incoming, published)

    def add_batch(self, paths, published):
        previous = self.inventory("repo", REPO)
        self.retain(previous, published)
        additions = dict(deb_payload(path) for path in paths)
        expected = previous | additions.keys()
        if len({ref[:3] for ref in expected}) != len(expected):
            raise Refused("a package/version/architecture already exists with different bytes")
        if previous - published and not self.receipt(previous).is_file():
            # A repo left by the older tool can contain packages that were never published.
            # Revalidate those bytes from a complete explicit add before they become visible.
            if previous - published - additions.keys():
                raise Refused("the release repo contains unvalidated packages; re-add their exact .debs in this batch")
            payloads = self.load(published)
        else:
            payloads = self.load(previous)
        payloads.update(additions)
        validate_payloads(payloads, published, announce=True)

        # An aptly 1.5.0 add can save valid members before reporting errors. Only copy a fully
        # imported batch into the release repo, with its validation record already durable.
        if INCOMING in self.aptly("repo", "list", "-raw", capture=True).splitlines():
            self.aptly("repo", "drop", INCOMING)
        self.aptly("repo", "create", INCOMING)
        try:
            self.aptly("repo", "add", INCOMING, *paths)
            if self.inventory("repo", INCOMING) != additions.keys():
                raise Refused("aptly staged a different package set than requested")
            self.approve(payloads)
            self.aptly("repo", "copy", INCOMING, REPO, "Name (% *)")
            if self.inventory("repo", REPO) != expected:
                raise Refused("aptly copied a different package set than validated")
        finally:
            try:
                self.aptly("repo", "drop", INCOMING)
            except (OSError, subprocess.SubprocessError) as error:
                print(f"repo.sh: couldn't remove {INCOMING}; next add will retry: {error}", file=sys.stderr)


def main(home, command, *args):
    archive = Archive(Path(home).resolve())
    suites = archive.published()
    published = {ref for suite in suites.values() for ref in suite}
    if command == "baseline" and not args:
        archive.baseline(suites)
    elif command == "add" and args:
        archive.add([Path(arg).resolve() for arg in args], published)
    elif command == "snapshot" and len(args) == 1 and args[0] and not args[0].startswith("-"):
        refs = archive.inventory("repo", REPO)
        archive.retain(refs, published)
        archive.load(refs)
        archive.aptly("snapshot", "create", args[0], "from", "repo", REPO)
    elif command == "publish" and len(args) == 2 and args[0] and not args[0].startswith("-"):
        refs = archive.inventory("snapshot", args[0])
        archive.retain(refs, suites.get(args[1], {}).keys() | suites.get("trixie-stable", {}).keys())
        payloads = archive.load(refs)
        # Another snapshot may have been published since this one was validated.
        missing_history = published - refs
        if refs - published and missing_history:
            for suite in suites.values():
                if missing_history & suite.keys():
                    payloads.update(archive.load(suite.keys()))
        validate_payloads(payloads, published)
    else:
        raise Refused(f"invalid arguments for {command}")


if __name__ == "__main__":
    try:
        main(*sys.argv[1:])
    except (OSError, ValueError, TypeError, KeyError, subprocess.SubprocessError, tarfile.TarError, Refused) as error:
        sys.exit(f"repo.sh: {error}")
