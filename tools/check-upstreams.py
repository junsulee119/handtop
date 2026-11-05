#!/usr/bin/env python3
"""Report pinned pieces whose upstream has moved past the pin (build/upstreams.conf).

Usage: tools/check-upstreams.py [--report FILE]

Prints a Markdown report (and writes it to FILE). Exit status: 0 = every piece is
current or waived, 1 = something is behind or a check failed, 2 = bad usage or a
broken upstreams.conf. Needs only Python 3, git and network access: no root, no
build, no hardware. Run weekly by .github/workflows/upstreams.yml; see
docs/upstreams.md.
"""
import argparse
import configparser
import datetime
import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request

TOP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONF = os.path.join(TOP, "build", "upstreams.conf")
TIMEOUT = 60
DEBIAN_SECURITY_JSON = "https://security-tracker.debian.org/tracker/data/json"
GO_RELEASES_JSON = "https://go.dev/dl/?mode=json"
ARM_GNU_URL = ("https://developer.arm.com/-/media/Files/downloads/gnu/{v}/binrel/"
               "arm-gnu-toolchain-{v}-x86_64-aarch64-none-linux-gnu.tar.xz")
SUITE = "trixie"


class CheckError(Exception):
    pass


def config_vars():
    """All variables build/config.sh sets, read by sourcing it in bash (it only assigns)."""
    out = subprocess.run(["bash", "-c", 'source "$1/build/config.sh" >/dev/null && set -o posix && set', "_", TOP],
                         capture_output=True, text=True, check=True).stdout
    vals = {}
    for line in out.splitlines():
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)=(.*)$", line)
        if m:
            v = m.group(2)
            if len(v) >= 2 and v[0] == v[-1] == "'":
                v = v[1:-1]
            vals[m.group(1)] = v
    return vals


def pin_value(ref, cvars):
    """VAR (from build/config.sh) or path/to/file:VAR (a VAR="..." line in that file)."""
    if ":" in ref:
        path, var = ref.split(":", 1)
        with open(os.path.join(TOP, path)) as f:
            for line in f:
                m = re.match(r'^\s*%s="([^"]*)"' % re.escape(var), line)
                if m:
                    return m.group(1)
        raise CheckError(f"{var} not found in {path}")
    if ref not in cvars:
        raise CheckError(f"{ref} is not set in build/config.sh")
    return cvars[ref]


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "handtop-check-upstreams"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return r.read()
    except OSError as e:
        raise CheckError(f"cannot fetch {url}: {e}") from e


def ls_remote(url, *patterns):
    try:
        out = subprocess.run(["git", "ls-remote", url, *patterns], capture_output=True, text=True,
                             timeout=TIMEOUT, check=True).stdout
    except (subprocess.SubprocessError, OSError) as e:
        raise CheckError(f"git ls-remote {url} failed: {e}") from e
    refs = {}
    for line in out.splitlines():
        sha, ref = line.split("\t", 1)
        refs[ref] = sha
    return refs


def vkey(s):
    """Sort key for versions such as 7.1.5, v0.7.5, 20261001, go1.27.3."""
    return [int(x) for x in re.findall(r"\d+", s)]


def short(v):
    return v[:12] if re.fullmatch(r"[0-9a-f]{40}", v) else v


_debian_cache = {}


def debian_data():
    if "d" not in _debian_cache:
        _debian_cache["d"] = json.loads(fetch(DEBIAN_SECURITY_JSON))
    return _debian_cache["d"]


# Each check returns (pinned, upstream, behind: bool, note).
def check_debian_security(args, cvars, section):
    pkg, var = args
    ours = pin_value(var, cvars)
    seen = section.get("debian_seen", "").strip()
    entries = debian_data().get(pkg)
    if not entries:
        raise CheckError(f"{pkg} not in the Debian security tracker data")
    versions = set()
    open_cves = []
    for cve, info in entries.items():
        rel = info.get("releases", {}).get(SUITE)
        if not rel:
            continue
        versions.update(rel.get("repositories", {}).values())
        if rel.get("status") == "open":
            open_cves.append(cve)
    if not versions:
        raise CheckError(f"no {SUITE} version of {pkg} in the tracker data")
    newest = max(versions, key=vkey)
    upstream_part = re.sub(r"^\d+:", "", newest).split("-")[0]
    behind = newest != seen or vkey(upstream_part) > vkey(ours)
    note = f"Debian {SUITE}: {newest} (last looked at: {seen or 'never'}); ours {ours}."
    if newest != seen:
        note += " **Debian has a version we have not compared with ours yet.**"
    note += f" Open in Debian too (no fix to take yet): {len(open_cves)} CVEs."
    return ours, newest, behind, note


def check_git_branch(args, cvars, section):
    url, branch, var = args
    ours = pin_value(var, cvars)
    refs = ls_remote(url, f"refs/heads/{branch}")
    head = refs.get(f"refs/heads/{branch}")
    if not head:
        return short(ours), "(branch gone)", True, f"branch {branch} no longer exists"
    return short(ours), short(head), head != ours, f"head of {branch}"


def check_git_newer_branches(args, cvars, section):
    """Branches newer than ours. Only those for our FFmpeg major.minor count: a newer
    major (n8.x) has another libav ABI and does not fit the Debian release."""
    url, branch, var = args
    release = vkey(pin_value(var, cvars))[:2]
    prefix = re.sub(r"[0-9.]+$", "", branch)
    refs = ls_remote(url, f"refs/heads/{prefix}*")
    names = [r[len("refs/heads/"):] for r in refs]
    newer = sorted((n for n in names if vkey(n) > vkey(branch)), key=vkey)
    fitting = [n for n in newer if vkey(n)[:2] == release]
    others = [n for n in newer if n not in fitting]
    note = ("a branch for our FFmpeg release line: it could replace the diff" if fitting
            else "no newer branch for our FFmpeg release line")
    if others:
        note += f" (other release lines, not usable on {SUITE}: {', '.join(others)})"
    return branch, ", ".join(fitting) or "(none)", bool(fitting), note


def check_git_head(args, cvars, section):
    url, var = args
    ours = pin_value(var, cvars)
    refs = ls_remote(url, "HEAD")
    head = refs.get("HEAD")
    if not head:
        raise CheckError(f"no HEAD at {url}")
    return short(ours), short(head), head != ours, "default branch"


def git(repo, *cmd, timeout=TIMEOUT):
    try:
        return subprocess.run(["git", "-C", repo, *cmd], capture_output=True, text=True,
                              timeout=timeout, check=True).stdout.strip()
    except subprocess.CalledProcessError as e:
        raise CheckError(f"git {cmd[0]} failed: {e.stderr.strip() or e}") from e
    except (subprocess.SubprocessError, OSError) as e:
        raise CheckError(f"git {cmd[0]} failed: {e}") from e


def check_git_path(args, cvars, section):
    """Commits on the branch after the pinned one that touch the path. For pieces taken from
    one folder of a busy repo (a patch series), where git-head would always show "behind".
    Fetches the branch's history without file contents (LibreELEC.tv: ~50 MB, a few seconds)."""
    url, branch, path, var = args
    ours = pin_value(var, cvars)
    with tempfile.TemporaryDirectory(prefix="upstream-") as repo:
        git(repo, "init", "-q", "--bare")
        git(repo, "fetch", "-q", "--filter=blob:none", url, f"refs/heads/{branch}", timeout=TIMEOUT * 10)
        head = git(repo, "rev-parse", "FETCH_HEAD")
        try:
            pin = git(repo, "rev-parse", "--verify", "-q", f"{ours}^{{commit}}")
        except CheckError:
            return short(ours), short(head), True, f"pinned commit not found on {branch} (rewritten history?)"
        if subprocess.run(["git", "-C", repo, "merge-base", "--is-ancestor", pin, head]).returncode != 0:
            return short(ours), short(head), True, f"pinned commit is no longer part of {branch}"
        total = int(git(repo, "rev-list", "--count", f"{pin}..{head}"))
        touching = git(repo, "rev-list", f"{pin}..{head}", "--", path).split()
    if not touching:
        return short(ours), short(ours), False, f"{total} commits on {branch} since the pin, none touch {path}"
    return (short(ours), short(touching[0]), True,
            f"{len(touching)} of {total} commits on {branch} since the pin touch {path}")


def check_git_tags(args, cvars, section):
    url, pattern, var = args
    ours = pin_value(var, cvars)
    refs = ls_remote(url, "refs/tags/*")
    tags = {r[len("refs/tags/"):].removesuffix("^{}") for r in refs}
    tags = [t for t in tags if re.search(pattern, t)]
    if not tags:
        raise CheckError(f"no tags matching {pattern} at {url}")
    newest = max(tags, key=vkey)
    return ours, newest, vkey(newest) > vkey(ours), "newest release tag"


def check_go(args, cvars, section):
    (var,) = args
    ours = pin_value(var, cvars)
    rel = [r["version"] for r in json.loads(fetch(GO_RELEASES_JSON)) if r.get("stable")]
    minor = vkey(ours)[:2]
    same = [v for v in rel if vkey(v)[:2] == minor]
    newest_same = max(same, key=vkey) if same else None
    newest = max(rel, key=vkey)
    behind = bool(newest_same) and vkey(newest_same) > vkey(ours)
    note = "newer patch release of our minor (security fixes)" if behind else "patch release current"
    if vkey(newest)[:2] > minor:
        note += f"; newer minor {newest} exists (optional)"
    return ours, newest_same or newest, behind, note


def url_exists(url):
    """True on 2xx, False on 404; anything else (network, 403, 5xx) is a failed check."""
    req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "handtop-check-upstreams"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT):
            return True
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return False
        raise CheckError(f"HEAD {url}: HTTP {e.code}") from e
    except OSError as e:
        raise CheckError(f"HEAD {url}: {e}") from e


def check_arm_gnu(args, cvars, section):
    """Arm publishes no release list that is easy to read, so probe the download URL (the
    x86_64 build, as in build/config.sh) for the next names in Arm's X.Y.relN scheme: this
    major and the next, minors 1-4, rel1-3. Our own version must still be found there, so
    a change of Arm's URL layout fails the check instead of going quiet."""
    (var,) = args
    ours = pin_value(var, cvars)
    m = re.fullmatch(r"(\d+)\.(\d+)\.rel(\d+)", ours)
    if not m:
        raise CheckError(f"{var}={ours} is not in Arm's X.Y.relN form")
    if not url_exists(ARM_GNU_URL.format(v=ours)):
        raise CheckError(f"Arm's download of our own {ours} is gone: the URL layout changed, update ARM_GNU_URL")
    major = int(m.group(1))
    found = [v for v in (f"{a}.{b}.rel{c}" for a in (major, major + 1) for b in range(1, 5) for c in range(1, 4))
             if vkey(v) > vkey(ours) and url_exists(ARM_GNU_URL.format(v=v))]
    if not found:
        return ours, ours, False, f"no newer Arm GNU toolchain (probed {major}.x and {major + 1}.x)"
    return (ours, max(found, key=vkey), True,
            "newer Arm GNU toolchain; take it only when ROCKNIX builds its kernel with that GCC (docs/kernel.md)")


CHECKS = {
    "arm-gnu": check_arm_gnu,
    "debian-security": check_debian_security,
    "git-branch": check_git_branch,
    "git-newer-branches": check_git_newer_branches,
    "git-head": check_git_head,
    "git-path": check_git_path,
    "git-tags": check_git_tags,
    "go": check_go,
}


def run(conf, cvars):
    rows = []
    for name in conf.sections():
        s = conf[name]
        waive = [x.strip() for x in s.get("waive", "").split("|")]
        for line in [l.strip() for l in s.get("check", "").splitlines() if l.strip()]:
            kind, *args = line.split()
            if kind == "none":
                rows.append((name, "-", "-", "untracked", " ".join(args)))
                continue
            if kind == "follows":
                rows.append((name, "-", "-", "follows", f"updated together with [{args[0]}]"))
                continue
            fn = CHECKS.get(kind)
            if not fn:
                print(f"upstreams.conf [{name}]: unknown check {kind!r}", file=sys.stderr)
                sys.exit(2)
            try:
                ours, up, behind, note = fn(args, cvars, s)
            except (CheckError, ValueError, KeyError, json.JSONDecodeError) as e:
                rows.append((name, "?", "?", "check failed", str(e)))
                continue
            status = "behind" if behind else "ok"
            if behind and waive[0] and waive[0] == up:
                status = "waived"
                note += f" Waived {waive[1] if len(waive) > 1 else ''}: {waive[2] if len(waive) > 2 else ''}"
            rows.append((name, ours, up, status, note))
    return rows


def report(rows):
    today = datetime.date.today().isoformat()
    bad = [r for r in rows if r[3] in ("behind", "check failed")]
    out = [f"# Upstream drift report ({today})", ""]
    out.append(f"**{len(bad)} to look at.**" if bad else "**Everything pinned is current or waived.**")
    out += ["", "Pins and how to update or waive them: `build/upstreams.conf`, `docs/upstreams.md`.", "",
            "| Piece | Pinned | Upstream | Status | Notes |", "|---|---|---|---|---|"]
    order = {"check failed": 0, "behind": 1, "waived": 2, "ok": 3, "follows": 4, "untracked": 5}
    for r in sorted(rows, key=lambda r: order.get(r[3], 9)):
        status = {"behind": "**behind**", "check failed": "**check failed**"}.get(r[3], r[3])
        cells = [r[0], f"`{r[1]}`" if r[1] not in "-?" else r[1], f"`{r[2]}`" if r[2] not in "-?" else r[2],
                 status, r[4].replace("|", "\\|")]
        out.append("| " + " | ".join(cells) + " |")
    return "\n".join(out) + "\n", bool(bad)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--report", help="also write the Markdown report to this file")
    a = ap.parse_args()
    conf = configparser.ConfigParser(interpolation=None)
    if not conf.read(CONF):
        sys.exit(f"cannot read {CONF}")
    text, bad = report(run(conf, config_vars()))
    print(text, end="")
    if a.report:
        with open(a.report, "w") as f:
            f.write(text)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
