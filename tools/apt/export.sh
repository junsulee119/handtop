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
rsync -rL --delete --exclude=.git --exclude=README.md --exclude=.nojekyll --exclude=handtop-archive.asc \
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
