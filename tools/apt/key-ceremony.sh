#!/bin/bash
# Creates Handtop's archive signing key (project doc update-system.md, "Signing").
# The primary key exists only in RAM (/dev/shm) and in the backup you copy to a USB stick;
# the build server keeps only the signing subkey, in ~/.handtop-apt/gnupg.
# The passphrase is asked once (twice to confirm), kept only in this shell's memory and given to
# gpg through a pipe; temporary files go to the RAM directory.
# Run interactively:  bash ~/handtop-apt-tools/key-ceremony.sh
# HANDTOP_KEY_TEST=1 runs it with the passphrase "test" into throwaway directories (test only).
set -euo pipefail
NAME="Handtop archive signing key"
KEEP="${HANDTOP_APT_HOME:-$HOME/.handtop-apt}/gnupg"
T=$(mktemp -d /dev/shm/handtop-key.XXXXXX)
chmod 700 "$T"
export TMPDIR="$T"
export GNUPGHOME="$T/gnupg"
mkdir -m 700 "$GNUPGHOME"
if [ "${HANDTOP_KEY_TEST:-0}" = 1 ]; then
	P="test"
	KEEP="$T/keep"
else
	if [ -e "$KEEP" ] && gpg --homedir "$KEEP" -K 2>/dev/null | grep -q .; then
		echo "A signing key already exists in $KEEP; not creating another." >&2
		exit 1
	fi
	echo "Choose a strong passphrase for the new key and write it down offline."
	while :; do
		read -r -s -p "Passphrase: " P; echo
		read -r -s -p "Again: " P2; echo
		if [ "$P" != "$P2" ]; then echo "They differ; try again."; continue; fi
		if [ "${#P}" -lt 12 ]; then echo "Use at least 12 characters."; continue; fi
		break
	done
	unset P2
fi
g() { gpg --batch --pinentry-mode loopback --passphrase-fd 3 "$@" 3<<<"$P"; }
echo "== 1/4 primary key (certify only, 10 years)"
g --quick-gen-key "$NAME" ed25519 cert 10y
FPR=$(gpg --list-keys --with-colons "$NAME" | awk -F: '/^fpr/{print $10; exit}')
echo "== 2/4 signing subkey (2 years)"
g --quick-add-key "$FPR" ed25519 sign 2y
OUT="$T/backup"
mkdir -m 700 "$OUT"
gpg --armor --export "$FPR" > "$OUT/handtop-archive-public.asc"
g --armor --export-secret-keys "$FPR" > "$OUT/handtop-archive-primary-SECRET.asc"
g --armor --export-secret-subkeys "$FPR" > "$T/signing-subkey.asc"
cp "$GNUPGHOME/openpgp-revocs.d/$FPR.rev" "$OUT/handtop-archive-revocation.rev"
echo "$FPR" > "$OUT/FINGERPRINT.txt"
tar -C "$OUT" -cf "$T/handtop-key-backup.tar" .
echo "== 3/4 importing only the signing subkey into $KEEP"
mkdir -p -m 700 "$KEEP"
echo "pinentry-mode loopback" > "$KEEP/gpg.conf"
gpg --homedir "$KEEP" --batch --import "$OUT/handtop-archive-public.asc"
g --homedir "$KEEP" --import "$T/signing-subkey.asc"
echo "$FPR:6:" | gpg --homedir "$KEEP" --batch --import-ownertrust
rm -f "$T/signing-subkey.asc"
unset P
gpg --homedir "$KEEP" -K "$FPR"
if ! gpg --homedir "$KEEP" -K "$FPR" | grep -q '^sec#'; then
	echo "ERROR: the primary secret key is in $KEEP; expected only the subkey (sec#)." >&2
	exit 1
fi
cp "$OUT/handtop-archive-public.asc" "$OUT/FINGERPRINT.txt" "$(dirname "$KEEP")/"
echo
echo "== 4/4 done. Fingerprint: $FPR"
echo "Backup to copy to the USB stick (contains the primary secret key, passphrase-protected):"
echo "  $T/handtop-key-backup.tar"
echo "After copying it, wipe the RAM copy:  bash ~/handtop-apt-tools/key-ceremony-wipe.sh $T"
