#!/bin/bash
# Copies the signed tree from $HANDTOP_APT_HOME/public into a handtop-apt checkout for GitHub Pages:
# links materialised as files, .nojekyll, the public key and a README. Leaves .git and .gitattributes
# alone and removes files that are no longer published (only inside the checkout).
#   bash tools/apt/export.sh [--with-migrate] [--nonempty SUITE]... <handtop-apt checkout>
# --with-migrate: the v0.4.x migration files must be there and be this checkout's handtop-migrate
# (release exports). --nonempty SUITE: that suite must list packages (the suite being released).
# tools/apt/verify-tree.py checks the tree first and the checkout again after copying (review
# 2026-11-19 #20, 2026-11-26 #77); a tree that fails is not copied, a checkout that fails is not to be pushed.
set -euo pipefail
TOP=$(cd "$(dirname "$(realpath "$0")")/../.." && pwd)
APT_HOME="${HANDTOP_APT_HOME:-$HOME/.handtop-apt}"
opts=()
while [ $# -gt 1 ]; do
	case "$1" in
		--with-migrate) opts+=(--migrate "$TOP/tools/apt/handtop-migrate"); shift ;;
		--nonempty) opts+=(--nonempty "$2"); shift 2 ;;
		*) echo "unknown option $1" >&2; exit 2 ;;
	esac
done
DEST="${1:?usage: export.sh [--with-migrate] [--nonempty SUITE]... <handtop-apt checkout>}"
[ -d "$DEST/.git" ] || { echo "$DEST is not a git checkout" >&2; exit 1; }
# The right repository: Pages serves whatever is pushed there.
url=$(git -C "$DEST" remote get-url origin 2>/dev/null || true)
[[ "$url" =~ ^(https://github\.com/|git@github\.com:)junsulee119/handtop-apt(\.git)?$ ]] ||
	{ echo "$DEST is not a clone of junsulee119/handtop-apt (origin: ${url:-none})" >&2; exit 1; }
FPR=$(cat "$APT_HOME/FINGERPRINT.txt")
KEY="$APT_HOME/handtop-archive-public.asc"
G=$(mktemp -d); trap 'rm -rf "$G"' EXIT
gpg --homedir "$G" --batch -q --import "$KEY" 2>/dev/null
verify() { python3 "$TOP/tools/apt/verify-tree.py" "$1" --fpr "$FPR" --gnupghome "$G" --key "$KEY" "${opts[@]}"; }
verify "$APT_HOME/public" || { echo "not exported: fix the tree above (publish / sign.sh)" >&2; exit 1; }
rsync -rL --delete --exclude=/.git --exclude=/.gitattributes --exclude=/README.md --exclude=/.nojekyll \
	--exclude=/handtop-archive.asc "$APT_HOME/public/" "$DEST/"
touch "$DEST/.nojekyll"
cp "$KEY" "$DEST/handtop-archive.asc"
cat > "$DEST/README.md" <<README
# Handtop apt repository

Packages for [Handtop](https://github.com/junsulee119/handtop), published with GitHub Pages.
Installs get them through Handtop's Update app; there is nothing to do here by hand.

- Suites: \`trixie-stable\` (released), \`trixie-testing\` (pre-releases and fixes under test).
- Signing key fingerprint: \`$FPR\` (\`handtop-archive.asc\`).
README
verify "$DEST" || { echo "the checkout $DEST doesn't verify after copying: don't push it" >&2; exit 1; }
echo "exported to $DEST; commit and push it there"
