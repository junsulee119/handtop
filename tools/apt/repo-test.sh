#!/bin/bash
# Imports, publishes, signs and exports fake releases in throwaway aptly homes.
# Run as the build server's own user (needs aptly and gpg).
#   bash tools/apt/repo-test.sh
set -euo pipefail
HERE=$(dirname "$(realpath "$0")")
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
export HANDTOP_APT_HOME="$T/apt"
pass=0; fail=0
ok()  { echo "PASS: $*"; pass=$((pass+1)); }
bad() { echo "FAIL: $*"; fail=$((fail+1)); }
deb() {  # deb <version> [paths, one per line] [arch] [name] [extra control fields]
  local d p out arch="${3:-arm64}" name="${4:-handtop-repotest}"
  d=$(mktemp -d "$T/build.XXXXXX")
  mkdir -p "$d/DEBIAN" "$d/usr/share/doc/$name"
  while IFS= read -r p; do
    [ -n "$p" ] || continue
    [[ "$p" == /* ]] || p="/usr/share/doc/$name/$p"
    mkdir -p "$d$(dirname "$p")"
    echo x > "$d$p"
  done <<<"${2:-}"
  printf 'Package: %s\nVersion: %s\nArchitecture: %s\nMaintainer: test <t@t>\nDescription: test\n' \
    "$name" "$1" "$arch" > "$d/DEBIAN/control"
  [ -z "${5:-}" ] || printf '%s\n' "$5" >> "$d/DEBIAN/control"
  echo "$1" > "$d/usr/share/doc/$name/version"
  out="$T/${name}_${1}_${arch}.deb"
  dpkg-deb --root-owner-group -b "$d" "$out" >/dev/null
  echo "$out"
}
version_in() { sed -n 's/^Version: //p' "$HANDTOP_APT_HOME/public/dists/$1/main/binary-arm64/Packages"; }
R() { bash "$HERE/repo.sh" "$@"; }
A() { aptly -config="$HANDTOP_APT_HOME/aptly.conf" "$@"; }
refuses() {
  local title="$1" diagnostic="$2" out; shift 2
  if out=$("$@" 2>&1); then
    bad "$title (accepted)"
  elif grep -Fq -- "$diagnostic" <<<"$out"; then
    ok "$title"
  else
    bad "$title: $out"
  fi
}
R init >/dev/null
d1=$(deb 1.0)
out=$(R add "$d1")
grep -Fq "new package, no published baseline" <<<"$out" && ok "a new package reports no baseline" || bad "no message on first add"
R snapshot s1 >/dev/null
R publish s1 trixie-testing >/dev/null && ok "first publish to testing" || bad "first publish to testing"
R publish s1 trixie-stable >/dev/null && ok "first publish to stable" || bad "first publish to stable"
d2=$(deb 2.0 'extra detail.txt')
R add "$d2" >/dev/null; R snapshot s2 >/dev/null
R publish s2 trixie-testing >/dev/null && ok "second publish to testing (switch)" || bad "second publish to testing"
[ "$(version_in trixie-testing | sort -V | tail -1)" = 2.0 ] && ok "testing has 2.0" || bad "testing: $(version_in trixie-testing | xargs)"
[ "$(version_in trixie-stable | xargs)" = 1.0 ] && ok "stable still 1.0" || bad "stable: $(version_in trixie-stable | xargs)"
R publish s2 trixie-stable >/dev/null && ok "promote to stable (switch)" || bad "promote to stable"
[ "$(version_in trixie-stable | sort -V | tail -1)" = 2.0 ] && ok "stable has 2.0" || bad "stable: $(version_in trixie-stable | xargs)"
refuses "a dropped path with spaces is refused and named in full" "/usr/share/doc/handtop-repotest/extra detail.txt" R add "$(deb 3.0)"
refuses "a previously validated snapshot cannot remove published versions" "would lose published" R publish s1 trixie-stable

m="$HANDTOP_APT_HOME/manifests"
m1="$m/$(sha256sum < "$d1" | cut -d' ' -f1).json"
m2="$m/$(sha256sum < "$d2" | cut -d' ' -f1).json"
mv "$m2" "$T/saved.json"
d21=$(deb 2.1 'extra detail.txt')
refuses "a missing published baseline fails even with an older one present" "missing baseline for handtop-repotest 2.0 arm64" R add "$d21"
cp "$m1" "$m2"
refuses "an older manifest at the expected filename fails" "stale baseline for handtop-repotest 2.0 arm64" R add "$d21"
changed=$(deb 2.0 changed)
pool2=$(find "$HANDTOP_APT_HOME/public/pool" -name "${d2##*/}" -print -quit)
cp "$pool2" "$T/published.deb"
cp "$changed" "$pool2"
refuses "baseline refuses changed bytes at the published pool path" "expected published handtop-repotest 2.0 arm64" R baseline
cp "$T/published.deb" "$pool2"
R baseline >/dev/null
cmp -s "$m2" "$T/saved.json" && ok "baseline rebuilds the manifest from the exact published deb" ||
  bad "the rebuilt baseline differs"
refuses "different bytes at a published identity are refused" "already exists with different bytes" R add "$changed"

# Feed aptly one valid and one malformed file after validation, so the real aptly 1.5.0
# error path saves one member before it returns. It must never reach the release repository.
mkdir "$T/bin"
export REPOTEST_APTLY REPOTEST_BROKEN="$T/broken.deb"
REPOTEST_APTLY=$(command -v aptly)
echo broken > "$REPOTEST_BROKEN"
cat > "$T/bin/aptly" <<'SH'
#!/bin/bash
set -euo pipefail
if [ "$2" = repo ] && [ "$3" = add ]; then
  rc=0
  "$REPOTEST_APTLY" "${@:1:5}" "$REPOTEST_BROKEN" || rc=$?
  if [ "$rc" -ne 0 ] && "$REPOTEST_APTLY" "$1" repo search "$4" >/dev/null; then
    echo "aptly saved a member in staging before failing" >&2
  fi
  exit "$rc"
fi
exec "$REPOTEST_APTLY" "$@"
SH
chmod +x "$T/bin/aptly"
newdeb=$(deb 1.0 '' arm64 handtop-repotest-new)
PATH="$T/bin:$PATH" refuses "aptly reports a genuinely partial staging import" "aptly saved a member in staging before failing" \
  R add "$d21" "$newdeb"
R snapshot after-failure >/dev/null
[ "$(A snapshot search after-failure)" = "$(A snapshot search s2)" ] &&
  ok "the snapshot after a failed batch has exactly the previous package set" || bad "partial batch reached a snapshot"
R add "$d21" "$newdeb" >/dev/null && ok "the complete batch can be retried" || bad "retry of complete batch failed"
printf 'handtop-repotest /usr/share/doc/handtop-repotest/extra detail.txt\n' > "$T/removed.txt"
export HANDTOP_REMOVED_FILES="$T/removed.txt"
R add "$(deb 3.0)" >/dev/null 2>&1 && ok "a declared path with spaces can be dropped" ||
  bad "declared drop refused"

# Signing and export (review 2026-11-26 #77): a throwaway key (no passphrase) signs the published
# suites with sign.sh; export.sh copies them into a fake handtop-apt checkout and verifies it there.
R snapshot s3 >/dev/null; R publish s3 trixie-testing >/dev/null
export GNUPGHOME="$HANDTOP_APT_HOME/gnupg"; mkdir -m 700 "$GNUPGHOME"
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
# A higher version in the same suite: the tested 3.0 downloads, but cards would pick 3.1 (#96).
R add "$(deb 3.1)" >/dev/null 2>&1; R snapshot s4 >/dev/null; R publish s4 trixie-testing >/dev/null
HANDTOP_APT_TEST_PASS='' bash "$HERE/sign.sh" >/dev/null 2>&1; X >/dev/null 2>&1 || true
out=$(bash "$HERE/client-test.sh" "file:$C" trixie-testing "$T/packages.txt" 2>&1) && bad "client-test accepted a suite where cards pick another version" ||
  { grep -q "a card would install handtop-repotest 3.1" <<<"$out" && ok "client-test refuses a suite where cards pick another version"; }
echo "handtop-repotest 3.0 arm64 $(printf x | sha256sum | cut -d' ' -f1)" > "$T/packages.txt"
out=$(bash "$HERE/client-test.sh" "file:$C" trixie-testing "$T/packages.txt" 2>&1) && bad "client-test accepted other bytes" ||
  { grep -q "is not the tested package" <<<"$out" && ok "client-test refuses bytes that weren't tested"; }
HANDTOP_APT_VALID_DAYS=3 HANDTOP_APT_TEST_PASS='' bash "$HERE/sign.sh" >/dev/null 2>&1
out=$(X) && bad "a Release expiring in 3 days was exported" || { grep -q "less than 7 days" <<<"$out" && ok "export refuses a nearly expired Release"; }

# A separate archive lets the suites name different published predecessors and architectures.
export HANDTOP_APT_HOME="$T/history"
R init >/dev/null
history=handtop-repotest-history
initial=$(deb '1:1.0~old' '' arm64 "$history")
A repo create unchecked >/dev/null; A repo add unchecked "$initial" >/dev/null
A snapshot create unchecked from repo unchecked >/dev/null
refuses "publish refuses an unvalidated snapshot" "package set was not validated" R publish unchecked trixie-testing
A repo add handtop "$initial" >/dev/null
refuses "snapshot refuses an unvalidated local repository" "package set was not validated" R snapshot h0
other_arch=$(deb '1:1.1+other' arch-only all "$history")
refuses "add refuses an incomplete batch for an older unvalidated repository" "re-add their exact .debs" R add "$other_arch"
R add "$initial" "$other_arch" >/dev/null
R snapshot h1 >/dev/null; R publish h1 trixie-stable >/dev/null
R add "$(deb '1:1.1' settings arm64 "$history")" >/dev/null
R snapshot h2 >/dev/null; R publish h2 trixie-testing >/dev/null
refuses "the highest lower version is selected across both suites" "published $history 1:1.1 arm64" R add "$(deb '1:1.2' '' arm64 "$history")"
R add "$(deb '1:1.4' $'settings\nlater' arm64 "$history")" >/dev/null
R add "$(deb '1:1.2' settings arm64 "$history")" >/dev/null &&
  ok "the other architecture and an unpublished higher version are ignored" || bad "wrong baseline selected"
R snapshot h3 >/dev/null; R publish h3 trixie-testing >/dev/null
R add "$(deb '1:1.3' settings arm64 "$history")" >/dev/null &&
  ok "a published higher version is ignored for a backfill" || bad "backfill compared to a higher version"

donor=handtop-repotest-donor
recipient=handtop-repotest-recipient
shared='/usr/share/repotest/split file'
R add "$(deb 1.0 "$shared" arm64 "$donor")" >/dev/null
R snapshot h4 >/dev/null; R publish h4 trixie-testing >/dev/null
refuses "a different package cannot take over a file without transfer metadata" "needs versioned Breaks and Replaces" \
  R add "$(deb 1.0 "$shared" arm64 "$recipient")"
printf -v relationships 'Breaks: %s (<< 1.0)\nReplaces: %s (<< 2.0)' "$donor" "$donor"
refuses "Breaks must cover the actual old owner version" "needs versioned Breaks and Replaces" \
  R add "$(deb 1.0 "$shared" arm64 "$recipient" "$relationships")"
printf '%s %s\n' "$donor" "$shared" >> "$HANDTOP_REMOVED_FILES"
printf -v relationships 'Breaks: %s (<< 2.0)\nReplaces: %s (<< 2.0)' "$donor" "$donor"
R add "$(deb 2.0 '' arm64 "$donor")" "$(deb 1.0 "$shared" arm64 "$recipient" "$relationships")" >/dev/null &&
  ok "a declared transfer with versioned Breaks and Replaces is accepted" || bad "a valid transfer was refused"

echo "repo-test: $pass passed, $fail failed"
[ "$fail" = 0 ]
