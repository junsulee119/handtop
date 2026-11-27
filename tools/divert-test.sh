#!/bin/bash
# Diversions of Debian's config files (build/pkg/diversions.txt, review 2026-11-19 #8): the preinst and
# postrm that build/pkg/build-debs.py writes, tried with two small packages (a "Debian owner" and a
# "Handtop" package diverting its config file) through install, Debian update, upgrade, remove,
# reinstall, purge, a card whose file was already Handtop's, and aborted installs.
#   tools/divert-test.sh ROOTFS   (root; ROOTFS a throwaway copy with dpkg, e.g. update-test's)
set -euo pipefail
TOP=$(cd "$(dirname "$(realpath "$0")")/.." && pwd)
ROOT=$(realpath "${1:?usage: divert-test.sh ROOTFS}")
[ "$ROOT" != / ] && [ -x "$ROOT/usr/bin/dpkg" ] || { echo "divert-test: $ROOT is not a scratch root with dpkg" >&2; exit 2; }
W="$ROOT/tmp/divert-test"; mkdir -p "$W/new"
python3 - "$TOP/build/pkg" "$W/new" <<'PY'
import sys, importlib.util as u
sys.path.insert(0, sys.argv[1])
s = u.spec_from_file_location("bd", sys.argv[1] + "/build-debs.py"); m = u.module_from_spec(s); s.loader.exec_module(m)
m.audit.diversions = lambda: {"/etc/dt/a.conf": "dt-handtop"}
m.audit.diversion_owners = lambda: {"/etc/dt/a.conf": "dt-owner"}
o = m.maintainer_scripts("dt-handtop", [], {})
for k in ("preinst", "postrm"):
    open(sys.argv[2] + "/" + k, "w").write(o[k])
PY
cat > "$W/t.sh" <<'T'
#!/bin/bash
export DEBIAN_FRONTEND=noninteractive LC_ALL=C
cd /tmp/divert-test
pass=0; fail=0
ok() { echo "PASS: $*"; pass=$((pass+1)); }; bad() { echo "FAIL: $*"; fail=$((fail+1)); }
chk() { if eval "$2"; then ok "$1"; else bad "$1 [$(ls /etc/dt 2>/dev/null | xargs); a.conf=$(cat /etc/dt/a.conf 2>/dev/null); div=$(dpkg-divert --list /etc/dt/a.conf)]"; fi; }
mk() { d=b/$1-$2; mkdir -p $d/DEBIAN $d/etc/dt; echo "$3" > $d/etc/dt/a.conf; echo /etc/dt/a.conf > $d/DEBIAN/conffiles
  printf 'Package: %s\nVersion: %s\nArchitecture: all\nMaintainer: t <t@t>\nDescription: t\n' $1 $2 > $d/DEBIAN/control
  [ "$1" = dt-handtop ] && cp new/preinst new/postrm $d/DEBIAN/ && chmod 755 $d/DEBIAN/preinst $d/DEBIAN/postrm
  dpkg-deb --root-owner-group -b $d $d.deb >/dev/null; }
D() { dpkg --force-confdef --force-confold "$@" </dev/null >/tmp/dt.out 2>&1; }
dt_status() { dpkg-query -W -f='${db:Status-Status}' dt-handtop 2>/dev/null; }
reset() { D -P dt-handtop; D -P dt-owner; dpkg-divert --list | grep -q dt-handtop && dpkg-divert --package dt-handtop --no-rename --remove /etc/dt/a.conf >/dev/null; rm -f /etc/dt/a.conf*; }
c() { [ "$(cat /etc/dt/a.conf 2>/dev/null)" = "$1" ]; }; cd_() { [ "$(cat /etc/dt/a.conf.debian 2>/dev/null)" = "$1" ]; }
mk dt-owner 1 debian1; mk dt-owner 2 debian2; mk dt-handtop 1 handtop1; mk dt-handtop 2 handtop2
reset
echo "== S1 fresh install over Debian's untouched file"
D -i b/dt-owner-1.deb; D -i b/dt-handtop-1.deb
chk "installed: ours in place, Debian's saved" 'c handtop1 && cd_ debian1'
D -i b/dt-owner-2.deb
chk "Debian update goes to .debian, ours untouched" 'c handtop1 && cd_ debian2 && [ ! -e /etc/dt/a.conf.debian.dpkg-dist ]'
D -i b/dt-handtop-2.deb
chk "Handtop upgrade" 'c handtop2 && cd_ debian2'
D -r dt-handtop
chk "remove: config kept, diversion kept" 'c handtop2 && cd_ debian2 && dpkg-divert --listpackage /etc/dt/a.conf | grep -qx dt-handtop'
D -i b/dt-handtop-2.deb
chk "reinstall after remove" 'c handtop2 && cd_ debian2'
D -P dt-handtop; cat /tmp/dt.out | grep dt-handtop: ; 
chk "purge: Debian's back, no diversion" 'c debian2 && [ ! -e /etc/dt/a.conf.debian ] && [ -z "$(dpkg-divert --list /etc/dt/a.conf)" ]'
chk "dpkg --verify dt-owner clean" '[ -z "$(dpkg --verify dt-owner)" ]'
D -i b/dt-owner-2.deb
chk "Debian reinstall afterwards fine" 'c debian2'
reset
echo "== S2 the user had edited Debian's file before"
D -i b/dt-owner-1.deb; echo "user" >> /etc/dt/a.conf; D -i b/dt-handtop-1.deb
chk "user's edit kept in place, no .debian saved" '[ "$(tail -1 /etc/dt/a.conf)" = user ] && [ ! -e /etc/dt/a.conf.debian ] && [ -f /etc/dt/a.conf.dpkg-dist ]'
D -P dt-handtop
chk "purge: gone like any purged config file, hint printed" '[ ! -e /etc/dt/a.conf ] && grep -q force-confmiss /tmp/dt.out && [ -z "$(dpkg-divert --list /etc/dt/a.conf)" ]'
reset
echo "== S3 card where the file was already Handtop's (v0.4.x migration)"
D -i b/dt-owner-1.deb; echo handtop1 > /etc/dt/a.conf; D -i b/dt-handtop-1.deb
chk "installed, no .debian" 'c handtop1 && [ ! -e /etc/dt/a.conf.debian ]'
D -i b/dt-owner-2.deb
chk "Debian update arrives as .debian.dpkg-dist" '[ "$(cat /etc/dt/a.conf.debian.dpkg-dist)" = debian2 ] && c handtop1'
D -i b/dt-handtop-2.deb
chk "next Handtop version adopts it as .debian" 'cd_ debian2 && [ ! -e /etc/dt/a.conf.debian.dpkg-dist ] && c handtop2'
D -P dt-handtop
chk "purge: Debian's back" 'c debian2 && [ -z "$(dpkg-divert --list /etc/dt/a.conf)" ] && [ -z "$(dpkg --verify dt-owner)" ]'
reset
echo "== S4 purge with no Debian copy at all"
D -i b/dt-owner-1.deb; echo handtop1 > /etc/dt/a.conf; D -i b/dt-handtop-1.deb; D -P dt-handtop
chk "purge prints the --force-confmiss hint" 'grep -q "force-confmiss dt-owner" /tmp/dt.out && [ -z "$(dpkg-divert --list /etc/dt/a.conf)" ]'
reset
echo "== S5 install aborted after preinst (unpack fails)"
D -i b/dt-owner-1.deb
mkdir -p b/dt-handtop-3/DEBIAN; cp -r b/dt-handtop-1/* b/dt-handtop-3/; sed -i 's/^Version: 1/Version: 3/' b/dt-handtop-3/DEBIAN/control
mkdir -p b/dt-handtop-3/usr/share/dt; echo x > b/dt-handtop-3/usr/share/dt/clash; dpkg-deb -b b/dt-handtop-3 b/dt-handtop-3.deb >/dev/null
mkdir -p b/dt-other/DEBIAN b/dt-other/usr/share/dt; echo y > b/dt-other/usr/share/dt/clash
printf 'Package: dt-other\nVersion: 1\nArchitecture: all\nMaintainer: t <t@t>\nDescription: t\n' > b/dt-other/DEBIAN/control; dpkg-deb -b b/dt-other b/dt-other.deb >/dev/null
D -i b/dt-other.deb
chk "first install fails in unpack and calls abort-install" \
  '! D -D2 -i b/dt-handtop-3.deb && grep -Fq "trying to overwrite" /tmp/dt.out &&
   grep -Fq "postrm ( abort-install )" /tmp/dt.out'
chk "aborted: Debian's file in place, no diversion, no copy" \
  'c debian1 && [ ! -e /etc/dt/a.conf.debian ] && [ -z "$(dpkg-divert --list /etc/dt/a.conf)" ] &&
   [ "$(dt_status || echo not-installed)" = not-installed ]'
reset
echo "== S6 reinstall aborted after remove (unpack fails)"
D -i b/dt-owner-1.deb && D -i b/dt-handtop-2.deb && D -r dt-handtop || { cat /tmp/dt.out; exit 1; }
chk "reinstall fails in unpack and calls abort-install with both versions" \
  '! D -D2 -i b/dt-handtop-3.deb && grep -Fq "trying to overwrite" /tmp/dt.out &&
   grep -Fq "postrm ( abort-install 2 3 )" /tmp/dt.out'
chk "aborted reinstall: config-files state and diversion kept" \
  '[ "$(dt_status)" = config-files ] && [ "$(dpkg-divert --listpackage /etc/dt/a.conf)" = dt-handtop ] &&
   [ "$(dpkg-divert --truename /etc/dt/a.conf)" = /etc/dt/a.conf.debian ]'
chk "aborted reinstall: live and saved configs unchanged" \
  'cmp -s /etc/dt/a.conf b/dt-handtop-2/etc/dt/a.conf &&
   cmp -s /etc/dt/a.conf.debian b/dt-owner-1/etc/dt/a.conf'
chk "purge after aborted reinstall restores Debian's original" \
  'D -P dt-handtop && cmp -s /etc/dt/a.conf b/dt-owner-1/etc/dt/a.conf &&
   [ ! -e /etc/dt/a.conf.debian ] && [ -z "$(dpkg-divert --list /etc/dt/a.conf)" ]'
D -P dt-other
reset
echo "divert-test: $pass passed, $fail failed"
[ "$fail" = 0 ]
T
chroot "$ROOT" bash /tmp/divert-test/t.sh
