#!/usr/bin/env python3
"""Find how Anbernic's stock U-Boot picks between two screen panels (read-only analysis).

Anbernic's H700 stock firmware decides the panel in U-Boot, in lcd_panel_uboot_fj035fhd05_v1_init:
it reads a GPIO and stores lcd_type, which selects one of two init sequences. This tool finds that
function in a stock card image and reports which pin it reads, whether it turns on the pull-up,
and how the reading maps to lcd_type. Needs: pip install capstone. Touches no hardware.

    python3 ports/tools/stock-panel-check.py <image or first 64 MiB of it> [...]

Only the first 17 MiB of the image are needed (boot0 + the U-Boot package at 16400 KiB). The stock
images ship as .IMG.7z; extract the start of the .IMG (for example with py7zr) and pass that file.
"""
import re
import struct
import sys

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


def analyse(path):
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
    return result


if __name__ == "__main__":
    for p in sys.argv[1:]:
        r = analyse(p)
        if r["reads"]:
            for x in r["reads"]:
                print("%s: %s, pull-up %s, lcd_type = 1 when %s (function at u-boot %s)"
                      % (p, x["pin"], "set" if x["pull_up_set"] else "not set", x["lcd_type_1_when"], r["function"]))
        else:
            print("%s: no panel pin read: one panel only (function at u-boot %s)" % (p, r["function"]))
