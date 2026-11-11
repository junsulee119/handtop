"""Pack the downloadable themes (src/theme/extra/<id>/) as <id>.handtop-theme files, checked the
way the Theme app checks an import (GdkPixbuf and fontconfig where installed).

Usage: python3 tools/themes/pack-extra-themes.py <output folder>
The files are release assets, not part of the image."""
import os
import sys
import tempfile

TOP = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(TOP, "src", "theme"))
from handtop_theme import builtin, imgops, package  # noqa: E402
from handtop_theme import theme as T  # noqa: E402


def main(out):
    os.makedirs(out, exist_ok=True)
    extra = os.path.join(TOP, "src", "theme", "extra")
    with tempfile.TemporaryDirectory() as bdir:
        builtin.assemble(TOP, bdir)
        bad = 0
        for tid in sorted(os.listdir(extra)):
            path = os.path.join(extra, tid)
            if not os.path.isfile(os.path.join(path, "theme.json")):
                continue
            t = T.load(path, bdir, decode=imgops.available())
            for p in t.problems:
                print(f"{tid}: {p}")
            if t.errors:
                bad = 1
                continue
            dest = package.export_theme(path, os.path.join(out, f"handtop-{tid}.handtop-theme"), bdir)
            # the packed file must import cleanly
            with tempfile.TemporaryDirectory() as udir:
                package.import_theme(dest, udir, bdir, decode=imgops.available())
            print(f"{dest}  {os.path.getsize(dest) // 1024} KB")
    return bad


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__.split("\n\n")[1])
    sys.exit(main(sys.argv[1]))
