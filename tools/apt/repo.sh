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
	# A file the package's last added version had and this one lacks would be deleted from cards on
	# upgrade: refused unless build/pkg/removed-files.txt says it goes on purpose (review #9).
	TOP=$(cd "$(dirname "$(realpath "$0")")/../.." && pwd)
	M="$APT_HOME/manifests"; mkdir -p "$M"
	T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
	for d in "$@"; do
		n=$(dpkg-deb -f "$d" Package)
		dpkg-deb -c "$d" | awk '$1 !~ /^d/ {sub(/^\./, "", $6); print $6}' | sort > "$T/$n.list"
		[ -f "$M/$n.list" ] || continue
		comm -23 "$M/$n.list" "$T/$n.list" > "$T/$n.gone"
		awk -v n="$n" '$1 == n {print $2}' "${HANDTOP_REMOVED_FILES:-$TOP/build/pkg/removed-files.txt}" 2>/dev/null |
			sort > "$T/$n.ok"
		comm -23 "$T/$n.gone" "$T/$n.ok" > "$T/$n.bad"
		if [ -s "$T/$n.bad" ]; then
			echo "repo.sh: $(basename "$d") lacks files its last version had:" >&2
			sed 's/^/  /' "$T/$n.bad" | head -20 >&2
			die "refused (list them in build/pkg/removed-files.txt if they go on purpose)"
		fi
	done
	a repo add "$REPO" "$@"
	for d in "$@"; do n=$(dpkg-deb -f "$d" Package); cp "$T/$n.list" "$M/$n.list"; done
	;;
snapshot)
	[ -n "${2:-}" ] || die "usage: repo.sh snapshot <name>"
	a snapshot create "$2" from repo "$REPO"
	;;
publish)
	snap="${2:-}"; suite="${3:-}"
	[ -n "$snap" ] && [ -n "$suite" ] || die "usage: repo.sh publish <snapshot> <suite>"
	case "$suite" in trixie-testing|trixie-stable) ;; *) die "unknown suite $suite" ;; esac
	# Already published: switch it (asked directly: the list's raw format differs between aptly versions,
	# e.g. 1.5.0 prints "filesystem:pages:. trixie-stable"; review 2026-11-19 #10).
	if a publish show "$suite" filesystem:pages: >/dev/null 2>&1; then
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
