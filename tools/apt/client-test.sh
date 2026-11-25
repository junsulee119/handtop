#!/bin/bash
# Checks the live repository like a client would: apt-get update against <url> with a throwaway
# state directory, the published key, and both suites; fails on any signature or expiry error.
#   bash tools/apt/client-test.sh https://junsulee119.github.io/handtop-apt
set -euo pipefail
URL="${1:?usage: client-test.sh <url>}"
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
echo "client-test: OK"
