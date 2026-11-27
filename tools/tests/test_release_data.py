import importlib.machinery
import importlib.util
from pathlib import Path
import shutil
import subprocess
import sys
from types import SimpleNamespace

import pytest


TOP = Path(__file__).resolve().parents[2]
KERNEL = "9.8.7"
KERNEL_SHA = "a" * 64
ABI = f"platform=h700\nkernel={KERNEL}\nkernel_sha256={KERNEL_SHA}\n"
REL = "v0.4.1"
MODULES = f"/usr/lib/modules/{KERNEL}/"
USB = MODULES + "extra/usb_f_fs_xinput.ko"
USB_SHA = "b" * 64
VP9 = MODULES + "kernel/drivers/media/v4l2-core/v4l2-vp9.ko"
DDR4_ONLY = MODULES + "extra/ddr4-only.ko"
LINK = "/usr/local/bin/handtop-link"
FFMPEG_LINK = "/usr/lib/aarch64-linux-gnu/libavcodec.so"


@pytest.fixture
def release_table(tmp_path):
    checkout = tmp_path / "checkout"
    for path in ("tools/release-data.py", "build/pkg/audit-unowned.py",
                 "build/pkg/classes.txt", "build/pkg/diversions.txt"):
        dst = checkout / path
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(TOP / path, dst)
    (checkout / "build/pkg/modules.txt").write_text(
        "# Relative to the kernel directory\n\nextra/usb_f_fs_xinput.ko\n"
        "kernel/drivers/media/v4l2-core/v4l2-vp9.ko # nested path\nextra/ddr4-only.ko\n"
    )
    abi = tmp_path / "boot-abi"
    abi.write_text(ABI)
    out = tmp_path / "releases.tsv"
    args = [sys.executable, str(checkout / "tools/release-data.py"), str(out), str(abi)]
    common = [
        ("/boot/firmware/KERNEL", "f", "664", KERNEL_SHA, "u"),
        (LINK, "l", "777", "handtop-target", "u"),
        (FFMPEG_LINK, "l", "777", "libavcodec.so.61", "u"),
        (MODULES + "extra/unlisted.ko", "f", "644", "c" * 64, "u"),
        (USB.replace(KERNEL, "1.2.3"), "f", "644", "c" * 64, "u"),
    ]
    ddr4 = [(USB, "f", "644", USB_SHA, "u"), (VP9, "f", "644", "c" * 64, "u"),
            (DDR4_ONLY, "f", "644", "d" * 64, "u")]
    ddr3 = [(USB.removeprefix("/usr"), "f", "644", USB_SHA, "o"), (VP9, "f", "644", "e" * 64, "u")]
    for ram, rows in (("DDR4", ddr4), ("DDR3", ddr3)):
        manifest = tmp_path / f"{ram}.tsv"
        manifest.write_text("".join("\t".join(row) + "\n" for row in common + rows))
        args.append(f"{REL}:{ram}={manifest}")
    subprocess.run(args, check=True, timeout=30)
    return out


def test_release_data_merges_module_rows(release_table):
    lines = release_table.read_text().splitlines()[1:]
    assert [tuple(line.split("\t")) for line in lines] == [
        (REL, "*", "@boot-abi", "k", ";".join(ABI.splitlines()), ""),
        (REL, "*", "/boot/firmware/KERNEL", "f", KERNEL_SHA, "664"),
        (REL, "*", FFMPEG_LINK, "x", "l:libavcodec.so.61", ""),
        (REL, "DDR4", DDR4_ONLY, "f", "d" * 64, "644"),
        (REL, "*", USB, "f", USB_SHA, "644"),
        (REL, "DDR3", VP9, "f", "e" * 64, "644"),
        (REL, "DDR4", VP9, "f", "c" * 64, "644"),
        (REL, "*", LINK, "l", "handtop-target", ""),
    ]


@pytest.fixture
def worker(monkeypatch):
    if sys.platform == "win32":
        # The migration decisions below run without taking the worker's Linux file lock.
        monkeypatch.setitem(sys.modules, "fcntl", SimpleNamespace())
    loader = importlib.machinery.SourceFileLoader(
        "handtop_update", str(TOP / "overlay/usr/local/sbin/handtop-update")
    )
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


def test_modules_do_not_affect_card_identification(worker, monkeypatch):
    file = ("f", USB_SHA)
    old, new = "/usr/local/bin/old-tool", "/usr/local/bin/new-tool"
    rootfix = worker.FAT + "/rootfix.cpio"
    data = {"v0.4.0": {old: {"*": file}, USB: {"*": file}},
            REL: {new: {"*": file}, DDR4_ONLY: {"*": file}, rootfix: {"DDR4": file}}}
    card = {new: file, rootfix: file, USB: file}
    monkeypatch.setattr(worker, "card_value", card.get)
    monkeypatch.setattr(worker.os.path, "ismount", lambda path: path == worker.FAT)
    assert worker.identify(data) == (REL, "DDR4", 1.0)
    card[old] = ("f", "f" * 64)
    with pytest.raises(worker.Fail, match="mixes files"):
        worker.identify(data)


def test_adoption_distinguishes_stock_and_changed_modules(release_table, worker, monkeypatch):
    card = {USB: ("f", USB_SHA)}
    package_md5 = "a" * 32
    plan = {"from": {"release": REL},
            "packages": [{"name": f"handtop-modules-h700-{KERNEL}", "file": "modules.deb"}]}
    monkeypatch.setattr(worker, "RELEASES", release_table)
    monkeypatch.setattr(worker, "card_value", card.get)
    monkeypatch.setattr(worker, "deb_control", lambda _: (set(), {USB: package_md5}))
    monkeypatch.setattr(worker, "md5", lambda _: "b" * 32)
    monkeypatch.setattr(worker, "os", SimpleNamespace(path=worker.os.path,
                                                      stat=lambda _: SimpleNamespace(st_mode=0o644)))
    data = worker.release_data()
    stock = worker.adoption(plan, data)
    assert stock["stock"] == [[USB, USB_SHA, package_md5]]
    assert stock["backup"] == []

    edited_sha = "f" * 64
    card[USB] = ("f", edited_sha)
    edited = worker.adoption(plan, data)
    assert edited["stock"] == []
    assert edited["backup"] == [[USB, edited_sha]]
