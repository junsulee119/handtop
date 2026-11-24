#!/bin/bash
# Signs the published suites in $HANDTOP_APT_HOME/public with the archive signing subkey.
# Sets Date to now and Valid-Until to now + 30 days in each Release, then writes InRelease
# (clear-signed) and Release.gpg (detached), and checks both against the public key.
# Run by Jason (asks for the key's passphrase once):  bash tools/apt/sign.sh
# Re-run at least monthly, even without a new release, or clients refuse the expired Release.
set -euo pipefail
APT_HOME="${HANDTOP_APT_HOME:-$HOME/.handtop-apt}"
export GNUPGHOME="$APT_HOME/gnupg"
FPR=$(cat "$APT_HOME/FINGERPRINT.txt")
DAYS="${HANDTOP_APT_VALID_DAYS:-30}"
[ -d "$APT_HOME/public/dists" ] || { echo "nothing published in $APT_HOME/public" >&2; exit 1; }
T=$(mktemp -d /dev/shm/handtop-sign.XXXXXX)
trap 'rm -rf "$T"' EXIT
export TMPDIR="$T"
if [ "${HANDTOP_APT_TEST_PASS+x}" ]; then P="$HANDTOP_APT_TEST_PASS"; else read -r -s -p "Passphrase for the Handtop archive key: " P; echo; fi
g() { gpg --batch --yes --pinentry-mode loopback --passphrase-fd 3 --local-user "$FPR" --digest-algo SHA512 "$@" 3<<<"$P"; }
now=$(LC_ALL=C date -u '+%a, %d %b %Y %H:%M:%S UTC')
until=$(LC_ALL=C date -u -d "+$DAYS days" '+%a, %d %b %Y %H:%M:%S UTC')
for rel in "$APT_HOME"/public/dists/*/Release; do
	d=$(dirname "$rel")
	awk -v now="$now" -v until="$until" '
		/^Date:/ { print "Date: " now; print "Valid-Until: " until; next }
		/^Valid-Until:/ { next }
		{ print }' "$rel" > "$T/Release"
	cat "$T/Release" > "$rel"
	g --clearsign -o "$d/InRelease" "$rel"
	g --detach-sign --armor -o "$d/Release.gpg" "$rel"
	gpg --batch --verify "$d/InRelease" 2>&1 | grep -q 'Good signature' || { echo "InRelease check failed: $d" >&2; exit 1; }
	gpg --batch --verify "$d/Release.gpg" "$rel" 2>&1 | grep -q 'Good signature' || { echo "Release.gpg check failed: $d" >&2; exit 1; }
	echo "signed $(basename "$d"): valid until $until"
done
# The script that moves v0.4.x cards onto packages (repo.sh migrate): a detached signature.
M="$APT_HOME/public/migrate/handtop-migrate"
if [ -f "$M" ]; then
	g --detach-sign --armor -o "$M.asc" "$M"
	gpg --batch --verify "$M.asc" "$M" 2>&1 | grep -q 'Good signature' || { echo "handtop-migrate signature check failed" >&2; exit 1; }
	echo "signed migrate/handtop-migrate"
fi
unset P
