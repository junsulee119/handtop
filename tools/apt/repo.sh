#!/bin/bash
# Handtop's apt repository on the build server (aptly). Project doc: update-system.md.
# State lives in $HANDTOP_APT_HOME (default ~/.handtop-apt): aptly/ (database and pool),
# public/ (the published tree, unsigned until tools/apt/sign.sh), gnupg/ (signing subkey only).
#
#   repo.sh init                         create the aptly config and the local repo
#   repo.sh add <file.deb>...            add packages to the local repo
#   repo.sh snapshot <name>              freeze the local repo as snapshot <name>
#   repo.sh publish <snapshot> <suite>   publish (or switch) <suite> to <snapshot>, unsigned
#   repo.sh migrate                      put tools/apt/handtop-migrate and the public key in
#                                        public/migrate/ (moving v0.4.x cards; sign.sh signs it)
#   repo.sh list                         snapshots and published suites
#
# Suites: trixie-testing, trixie-stable. Promotion = publishing the same snapshot to trixie-stable.
# Signing is a separate step (sign.sh) because it needs Jason's passphrase.
set -euo pipefail
APT_HOME="${HANDTOP_APT_HOME:-$HOME/.handtop-apt}"
CONF="$APT_HOME/aptly.conf"
REPO=handtop
die() { echo "repo.sh: $*" >&2; exit 1; }
a() { aptly -config="$CONF" "$@"; }

case "${1:-}" in
init)
	mkdir -p "$APT_HOME/aptly" "$APT_HOME/public"
	if [ ! -e "$CONF" ]; then
		cat > "$CONF" <<CONF
{
  "rootDir": "$APT_HOME/aptly",
  "architectures": ["arm64", "all"],
  "gpgDisableSign": true,
  "gpgDisableVerify": true,
  "FileSystemPublishEndpoints": {
    "pages": { "rootDir": "$APT_HOME/public", "linkMethod": "copy" }
  }
}
CONF
	fi
	a repo show "$REPO" >/dev/null 2>&1 || a repo create -comment="Handtop packages" -component=main "$REPO"
	echo "ready: $CONF"
	;;
add)
	shift
	[ $# -gt 0 ] || die "no packages given"
	a repo add "$REPO" "$@"
	;;
snapshot)
	[ -n "${2:-}" ] || die "usage: repo.sh snapshot <name>"
	a snapshot create "$2" from repo "$REPO"
	;;
publish)
	snap="${2:-}"; suite="${3:-}"
	[ -n "$snap" ] && [ -n "$suite" ] || die "usage: repo.sh publish <snapshot> <suite>"
	case "$suite" in trixie-testing|trixie-stable) ;; *) die "unknown suite $suite" ;; esac
	if a publish list -raw 2>/dev/null | grep -qx "filesystem:pages: $suite"; then
		a publish switch -skip-signing "$suite" filesystem:pages: "$snap"
	else
		a publish snapshot -skip-signing -acquire-by-hash -architectures=arm64,all -distribution="$suite" -component=main \
			-origin=Handtop -label=Handtop "$snap" filesystem:pages:
	fi
	echo "published $snap as $suite (unsigned): run tools/apt/sign.sh next"
	;;
migrate)
	TOP=$(cd "$(dirname "$(realpath "$0")")/../.." && pwd)
	mkdir -p "$APT_HOME/public/migrate"
	install -m644 "$TOP/tools/apt/handtop-migrate" "$APT_HOME/public/migrate/handtop-migrate"
	install -m644 "$TOP/overlay/usr/share/keyrings/handtop-archive.asc" "$APT_HOME/public/migrate/handtop-archive.asc"
	rm -f "$APT_HOME/public/migrate/handtop-migrate.asc"
	echo "public/migrate updated (unsigned): run tools/apt/sign.sh next"
	;;
list)
	a snapshot list
	a publish list
	;;
*)
	sed -n '2,17p' "$0"; exit 1 ;;
esac
