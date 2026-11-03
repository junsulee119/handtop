# Pinned upstreams and the weekly drift check

Most of Handtop comes from Debian, and apt keeps it updated. A few pieces don't: we build or download them ourselves at a pinned version (FFmpeg with the V4L2 request patches, the VA-API driver, ROCKNIX's kernel and firmware, our kernel modules, the cedrus VP9 series, Go, nwg-drawer). **Nothing updates those by itself, and nothing told us when they fell behind.** The codebase audit of 2026-10-30 found exactly that: our FFmpeg was about 390 upstream commits behind Debian's, two CVE fixes among them, while dpkg still showed Debian's version (finding H01, fixed by moving to the release Debian ships, see [video-decode.md](video-decode.md)).

So every such piece is listed in **`build/upstreams.conf`**, and **`tools/check-upstreams.py`** compares each pin with its upstream: weekly in GitHub Actions (`.github/workflows/upstreams.yml`) and whenever you run it by hand.

## The list: `build/upstreams.conf`

One section per piece, with:

| Key | Meaning |
|---|---|
| `what` | What it is and which build step uses it |
| `pin` | The variables that pin it: in `build/config.sh`, or `path:VAR` for another file |
| `shadows` | The Debian package it replaces, if any (our FFmpeg replaces Debian's `libav*`, which are held) |
| `check` | How the check finds the newest upstream, one per line (below) |
| `constraint` | What limits updating it (ABI, must match ROCKNIX's kernel, ...) |
| `delivery` | How a fix reaches handhelds: today by reflashing; later, with the planned updates without reflashing, as a package (named) or still reflash-only |
| `waive` | `<upstream version> \| <date> \| <reason>`: an update we know about and deliberately don't take |

Kinds of check:

| Check | Behind when |
|---|---|
| `debian-security <package> <VAR>` | Debian's newest version of the package (security tracker, `trixie` and `trixie-security`) differs from `debian_seen`, or its upstream release is newer than ours. Also reports how many CVEs are open in Debian too (nothing to take yet) |
| `git-branch <url> <branch> <VAR>` | The branch head is no longer the pinned commit |
| `git-newer-branches <url> <branch> <VAR>` | A newer branch exists **for our FFmpeg release line** (major.minor of VAR); branches for other lines (n8.x: another libav ABI) are only mentioned |
| `git-head <url> <VAR>` | The default branch has moved past the pinned commit |
| `git-path <url> <branch> <path> <VAR>` | A commit on the branch after the pinned one touches `path`. For a piece taken from one folder of a busy repo (a patch series), where `git-head` would report "behind" almost every week. Fetches the branch's history without file contents (LibreELEC.tv: about 50 MB, a few seconds). Also behind when the pinned commit is no longer on the branch |
| `git-tags <url> <regex> <VAR>` | A newer release tag (by version order) exists |
| `go <VAR>` | A newer patch release of the same Go minor exists (those carry security fixes); a newer minor is only mentioned |
| `follows <section>` | Not checked on its own: updated together with that section (our kernel modules follow ROCKNIX) |
| `none <reason>` | Not checked (Chromium updates its extensions itself) |

Not in the list, because apt updates them: Debian packages, **Tailscale** and **Moonlight** (both from their vendors' own apt repos). Moonlight bundles its own FFmpeg, which only its upstream can fix.

## Running it

```
tools/check-upstreams.py [--report report.md]
```

It needs only Python 3, git and network access (no root, no build, no hardware). It prints a Markdown table. Exit status 0: everything is current or waived; 1: something is behind or a check failed; 2: a broken `upstreams.conf`.

## The weekly issue

`.github/workflows/upstreams.yml` runs it on Mondays (and on demand: Actions → Upstream drift → Run workflow). While something is behind it keeps **one open issue, "Upstream drift"**: it creates it, replaces the description with the new report, and comments when the report changes. When everything is current or waived it posts the report and closes the issue.

## Handling a "behind" line

1. **Look at what changed upstream** (release notes, the commits, Debian's changelog).
2. Then one of:
   - **Update:** bump the pin in `build/config.sh` (or the file named in `pin`), follow the piece's own update notes (FFmpeg: [video-decode.md](video-decode.md), "Updating FFmpeg"; ROCKNIX: every module in `build/06b`–`06e` is rebuilt against the new kernel, see [kernel.md](kernel.md)), build, test on the device as the PR rules require, and say in the CHANGELOG when it carries security fixes. For FFmpeg also update `debian_seen` to the Debian version you compared with.
   - **Waive:** write `waive = <the upstream version from the report> | <date> | <why>` in the piece's section. The line then shows as waived until upstream moves again.
3. A **check failed** line means the check itself broke (network, a renamed branch, a repo gone): fix the entry, don't waive it.

## Adding a piece

Anything new that the build downloads or builds outside apt gets a section in `build/upstreams.conf` in the same PR (AGENTS.md), with a `check` that can find its upstream. Run `tools/check-upstreams.py` once to see that the new line works.

## Later: delivery without reflashing

The planned updates without reflashing (an apt repo of Handtop packages) will ship these pieces as packages, so a fix will no longer need a new image. For FFmpeg that means our build under Debian's own package names with a higher version (`7:7.1.5-0+deb13u1+handtop1`), our repo pinned above Debian's for them instead of the apt hold, and a rebuild whenever this check reports a new Debian version. The boot layer (kernel, U-Boot, device trees, firmware) stays reflash-only.
