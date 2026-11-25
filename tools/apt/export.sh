#!/bin/bash
# Copies the signed tree from $HANDTOP_APT_HOME/public into a handtop-apt checkout for GitHub Pages:
# links materialised as files, .nojekyll, the public key and a README. Leaves .git alone and
# removes files that are no longer published (only inside the checkout, never .git).
#   bash tools/apt/export.sh <handtop-apt checkout>
set -euo pipefail
APT_HOME="${HANDTOP_APT_HOME:-$HOME/.handtop-apt}"
DEST="${1:?usage: export.sh <handtop-apt checkout>}"
[ -d "$DEST/.git" ] || { echo "$DEST is not a git checkout" >&2; exit 1; }
# The right repository (review 2026-11-19 #20): Pages serves whatever is pushed there.
url=$(git -C "$DEST" remote get-url origin 2>/dev/null || true)
[[ "$url" =~ ^(https://github\.com/|git@github\.com:)junsulee119/handtop-apt(\.git)?$ ]] ||
	{ echo "$DEST is not a clone of junsulee119/handtop-apt (origin: ${url:-none})" >&2; exit 1; }
# Every suite: signed by the archive key (InRelease and Release.gpg), InRelease = Release, and every
# index Release lists is there with its size and SHA-256. Checked before anything is copied.
FPR=$(cat "$APT_HOME/FINGERPRINT.txt")
G=$(mktemp -d); trap 'rm -rf "$G"' EXIT
gpg --homedir "$G" --batch -q --import "$APT_HOME/handtop-archive-public.asc" 2>/dev/null
signer() { gpg --homedir "$G" --batch --status-fd 1 --verify "$@" 2>/dev/null | awk '$2 == "VALIDSIG" {print $NF}' || true; }
for rel in "$APT_HOME"/public/dists/*/Release; do
	d=$(dirname "$rel")
	[ "$(signer "$d/InRelease")" = "$FPR" ] || { echo "not signed by the archive key: $d/InRelease (run sign.sh)" >&2; exit 1; }
	[ "$(signer "$d/Release.gpg" "$rel")" = "$FPR" ] || { echo "not signed by the archive key: $d/Release.gpg (run sign.sh)" >&2; exit 1; }
	gpg --homedir "$G" --batch -q --decrypt "$d/InRelease" 2>/dev/null | cmp -s - "$rel" ||
		{ echo "$d/InRelease doesn't carry Release (signed before the last publish? run sign.sh)" >&2; exit 1; }
	python3 - "$d" <<'IDX' || exit 1
import hashlib, os, re, sys
d = sys.argv[1]
text = open(os.path.join(d, "Release")).read()
block = re.search(r"^SHA256:\n((?: .*\n?)*)", text, re.M)
bad = []
for line in (block.group(1).splitlines() if block else []):
    h, size, name = line.split()
    p = os.path.join(d, name)
    if not os.path.isfile(p):
        continue                          # apt lists compressed variants that aren't all published
    if os.path.getsize(p) != int(size) or hashlib.sha256(open(p, "rb").read()).hexdigest() != h:
        bad.append(name)
if not block or bad:
    sys.exit("%s: Release and its indexes disagree (%s): publish and sign again" % (d, ", ".join(bad) or "no SHA256"))
IDX
done
# The v0.4.x migration files (repo.sh migrate, sign.sh): published only as a complete, signed set,
# signed by the archive key and with the archive key next to them; otherwise nothing is copied.
M="$APT_HOME/public/migrate"
if [ -d "$M" ]; then
	for f in handtop-migrate handtop-migrate.asc handtop-archive.asc; do
		[ -s "$M/$f" ] || { echo "incomplete $M: $f missing (repo.sh migrate, then sign.sh)" >&2; exit 1; }
	done
	cmp -s "$M/handtop-archive.asc" "$APT_HOME/handtop-archive-public.asc" ||
		{ echo "$M/handtop-archive.asc is not the archive's public key" >&2; exit 1; }
	[ "$(signer "$M/handtop-migrate.asc" "$M/handtop-migrate")" = "$FPR" ] ||
		{ echo "$M/handtop-migrate: signature missing, stale or not by the archive key (run sign.sh)" >&2; exit 1; }
fi
rsync -rL --delete --exclude=.git --exclude=README.md --exclude=.nojekyll --exclude=/handtop-archive.asc \
	"$APT_HOME/public/" "$DEST/"
touch "$DEST/.nojekyll"
cp "$APT_HOME/handtop-archive-public.asc" "$DEST/handtop-archive.asc"
cat > "$DEST/README.md" <<README
# Handtop apt repository

Packages for [Handtop](https://github.com/junsulee119/handtop), published with GitHub Pages.
Installs get them through Handtop's Update app; there is nothing to do here by hand.

- Suites: \`trixie-stable\` (released), \`trixie-testing\` (pre-releases and fixes under test).
- Signing key fingerprint: \`$FPR\` (\`handtop-archive.asc\`).
README
echo "exported to $DEST; commit and push it there"
