#!/bin/bash
# Checks the live repository like a client would: apt-get update against <url> with a throwaway
# state directory, the published key, and both suites; fails on any signature or expiry error.
#   bash tools/apt/client-test.sh https://junsulee119.github.io/handtop-apt [SUITE PACKAGES]
# With SUITE and a build's package list (work/pkg/packages.txt from 09b): every package listed there is
# downloaded from that suite alone, at its exact version, and must be the same bytes the image was
# built and tested with (review 2026-11-26 #77, #81).
set -euo pipefail
URL="${1:?usage: client-test.sh <url> [SUITE PACKAGES]}"
SUITE="${2:-}"; SUMS="${3:-}"
APT_HOME="${HANDTOP_APT_HOME:-$HOME/.handtop-apt}"
T=$(mktemp -d)
trap 'rm -rf "$T"' EXIT
mkdir -p "$T/etc/apt/sources.list.d" "$T/etc/apt/preferences.d" "$T/state/lists/partial" "$T/cache/archives/partial" "$T/keys"
gpg --dearmor < "$APT_HOME/handtop-archive-public.asc" > "$T/keys/handtop.gpg"
cat > "$T/etc/apt/sources.list.d/handtop.sources" <<SRC
Types: deb
URIs: $URL
Suites: trixie-stable trixie-testing
Components: main
Architectures: arm64
Signed-By: $T/keys/handtop.gpg
SRC
: > "$T/etc/apt/sources.list"
out=$(apt-get -o Dir::Etc="$T/etc/apt" -o Dir::State="$T/state" -o Dir::Cache="$T/cache" \
	-o Dir::Etc::SourceList="$T/etc/apt/sources.list" -o APT::Architecture=arm64 \
	-o Debug::NoLocking=1 update 2>&1) && rc=0 || rc=$?
echo "$out"
if [ "$rc" != 0 ] || echo "$out" | grep -E -q '^(W|E):|NO_PUBKEY|not signed|expired|invalid'; then
	echo "client-test: FAILED" >&2; exit 1
fi
if [ -n "$SUITE" ]; then
	[ -s "$SUMS" ] || { echo "client-test: no $SUMS" >&2; exit 1; }
	sed -i "s/^Suites: .*/Suites: $SUITE/" "$T/etc/apt/sources.list.d/handtop.sources"
	# The card's own pins (handtop-keyring's file): what apt picks there is what cards get (#96).
	cp "$(dirname "$(realpath "$0")")/../../overlay/etc/apt/preferences.d/handtop.pref" "$T/etc/apt/preferences.d/"
	find "$T/state/lists" -maxdepth 1 -type f -delete
	A=(-o Dir::Etc="$T/etc/apt" -o Dir::State="$T/state" -o Dir::Cache="$T/cache"
	   -o Dir::Etc::SourceList="$T/etc/apt/sources.list" -o APT::Architecture=arm64 -o Debug::NoLocking=1)
	apt-get "${A[@]}" -qq update >/dev/null 2>&1 || { echo "client-test: update of $SUITE alone failed" >&2; exit 1; }
	mkdir -p "$T/dl"; n=0; badn=0
	while read -r pkg ver _arch sum; do
		if ! (cd "$T/dl" && apt-get "${A[@]}" -qq download "$pkg=$ver" </dev/null >/dev/null 2>&1); then
			echo "client-test: $pkg $ver not downloadable from $SUITE" >&2; badn=$((badn+1)); continue
		fi
		got=$(sha256sum "$T/dl/"*.deb | cut -d' ' -f1); find "$T/dl" -type f -delete
		[ "$got" = "$sum" ] || { echo "client-test: $pkg $ver from $SUITE is not the tested package" >&2; badn=$((badn+1)); }
		cand=$(apt-cache "${A[@]}" policy "$pkg" </dev/null 2>/dev/null | sed -n 's/^  Candidate: //p')
		[ "$cand" = "$ver" ] || { echo "client-test: in $SUITE a card would install $pkg $cand, not the tested $ver" >&2; badn=$((badn+1)); }
		n=$((n+1))
	done < "$SUMS"
	[ "$badn" = 0 ] || { echo "client-test: FAILED ($badn of $n packages)" >&2; exit 1; }
	echo "client-test: $n packages in $SUITE are the tested ones, and the ones a card picks"
fi
echo "client-test: OK"
