"""Build host fixtures for the FFmpeg input record and package paths."""

from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys

import pytest

TOP = Path(__file__).resolve().parents[3]
PATHS = TOP / "build/pkg/ffmpeg-paths.py"
RECORD = Path("build/pkg/ffmpeg-inputs.txt")
CONFIG = Path("build/config.sh")
DEBIAN_VERSION = "7:7.1.5-0+deb13u1"
SYSROOT = "/build/handtop/rootfs"


def run(*args, check=True):
    return subprocess.run(args, capture_output=True, text=True, check=check, timeout=30)


def set_pin(repo, name, value):
    config = repo / CONFIG
    text, count = re.subn(f"^{name}=.*$", f"{name}={value}", config.read_text(), flags=re.M)
    assert count == 1
    config.write_text(text)


@pytest.fixture
def input_repo(tmp_path):
    for path in (
        CONFIG, "build/lib/safety.sh", "build/04c-v4l2-ffmpeg.sh",
        "build/patches/ffmpeg-v4l2request-drm.patch", "build/pkg/build-ffmpeg-debs.py",
        "build/pkg/ffmpeg-paths.py", "tools/ffmpeg-inputs.sh",
    ):
        dst = tmp_path / path
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(TOP / path, dst)
    set_pin(tmp_path, "FFMPEG_DEBIAN_VERSION", DEBIAN_VERSION)
    set_pin(tmp_path, "FFMPEG_HANDTOP_REV", 1)
    (tmp_path / RECORD).write_text(f"{DEBIAN_VERSION}+handtop1 {'0' * 64}\n")
    return tmp_path


def test_input_history(input_repo):
    record = input_repo / RECORD
    released = record.read_bytes()
    guard = ("bash", input_repo / "tools/ffmpeg-inputs.sh")
    assert "already recorded" in run(*guard, "--update", check=False).stderr
    assert record.read_bytes() == released

    script = input_repo / "build/pkg/build-ffmpeg-debs.py"
    script.write_text(script.read_text() + '\nfixture = """\n# original\n"""\n')
    set_pin(input_repo, "FFMPEG_HANDTOP_REV", 9)
    assert run(*guard, check=False).returncode == 1  # newer needs a record
    run(*guard, "--update")
    run(*guard)
    rev9 = record.read_bytes()
    assert rev9.startswith(released)
    assert len(rev9.splitlines()) == 2
    run(*guard, "--update")
    assert record.read_bytes() == rev9

    # A line beginning with # contributes bytes inside a multiline string.
    script.write_text(script.read_text().replace("# original", "# changed"))
    assert "already recorded" in run(*guard, check=False).stderr
    assert "already recorded" in run(*guard, "--update", check=False).stderr
    assert record.read_bytes() == rev9

    set_pin(input_repo, "FFMPEG_HANDTOP_REV", 10)
    run(*guard, "--update")
    run(*guard)
    rev10 = record.read_bytes()
    assert rev10.startswith(rev9)
    assert rev10.splitlines()[-1].startswith(f"{DEBIAN_VERSION}+handtop10 ".encode())
    set_pin(input_repo, "FFMPEG_HANDTOP_REV", 9)
    assert "older than" in run(*guard, "--update", check=False).stderr
    assert record.read_bytes() == rev10

    set_pin(input_repo, "FFMPEG_DEBIAN_VERSION", "7:7.1.5-0+deb13u2")
    set_pin(input_repo, "FFMPEG_HANDTOP_REV", 1)
    run(*guard, "--update")
    run(*guard)
    new_debian = record.read_bytes()
    assert new_debian.startswith(rev10)
    set_pin(input_repo, "FFMPEG_DEBIAN_VERSION", DEBIAN_VERSION)
    set_pin(input_repo, "FFMPEG_HANDTOP_REV", 11)
    assert "older than" in run(*guard, "--update", check=False).stderr
    assert record.read_bytes() == new_debian


@pytest.mark.parametrize("pin,value", [
    ("FFMPEG_VERSION", "7.1.6"), ("KWIBOO_URL", "https://example.invalid/ffmpeg"), ("KWIBOO_COMMITS", 15),
])
def test_buildinfo_pins_affect_input_hash(input_repo, pin, value):
    guard = ("bash", input_repo / "tools/ffmpeg-inputs.sh")
    set_pin(input_repo, "FFMPEG_HANDTOP_REV", 2)
    run(*guard, "--update")
    recorded = (input_repo / RECORD).read_bytes()
    set_pin(input_repo, pin, value)
    assert "already recorded" in run(*guard, "--update", check=False).stderr
    assert (input_repo / RECORD).read_bytes() == recorded


def test_pc_rewrite_preserves_target_search_paths(tmp_path):
    root = "/build dir/rootfs"
    escaped_root = root.replace(" ", r"\ ")
    pc = tmp_path / "fixture.pc"
    pc.write_text(
        "libdir=/usr/lib\n"
        "Libs: -L${libdir} -lfixture\n"
        f'Libs.private: -L"{root}/opt/vendor lib" -L "{root}/lib" -L"{root}-sdk/lib"\n'
        f'Cflags: -I{escaped_root}/opt/include "-I{root}/usr/include" -I"{root}" '
        f'-DMESSAGE="-I{root}/other" -I/target/include\n'
    )
    run(sys.executable, PATHS, "rewrite-pc", root, pc)
    libdir, libs, private, cflags = pc.read_text().splitlines()
    assert libdir == "libdir=/usr/lib"
    assert libs == "Libs: -L${libdir} -lfixture"
    assert shlex.split(private) == [
        "Libs.private:", "-L/opt/vendor lib", "-L", "/lib", f"-L{root}-sdk/lib",
    ]
    assert shlex.split(cflags) == [
        "Cflags:", "-I/opt/include", "-I/usr/include", "-I/",
        f"-DMESSAGE=-I{root}/other", "-I/target/include",
    ]


@pytest.fixture
def deb_tree(tmp_path):
    tree = tmp_path / "tree"
    (tree / "DEBIAN").mkdir(parents=True)
    (tree / "DEBIAN/control").write_text(
        "Package: ffmpeg-fixture\nVersion: 1\nArchitecture: all\n"
        "Maintainer: Handtop <example@example.invalid>\nDescription: FFmpeg path check fixture\n"
    )
    return tree


def make_deb(tree, *options):
    deb = tree.parent / "fixture.deb"
    run("dpkg-deb", "--root-owner-group", *options, "--build", tree, deb)
    return deb


def scan(deb, *, check=True):
    return run(sys.executable, PATHS, "check-debs", SYSROOT, deb, check=check)


def test_scan_reports_an_early_match(deb_tree):
    (deb_tree / "00-first").write_bytes(b"\x7fELF\x00" + f"--sysroot={SYSROOT}/usr".encode() + b"\x00")
    (deb_tree / "99-last").write_bytes(b"\0" * (2 * 1024 * 1024))
    result = scan(make_deb(deb_tree), check=False)
    assert result.returncode == 1
    assert "00-first contains the build root path" in result.stderr


def test_scan_keeps_archive_members_separate(deb_tree):
    parent, leaf = SYSROOT.rsplit("/", 1)
    (deb_tree / "first").write_text(parent + "/")
    (deb_tree / "second").write_text(leaf)
    (deb_tree / "third").write_text(f"-L{SYSROOT}-sdk/lib")
    scan(make_deb(deb_tree))


@pytest.mark.parametrize("where", ["link", "control"])
def test_scan_checks_links_and_control(deb_tree, where):
    if where == "link":
        (deb_tree / "link").symlink_to(f"{SYSROOT}/usr/lib/libavutil.so")
    else:
        with (deb_tree / "DEBIAN/control").open("a") as control:
            control.write(f" Path: {SYSROOT}\n")
    result = scan(make_deb(deb_tree), check=False)
    assert result.returncode == 1
    assert f"{where} contains the build root path" in result.stderr


def test_scan_rejects_dpkg_read_error(tmp_path):
    deb = tmp_path / "broken.deb"
    deb.write_bytes(b"not a Debian archive")
    result = scan(deb, check=False)
    assert result.returncode == 1
    assert "dpkg-deb" in result.stderr
    assert "returned non-zero" in result.stderr


def test_scan_rejects_invalid_tar_header(deb_tree):
    deb = make_deb(deb_tree, "-Znone")
    data = bytearray(deb.read_bytes())
    # An ar member has a 60-byte header. Keep the first tar header and corrupt the second.
    start = data.index(b"data.tar        ") + 60
    assert data[start:start + 2] == b"./"
    data[start + 512] ^= 1
    deb.write_bytes(data)
    result = scan(deb, check=False)
    assert result.returncode == 1
    assert "missing end-of-archive blocks" in result.stderr
