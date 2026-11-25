#!/bin/bash
# Tests repo.sh against a throwaway aptly home (no signing, nothing published for real): two releases
# of a tiny package, each published to trixie-testing and then switched into trixie-stable, as a
# release goes. Run as the build server's own user (needs aptly).
#   bash tools/apt/repo-test.sh
set -euo pipefail
HERE=$(dirname "$(realpath "$0")")
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
export HANDTOP_APT_HOME="$T/apt"
pass=0; fail=0
ok()  { echo "PASS: $*"; pass=$((pass+1)); }
bad() { echo "FAIL: $*"; fail=$((fail+1)); }
deb() {  # deb <version> [extra file name]: a tiny arm64 package
  local d="$T/build-$1"; mkdir -p "$d/DEBIAN" "$d/usr/share/doc/handtop-repotest"
  [ -n "${2:-}" ] && echo x > "$d/usr/share/doc/handtop-repotest/$2"
  printf 'Package: handtop-repotest\nVersion: %s\nArchitecture: arm64\nMaintainer: test <t@t>\nDescription: test\n' "$1" > "$d/DEBIAN/control"
  echo "$1" > "$d/usr/share/doc/handtop-repotest/version"
  dpkg-deb --root-owner-group -b "$d" "$T/handtop-repotest_$1_arm64.deb" >/dev/null
  echo "$T/handtop-repotest_$1_arm64.deb"
}
version_in() { sed -n 's/^Version: //p' "$HANDTOP_APT_HOME/public/dists/$1/main/binary-arm64/Packages"; }
R="bash $HERE/repo.sh"
$R init >/dev/null
$R add "$(deb 1.0)" >/dev/null 2>&1; $R snapshot s1 >/dev/null
$R publish s1 trixie-testing >/dev/null && ok "first publish to testing" || bad "first publish to testing"
$R publish s1 trixie-stable >/dev/null && ok "first publish to stable" || bad "first publish to stable"
$R add "$(deb 2.0 extra)" >/dev/null 2>&1; $R snapshot s2 >/dev/null
$R publish s2 trixie-testing >/dev/null && ok "second publish to testing (switch)" || bad "second publish to testing"
[ "$(version_in trixie-testing | sort -V | tail -1)" = 2.0 ] && ok "testing has 2.0" || bad "testing: $(version_in trixie-testing | xargs)"
[ "$(version_in trixie-stable | xargs)" = 1.0 ] && ok "stable still 1.0" || bad "stable: $(version_in trixie-stable | xargs)"
$R publish s2 trixie-stable >/dev/null && ok "promote to stable (switch)" || bad "promote to stable"
[ "$(version_in trixie-stable | sort -V | tail -1)" = 2.0 ] && ok "stable has 2.0" || bad "stable: $(version_in trixie-stable | xargs)"
out=$($R add "$(deb 3.0)" 2>&1) && bad "a version that drops a file was added" ||
  { grep -q "/usr/share/doc/handtop-repotest/extra" <<<"$out" && ok "a dropped file is refused and named"; }
printf 'handtop-repotest /usr/share/doc/handtop-repotest/extra\n' > "$T/removed.txt"
HANDTOP_REMOVED_FILES="$T/removed.txt" $R add "$(deb 3.0)" >/dev/null 2>&1 && ok "a declared drop is accepted" ||
  bad "declared drop refused"

# Signing and export (review 2026-11-26 #77): a throwaway key (no passphrase) signs the published
# suites with sign.sh; export.sh copies them into a fake handtop-apt checkout and verifies it there.
$R publish "$($R snapshot s3 >/dev/null; echo s3)" trixie-testing >/dev/null
export GNUPGHOME="$HANDTOP_APT_HOME/gnupg"; mkdir -p -m 700 "$GNUPGHOME"
gpg --batch -q --passphrase '' --quick-gen-key "repo-test <t@t>" ed25519 sign 1d 2>/dev/null
gpg --batch --with-colons --list-keys 2>/dev/null | awk -F: '$1 == "fpr" {print $10; exit}' > "$HANDTOP_APT_HOME/FINGERPRINT.txt"
gpg --batch --armor --export > "$HANDTOP_APT_HOME/handtop-archive-public.asc"
unset GNUPGHOME
HANDTOP_APT_TEST_PASS='' bash "$HERE/sign.sh" >/dev/null 2>&1 && ok "sign.sh signs both suites" || bad "sign.sh failed"
C="$T/checkout"; git init -q "$C"; git -C "$C" remote add origin https://github.com/junsulee119/handtop-apt.git
echo '* -text' > "$C/.gitattributes"
X() { bash "$HERE/export.sh" "$@" "$C" 2>&1; }
out=$(X --nonempty trixie-testing --nonempty trixie-stable) && ok "export: signed, complete tree" || bad "export: $out"
[ "$(cat "$C/.gitattributes" 2>/dev/null)" = '* -text' ] && ok "export keeps .gitattributes" || bad ".gitattributes gone"
deb=$(find "$HANDTOP_APT_HOME/public/pool" -name '*3.0*.deb' | head -1)
cp "$deb" "$T/keep.deb"; echo x >> "$deb"
out=$(X) && bad "a changed pool package was exported" || { grep -q "doesn't match its index entry" <<<"$out" && ok "export refuses a changed pool package"; }
cp "$T/keep.deb" "$deb"
out=$(X --with-migrate) && bad "exported without the migration files" || { grep -q "migrate/ missing" <<<"$out" && ok "--with-migrate needs the migration files"; }
# A client of the exported tree gets exactly the listed packages from the suite (client-test.sh).
d3="$T/handtop-repotest_3.0_arm64.deb"
echo "handtop-repotest 3.0 arm64 $(sha256sum < "$d3" | cut -d' ' -f1)" > "$T/packages.txt"
out=$(bash "$HERE/client-test.sh" "file:$C" trixie-testing "$T/packages.txt" 2>&1) && ok "client gets the tested package from testing" ||
  bad "client-test: $(echo "$out" | tail -3)"
echo "handtop-repotest 3.0 arm64 $(printf x | sha256sum | cut -d' ' -f1)" > "$T/packages.txt"
out=$(bash "$HERE/client-test.sh" "file:$C" trixie-testing "$T/packages.txt" 2>&1) && bad "client-test accepted other bytes" ||
  { grep -q "is not the tested package" <<<"$out" && ok "client-test refuses bytes that weren't tested"; }
HANDTOP_APT_VALID_DAYS=3 HANDTOP_APT_TEST_PASS='' bash "$HERE/sign.sh" >/dev/null 2>&1
out=$(X) && bad "a Release expiring in 3 days was exported" || { grep -q "less than 7 days" <<<"$out" && ok "export refuses a nearly expired Release"; }
echo "repo-test: $pass passed, $fail failed"
[ "$fail" = 0 ]
