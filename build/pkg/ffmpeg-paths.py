"""Remove build sysroot prefixes from FFmpeg's .pc flags and check the resulting .debs."""

import argparse
import os
from pathlib import Path
import re
import shlex
import subprocess
import tarfile
import tempfile

FLAG_FIELD = re.compile(r"^((?:Libs|Cflags)(?:\.private)?:)([^\n]*)", re.M)
SEARCH_FLAGS = ("-L", "-I")


def rewrite_pc(path, root):
    def rewrite_flags(match):
        field, value = match.groups()
        flags = shlex.split(value)
        rewritten = flags.copy()
        for i, token in enumerate(flags):
            if i and flags[i - 1] in SEARCH_FLAGS:
                option, directory = "", token
            elif token.startswith(SEARCH_FLAGS):
                option, directory = token[:2], token[2:]
            else:
                continue
            if directory == root or directory.startswith(root + "/"):
                rewritten[i] = option + (directory[len(root):] or "/")
        return field + " " + shlex.join(rewritten) if rewritten != flags else match[0]

    text = path.read_text(encoding="utf-8")
    rewritten = FLAG_FIELD.sub(rewrite_flags, text)
    if rewritten != text:
        path.write_text(rewritten, encoding="utf-8")


def check_deb(path, root):
    # Match the root or a path inside it. A sibling such as rootfs-sdk can be a target path.
    root_path = re.compile(re.escape(os.fsencode(root)) + rb"""(?=$|[/\s\x00"'=:;,)\]}])""")
    for option in ("--fsys-tarfile", "--ctrl-tarfile"):
        # Wait for dpkg-deb to finish before inspecting the tar so late decompression errors
        # propagate and an early match can't cause a broken pipe.
        with tempfile.TemporaryFile() as payload:
            subprocess.run(["dpkg-deb", option, path], stdout=payload, check=True, timeout=300)
            payload.seek(0)
            with tarfile.open(fileobj=payload, mode="r:") as archive:
                for member in archive:
                    metadata = (member.name, member.linkname, *member.pax_headers.values())
                    leaked = any(root_path.search(os.fsencode(value)) for value in metadata)
                    if not leaked and member.isfile():
                        with archive.extractfile(member) as content:
                            leaked = root_path.search(content.read())
                    if leaked:
                        raise ValueError(f"{option} {member.name} contains the build root path ({root})")

                # tarfile can stop on an invalid header after the first member. Require the
                # two zero blocks that terminate the tar streams produced by dpkg-deb.
                payload.seek(archive.offset)
                end_marker = bytes(2 * tarfile.BLOCKSIZE)
                if payload.read(len(end_marker)) != end_marker:
                    raise tarfile.ReadError(f"{option}: missing end-of-archive blocks")


def main():
    actions = {"rewrite-pc": rewrite_pc, "check-debs": check_deb}
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=actions)
    parser.add_argument("rootfs")
    parser.add_argument("paths", nargs="+", type=Path)
    args = parser.parse_args()

    root = args.rootfs.rstrip("/")
    if not root.startswith("/"):
        parser.error("rootfs must be an absolute directory below /")
    for path in args.paths:
        try:
            actions[args.action](path, root)
        except (OSError, ValueError, tarfile.TarError, subprocess.SubprocessError) as exc:
            raise SystemExit(f"{path}: {exc}") from None


if __name__ == "__main__":
    main()
