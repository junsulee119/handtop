# Handtop's apt repository

Part of updates without reflashing (planned for v0.5.0): Handtop's packages are published as a signed apt repository on GitHub Pages, <https://junsulee119.github.io/handtop-apt>, from the separate repository [junsulee119/handtop-apt](https://github.com/junsulee119/handtop-apt). As of 2026-11-18 it is live and **empty**; nothing on a handheld uses it yet.

## Layout

- Suites `trixie-stable` (released) and `trixie-testing` (pre-releases, fixes under test), component `main`, architectures `arm64` and `all`, `Origin: Handtop`, `Acquire-By-Hash: yes`.
- Each `Release` carries `Valid-Until` 30 days after signing; clients refuse it after that, so **the repository is re-signed at least monthly**, even when nothing changed.
- Built with aptly on the build server. A release is a snapshot; `trixie-testing` is published from it, and after the device test the **same snapshot** is switched to `trixie-stable`, so stable gets exactly the tested files.

## Signing key

- Primary key `EF04B02F6569FB6FC8EAF9C5F5962C429E9C69FF` ("Handtop archive signing key", ed25519, certify only, expires 2036-11-15). It exists only in Jason's offline backups (passphrase-protected, with its revocation certificate).
- Releases are signed with an ed25519 signing subkey that expires 2028-11-17. The build server holds only that subkey, in `~/.handtop-apt/gnupg` (`gpg -K` shows `sec#`). A new subkey has to be made with the primary key and shipped to devices (keyring package) well before then.
- Created 2026-11-18 with `tools/apt/key-ceremony.sh`: the primary key lived only in RAM (`/dev/shm`) until the backup was copied off and `key-ceremony-wipe.sh` removed it.
- The passphrase is Jason's; no script stores it. Signing asks for it once per run.

## Scripts (`tools/apt/`, run on the build server)

| Script | What | Who |
|---|---|---|
| `repo.sh init` / `add` / `snapshot` / `publish <snapshot> <suite>` / `list` | aptly state in `~/.handtop-apt` (`aptly/`, `public/`); publishes unsigned | Claude or Jason |
| `sign.sh` | sets `Date` and `Valid-Until`, writes `InRelease` and `Release.gpg`, checks both | Jason (passphrase) |
| `export.sh [--with-migrate] [--nonempty SUITE]… <checkout>` | checks the signed tree with `verify-tree.py` (both suites, signatures, Release fields and at least 7 days of validity, every index and by-hash object, every pool package, nothing unlisted; `--with-migrate`: this checkout's `handtop-migrate`, signed), copies it into a `handtop-apt` checkout (links as files, `.nojekyll`, public key, README; `.gitattributes` kept) and checks the checkout again | Claude or Jason |
| `client-test.sh <url> [SUITE packages.txt]` | `apt-get update` against the live URL with a throwaway state; fails on any signature or expiry error. With a suite and a build's `work/pkg/packages.txt`: every package downloaded from that suite alone at its exact version must be the tested bytes | after every push |
| `key-ceremony.sh`, `key-ceremony-wipe.sh` | one-time key creation | Jason |

## Publishing

1. `repo.sh add …`, `repo.sh snapshot <name>`, `repo.sh publish <name> trixie-testing`.
2. `ssh -t claude@<build server> "bash ~/handtop-apt-tools/sign.sh"` (Jason).
3. Export into the local `handtop-apt` clone; Jason commits and pushes; GitHub Pages deploys.
4. `client-test.sh https://junsulee119.github.io/handtop-apt`.

The `handtop-apt` checkout has `.gitattributes` `* -text`: any line-ending conversion would break the signatures.

## Monthly re-sign

Steps 2–4 above, about five minutes. Start **7 days before** the deployed `Valid-Until` (check it in the live `dists/*/InRelease`), even without a new release; a reminder scheduled task fires for the first one (2026-12-11, expiry 2026-12-18).

Tested 2026-11-18: an empty repository signed with the real subkey passes the client test against the live Pages URL; a `Release` signed with an expiry in the past is refused (`is expired`).
