#!/bin/bash
# Handtop's apt repository on the build server (aptly). Project doc: docs/apt-repository.md.
# State lives in $HANDTOP_APT_HOME (default ~/.handtop-apt): aptly/ (database and pool),
# manifests/ (validated payloads and package sets), public/ (published tree), gnupg/ (signing subkey).
#
#   repo.sh init                         create the aptly config and the local repo
#   repo.sh baseline                     rebuild baselines from the published pool
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
TOP=$(cd "$(dirname "$(realpath "$0")")/../.." && pwd)
gate() { python3 "$TOP/tools/apt/repo-gate.py" "$APT_HOME" "$@"; }

# Keep validation, aptly changes and checks in a single writer's hands.
case "${1:-}" in
init|baseline|add|snapshot|publish)
	mkdir -p "$APT_HOME"
	exec 9>"$APT_HOME/repo.lock"
	flock -w 60 9 || die "another archive command holds $APT_HOME/repo.lock"
	;;
esac

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
baseline|add|snapshot)
	gate "$@"
	;;
publish)
	snap="${2:-}"; suite="${3:-}"
	[ -n "$snap" ] && [ -n "$suite" ] || die "usage: repo.sh publish <snapshot> <suite>"
	case "$suite" in trixie-testing|trixie-stable) ;; *) die "unknown suite $suite" ;; esac
	gate publish "$snap" "$suite"
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
	sed -n '2,18p' "$0"; exit 1 ;;
esac
