#!/bin/bash
# Removes the RAM copy left by key-ceremony.sh (primary key and backup). Only touches /dev/shm/handtop-key.*.
set -euo pipefail
T="${1:?usage: key-ceremony-wipe.sh /dev/shm/handtop-key.XXXXXX}"
case "$T" in /dev/shm/handtop-key.??????) ;; *) echo "refusing: $T" >&2; exit 1 ;; esac
GNUPGHOME="$T/gnupg" gpgconf --kill gpg-agent 2>/dev/null || true
find "$T" -type f -exec shred -u {} +
rm -rf "$T"
echo "wiped $T"
