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
echo "repo-test: $pass passed, $fail failed"
[ "$fail" = 0 ]
