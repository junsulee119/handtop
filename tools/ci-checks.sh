#!/bin/bash
# Checks that need no hardware, no root and no image build. Run by CI on every push
# and pull request (.github/workflows/ci.yml); run it locally before a PR the same way:
#   tools/ci-checks.sh
# Needs: bash, dash, shellcheck, python3 with pytest, git. What each check is for:
# docs/ci.md.
set -uo pipefail
source "$(dirname "$(realpath "$0")")/../build/config.sh"   # TOP, WORK, safe_rm
cd "$TOP" || exit 2
T="$WORK/ci-checks"                 # scratch space, inside work/ like every build output
[ -e "$T" ] && safe_rm -r "$T"
mkdir -p "$T"
fail=0
step() { echo; echo "== $*"; }
bad() { echo "FAIL: $*"; fail=1; }

# Every tracked file, NUL-safe (paths may contain spaces).
mapfile -d '' FILES < <(git ls-files -z)

# ---- shell scripts: by shebang, plus *.sh and files with a "shellcheck shell=" directive
SH=() BASH_=()
for f in "${FILES[@]}"; do
  [ -f "$f" ] && grep -Iq . "$f" || continue      # skip binaries (icons, images)
  first="$(head -n1 "$f")"
  case "$first" in
    '#!/bin/sh'*|'#!/usr/bin/env sh'*) SH+=("$f"); continue ;;
    '#!/bin/bash'*|'#!/usr/bin/env bash'*) BASH_+=("$f"); continue ;;
  esac
  if head -n5 "$f" | grep -q '^# shellcheck shell=sh'; then SH+=("$f")
  elif head -n5 "$f" | grep -q '^# shellcheck shell=bash' || [[ "$f" == *.sh ]]; then BASH_+=("$f")
  fi
done

step "dash -n (${#SH[@]} /bin/sh scripts: they run under dash on the device)"
for f in "${SH[@]}"; do dash -n "$f" || bad "dash -n $f"; done
step "bash -n (${#BASH_[@]} bash scripts)"
for f in "${BASH_[@]}"; do bash -n "$f" || bad "bash -n $f"; done
step "shellcheck, warnings and errors"
shellcheck -S warning "${SH[@]}" "${BASH_[@]}" || bad "shellcheck found warnings or errors"

# ---- Python: *.py plus scripts with a python shebang
PY=()
for f in "${FILES[@]}"; do
  [ -f "$f" ] || continue
  if [[ "$f" == *.py ]] || head -n1 "$f" | grep -qE '^#!.*python'; then PY+=("$f"); fi
done
step "py_compile (${#PY[@]} Python files)"
for f in "${PY[@]}"; do
  PYTHONPYCACHEPREFIX="$T/pycache" python3 -c 'import py_compile, sys; py_compile.compile(sys.argv[1], doraise=True)' "$f" \
    || bad "py_compile $f"
done

# ---- input daemon unit tests, both ways: pytest, and the direct run the image build uses
# (build/08-input.sh). Both must run the same number of tests (audit 2026-10-30, L01).
step "input daemon tests"
(cd src/inputd && python3 -m pytest -q tests) || bad "pytest (input daemon)"
python3 -m pytest -q tests || bad "pytest (tests/: External Controller services)"

# ---- theme system: contract, import / export, renderer (src/theme). Image work needs GdkPixbuf:
# test_gdk.py runs with the system Python where python3-gi + gir1.2-gdkpixbuf-2.0 are installed
# (CI installs them), and is skipped otherwise.
step "theme tests"
python3 -m pytest -q -p no:cacheprovider src/theme/tests || bad "pytest (src/theme)"
if /usr/bin/python3 -c 'import gi; gi.require_version("GdkPixbuf", "2.0"); import pytest' 2>/dev/null; then
  /usr/bin/python3 -m pytest -q -p no:cacheprovider src/theme/tests/test_gdk.py || bad "pytest (src/theme, GdkPixbuf)"
else
  echo "GdkPixbuf or pytest missing for /usr/bin/python3: image tests skipped"
fi
direct="$(PYTHONDONTWRITEBYTECODE=1 python3 src/inputd/tests/test_core.py)" || bad "direct test run"
echo "$direct" | tail -n1
n_direct="$(echo "$direct" | tail -n1 | sed -n 's#^[0-9]*/\([0-9]*\) passed$#\1#p')"
n_pytest="$(cd src/inputd && python3 -m pytest -q --collect-only tests/test_core.py 2>/dev/null | grep -c '::')"
[ -n "$n_direct" ] && [ "$n_direct" = "$n_pytest" ] \
  || bad "the build's direct run of test_core.py has ${n_direct:-?} tests, pytest finds $n_pytest there"

# ---- Wi-Fi import, from a copy whose path has a space (audit 2026-10-30, L03)
step "Wi-Fi import test (path with a space)"
copy="$T/with space/handtop"
mkdir -p "$copy"
git ls-files -z | tar --null -T - -cf - | tar -C "$copy" -xf -
bash "$copy/tools/test-wifi-import.sh" || bad "tools/test-wifi-import.sh"
safe_rm -r "$T"

echo
if [ "$fail" = 0 ]; then echo "All checks passed."; else echo "Some checks FAILED (see above)."; fi
exit "$fail"
