#!/usr/bin/env python3
"""Find how Anbernic's stock U-Boot picks between two screen panels (read-only analysis).

Anbernic's H700 stock firmware decides the panel in U-Boot, in lcd_panel_uboot_fj035fhd05_v1_init:
it reads a GPIO and stores lcd_type, which selects one of two init sequences. This tool finds that
function in a stock card image and reports which pin it reads, whether it turns on the pull-up,
and how the reading maps to lcd_type. Needs: pip install capstone. Touches no hardware.

    python3 ports/tools/stock-panel-check.py [--panels <dir>] <image or first 64 MiB of it> [...]

With --panels (ROCKNIX's panel firmware, work/rocknix/firmware/panels/), each of the two init
sequences is also compared with ROCKNIX's panel files, which tells which device tree each PE6
level needs.

Only the first 17 MiB of the image are needed (boot0 + the U-Boot package at 16400 KiB). The stock
images ship as .IMG.7z; extract the start of the .IMG (for example with py7zr) and pass that file.
"""
import re
import struct
import sys

import difflib
import glob
import os

import capstone

PACKAGE = 16400 * 1024
LOAD = 0x4A000000          # stock U-Boot load address
PIO = 0x0300B000           # H616 / H700 GPIO block; port n at PIO + 0x24 * n
PORTS = "ABCDEFGHI"


def uboot(data):
    if data[PACKAGE:PACKAGE + 13] != b"sunxi-package":
        raise SystemExit("no sunxi-package at 16400 KiB: not an H700 stock image?")
    count = struct.unpack("<I", data[PACKAGE + 0x20:PACKAGE + 0x24])[0]
    for i in range(count):
        entry = PACKAGE + 0x40 + i * 0x170
        if data[entry:entry + 64].split(b"\0")[0] == b"u-boot":
            off, size = struct.unpack("<II", data[entry + 0x40:entry + 0x48])
            return data[PACKAGE + off:PACKAGE + off + size]
    raise SystemExit("no u-boot in the package")


def word(u, a):
    return struct.unpack("<I", u[a:a + 4])[0]


def literal_refs(u, target):
    """Thumb-2 'ldr rX, [pc, #imm]' instructions that load the word at target."""
    out = []
    for p in range(0, len(u) - 4, 2):
        h = struct.unpack("<H", u[p:p + 2])[0]
        if h >> 11 == 0b01001 and ((p + 4) & ~3) + (h & 0xFF) * 4 == target:
            out.append(p)
        elif h == 0xF8DF and ((p + 4) & ~3) + (struct.unpack("<H", u[p + 2:p + 4])[0] & 0xFFF) == target:
            out.append(p)
    return out


def function(u):
    name = u.find(b"lcd_panel_uboot_fj035fhd05_v1_init\0")
    if name < 0:
        raise SystemExit("panel function not found")
    pools = [i for i in range(0, len(u) - 4, 4) if word(u, i) == LOAD + name]
    for pool in pools:
        refs = literal_refs(u, pool)
        if not refs:
            continue
        start = min(refs)
        while start > min(refs) - 0x2000:
            start -= 2
            h = struct.unpack("<H", u[start:start + 2])[0]
            if (h & 0xFF00) == 0xB500 or (h == 0xE92D and struct.unpack("<H", u[start + 2:start + 4])[0] & 0x4000):
                return start, pool
    raise SystemExit("could not find the function start")


def imm(op):
    m = re.search(r"#(-?0x[0-9a-f]+|-?\d+)$", op)
    return int(m.group(1), 0) if m else None


def walk(u, md, addr, regs):
    """Follow one init path; return its calls as (target, r0) with r0 tracked from mov / movs."""
    calls, regs = [], dict(regs)
    for _ in range(5000):
        got = list(md.disasm(u[addr:addr + 4], addr, 1))
        if not got:
            break
        x = got[0]
        addr = x.address + x.size
        if x.mnemonic in ("movs", "mov", "mov.w", "movw"):
            dst, src = [o.strip() for o in x.op_str.split(",", 1)]
            regs[dst] = imm(x.op_str) if imm(x.op_str) is not None else regs.get(src)
        elif x.mnemonic == "bl":
            calls.append((int(x.op_str.lstrip("#"), 0), regs.pop("r0", None)))
        elif x.mnemonic in ("b", "b.w"):
            addr = int(x.op_str.lstrip("#"), 0)
        elif x.mnemonic.startswith("pop") or x.mnemonic == "bx":
            break
    return calls


def commands(calls):
    """Calls to the command and data writers -> [(cmd, data...), ...]."""
    cmd_fn = calls[0][0]
    counts = {}
    for t, _ in calls:
        counts[t] = counts.get(t, 0) + 1
    data_fn = max((t for t in counts if t != cmd_fn), key=lambda t: counts[t])
    out, cur = [], None
    for t, v in calls:
        if t == cmd_fn:
            if cur:
                out.append(tuple(cur))
            cur = [v]
        elif t == data_fn and cur is not None:
            cur.append(v)
    if cur:
        out.append(tuple(cur))
    return out


def rocknix_panel(path):
    b = open(path, "rb").read()
    o = 0x40 + 32 * struct.unpack(">H", b[0x3e:0x40])[0]
    out = []
    while o < len(b):
        n = b[o]
        o += 1
        if n == 0:           # delay entry
            o += 1
            continue
        out.append(tuple(b[o:o + n]))
        o += n
    return out


def init_paths(u, md, ins):
    """{lcd_type: [(cmd, data...)]} from 'cmp rX, #1; bne other; b one'."""
    for i, x in enumerate(ins[:-2]):
        if x.mnemonic == "cmp" and x.op_str.endswith("#1") and ins[i + 1].mnemonic.startswith("bne"):
            reg = x.op_str.split(",")[0]
            pre = {}
            for y in ins[max(0, i - 6):i]:
                if y.mnemonic in ("movs", "mov") and imm(y.op_str) is not None:
                    pre[y.op_str.split(",")[0]] = imm(y.op_str)
            other = int(ins[i + 1].op_str.lstrip("#"), 0)
            one = int(ins[i + 2].op_str.lstrip("#"), 0)
            return {1: commands(walk(u, md, one, dict(pre, **{reg: 1}))),
                    0: commands(walk(u, md, other, dict(pre, **{reg: 0})))}
    return {}


def analyse(path, panels=None):
    data = open(path, "rb").read(PACKAGE + 0x110000)
    u = uboot(data)
    start, end = function(u)
    md = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB)
    ins = list(md.disasm(u[start:end], start))
    regs = []        # (index, register address)
    for i, x in enumerate(ins):
        if x.mnemonic.startswith("ldr") and "pc" in x.op_str:
            m = re.search(r"#(0x[0-9a-f]+|\d+)\]", x.op_str)
            if m:
                v = word(u, ((x.address + 4) & ~3) + int(m.group(1), 0))
                if PIO <= v < PIO + 0x24 * len(PORTS):
                    regs.append((i, v))
    result = {"function": hex(start), "reads": []}
    for i, addr in regs:
        port, reg = divmod(addr - PIO, 0x24)
        if reg != 0x10:          # only data-register reads decide anything
            continue
        tail = ins[i:i + 8]
        bit = invert = None
        for x in tail:
            m = re.match(r"r\d+, r\d+, #(\d+), #1", x.op_str)
            if x.mnemonic == "ubfx" and m:
                bit = int(m.group(1))
            if x.mnemonic.startswith("eor"):
                invert = True
        if bit is None:
            continue
        pull = any(a == PIO + 0x24 * port + 0x1C for _, a in regs)
        result["reads"].append({
            "pin": "P%s%d" % (PORTS[port], bit),
            "pull_up_set": pull,
            "lcd_type_1_when": "low" if invert else "high",
        })
    if panels:
        result["matches"] = {}
        for lcd_type, cmds in init_paths(u, md, ins).items():
            best = max(((difflib.SequenceMatcher(None, cmds, r, autojunk=False).ratio(), k)
                        for k, r in panels.items()), default=None)
            result["matches"][lcd_type] = best
    return result


if __name__ == "__main__":
    args, panels = sys.argv[1:], None
    if args[:1] == ["--panels"]:
        panels = {os.path.basename(f)[:-len(".panel")]: rocknix_panel(f)
                  for f in sorted(glob.glob(os.path.join(args[1], "*.panel")))}
        args = args[2:]
    for p in args:
        r = analyse(p, panels)
        if r["reads"]:
            for x in r["reads"]:
                print("%s: %s, pull-up %s, lcd_type = 1 when %s (function at u-boot %s)"
                      % (p, x["pin"], "set" if x["pull_up_set"] else "not set", x["lcd_type_1_when"], r["function"]))
        else:
            print("%s: no panel pin read: one panel only (function at u-boot %s)" % (p, r["function"]))
        for lcd_type, best in sorted(r.get("matches", {}).items()):
            if best:
                print("    lcd_type %d init sequence: closest ROCKNIX panel %s (%.2f)" % (lcd_type, best[1], best[0]))
