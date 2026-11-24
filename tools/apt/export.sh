#!/bin/bash
# Copies the signed tree from $HANDTOP_APT_HOME/public into a handtop-apt checkout for GitHub Pages:
# links materialised as files, .nojekyll, the public key and a README. Leaves .git alone and
# removes files that are no longer published (only inside the checkout, never .git).
#   bash tools/apt/export.sh <handtop-apt checkout>
set -euo pipefail
APT_HOME="${HANDTOP_APT_HOME:-$HOME/.handtop-apt}"
DEST="${1:?usage: export.sh <handtop-apt checkout>}"
[ -d "$DEST/.git" ] || { echo "$DEST is not a git checkout" >&2; exit 1; }
for rel in "$APT_HOME"/public/dists/*/Release; do
	[ -s "$(dirname "$rel")/InRelease" ] && [ "$(dirname "$rel")/InRelease" -nt "$rel" ] || { echo "not signed: $rel (run sign.sh)" >&2; exit 1; }
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
	G=$(mktemp -d); trap 'rm -rf "$G"' EXIT
	gpg --homedir "$G" --batch -q --import "$APT_HOME/handtop-archive-public.asc" 2>/dev/null
	signer=$(gpg --homedir "$G" --batch --status-fd 1 --verify "$M/handtop-migrate.asc" "$M/handtop-migrate" 2>/dev/null |
		awk '$2 == "VALIDSIG" {print $NF}' || true)
	[ "$signer" = "$(cat "$APT_HOME/FINGERPRINT.txt")" ] ||
		{ echo "$M/handtop-migrate: signature missing, stale or not by the archive key (run sign.sh)" >&2; exit 1; }
fi
rsync -rL --delete --exclude=.git --exclude=README.md --exclude=.nojekyll --exclude=/handtop-archive.asc \
	"$APT_HOME/public/" "$DEST/"
touch "$DEST/.nojekyll"
cp "$APT_HOME/handtop-archive-public.asc" "$DEST/handtop-archive.asc"
FPR=$(cat "$APT_HOME/FINGERPRINT.txt")
cat > "$DEST/README.md" <<README
# Handtop apt repository

Packages for [Handtop](https://github.com/junsulee119/handtop), published with GitHub Pages.
Installs get them through Handtop's Update app; there is nothing to do here by hand.

- Suites: \`trixie-stable\` (released), \`trixie-testing\` (pre-releases and fixes under test).
- Signing key fingerprint: \`$FPR\` (\`handtop-archive.asc\`).
README
echo "exported to $DEST; commit and push it there"
