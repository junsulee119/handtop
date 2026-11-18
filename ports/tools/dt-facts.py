#!/usr/bin/env python3
"""Summarise what H700 device trees and panel firmware say about each model.

Used to write the evidence pages in ports/evidence/. Reads files, writes JSON to stdout; touches
no hardware and runs on any build host.

    dtc must be installed (device-tree-compiler).
    python3 ports/tools/dt-facts.py <device_trees dir> <panels dir> > facts.json

<device_trees dir>: the .dtb files from the ROCKNIX image (build step 02 puts them in
work/rocknix/boot/device_trees/). <panels dir>: ROCKNIX's panel firmware (work/rocknix/firmware/panels/).
"""
import glob
import json
import os
import re
import struct
import subprocess
import sys


def decompile(path):
    return subprocess.run(["dtc", "-q", "-I", "dtb", "-O", "dts", path],
                          check=True, capture_output=True, text=True, timeout=60).stdout


def parse(text):
    """{node path: {property: raw value or True}}; good enough for dtc's own output."""
    nodes, stack = {}, []
    for raw in text.splitlines():
        line = raw.strip()
        m = re.match(r"^(?:[\w-]+:\s*)?([\w@,.+-]+|/)\s*\{$", line)
        if m:
            stack.append(m.group(1))
            nodes["/".join(stack).replace("//", "/")] = {}
            continue
        if line == "};":
            stack.pop()
            continue
        m = re.match(r"^([\w,#.+-]+)(?:\s*=\s*(.*))?;$", line)
        if m and stack:
            nodes["/".join(stack).replace("//", "/")][m.group(1)] = m.group(2) if m.group(2) is not None else True
    return nodes


def strings(v):
    return [s for s in str(v).strip('"').split('\\0') if s] if v else []


def cells(v):
    return [int(x, 16) for x in re.findall(r"0x[0-9a-f]+", str(v))] if v else []


def panel_modes(path):
    """Panel firmware for ROCKNIX's panel-mipi-dpi-spi driver: size in mm and display modes."""
    b = open(path, "rb").read()
    if not b.startswith(b"PANEL-FIRMWARE"):
        return None
    w_mm, h_mm = struct.unpack(">HH", b[0x10:0x14])
    count = struct.unpack(">H", b[0x3e:0x40])[0]
    modes = []
    for i in range(count):
        o = 0x40 + 32 * i
        f = struct.unpack(">8H", b[o:o + 16])
        modes.append({"width": f[0], "height": f[4], "clock_khz": struct.unpack(">I", b[o + 16:o + 20])[0]})
    return {"size_mm": [w_mm, h_mm], "modes": modes}


def facts(nodes, panels):
    root = nodes.get("/", {})
    r = {"model": strings(root.get("model"))[0] if root.get("model") else None,
         "compatible": strings(root.get("compatible")),
         "dt_id": strings(root.get("rocknix-dt-id"))[0] if root.get("rocknix-dt-id") else None}
    joy = [p for p in nodes if "joypad" in str(nodes[p].get("compatible", ""))]
    if joy:
        j = nodes[joy[0]]
        r["joypad"] = {
            "driver": strings(j.get("compatible"))[0],
            "name": strings(j.get("joypad-name"))[0] if j.get("joypad-name") else None,
            "stick_axes": (cells(j.get("amux-count")) or [0])[0],
            "inverted": sorted(k[len("invert-"):] for k in j if k.startswith("invert-")),
            "motor_pwm_channel": cells(j.get("pwms"))[1] if len(cells(j.get("pwms"))) > 1 else None,
            "button_codes": sorted(cells(nodes[p]["linux,code"])[0] for p in nodes
                                   if p.startswith(joy[0] + "/") and "linux,code" in nodes[p]),
        }
    r["keys"] = []
    for p in nodes:
        if strings(nodes[p].get("compatible")) [:1] == ["gpio-keys"]:
            for c in nodes:
                if c.startswith(p + "/") and "linux,code" in nodes[c]:
                    r["keys"].append({"group": os.path.basename(p), "label": strings(nodes[c].get("label"))[0],
                                      "code": cells(nodes[c]["linux,code"])[0],
                                      "type": (cells(nodes[c].get("linux,input-type")) or [1])[0]})
    r["leds"] = []
    for p in nodes:
        if strings(nodes[p].get("compatible"))[:1] == ["gpio-leds"]:
            for c in nodes:
                if c.startswith(p + "/") and c.count("/") == p.count("/") + 1:
                    r["leds"].append(strings(nodes[c].get("function"))[0] if nodes[c].get("function") else os.path.basename(c))
    panel = [p for p in nodes if os.path.basename(p).startswith("panel") and nodes[p].get("compatible")]
    if panel:
        comp = strings(nodes[panel[0]]["compatible"])
        r["panel"] = {"compatible": comp, "rotation": (cells(nodes[panel[0]].get("rotation")) or [0])[0],
                      "firmware": panels.get(comp[0])}
    def okay(p):
        return str(nodes[p].get("status", '"okay"')).strip('"') == "okay"
    r["wifi"] = any(os.path.basename(p).startswith("wifi@") for p in nodes)
    r["bluetooth"] = [strings(nodes[p].get("compatible")) for p in nodes if os.path.basename(p) == "bluetooth"]
    r["hdmi"] = any(os.path.basename(p).startswith("hdmi@") and okay(p) for p in nodes)
    r["usb_controllers"] = sorted(os.path.basename(p) for p in nodes
                                  if re.match(r"usb@", os.path.basename(p)) and okay(p))
    r["otg"] = [str(nodes[p].get("dr_mode")).strip('"') for p in nodes if nodes[p].get("dr_mode")]
    r["rtc"] = sorted(strings(nodes[p].get("compatible"))[0] for p in nodes
                      if "rtc@" in os.path.basename(p) and nodes[p].get("compatible"))
    r["uarts_enabled"] = sorted(os.path.basename(p) for p in nodes
                                if os.path.basename(p).startswith("serial@") and okay(p))
    return r


def main():
    dtb_dir, panel_dir = sys.argv[1], sys.argv[2]
    panels = {os.path.basename(p)[:-len(".panel")]: panel_modes(p)
              for p in sorted(glob.glob(os.path.join(panel_dir, "*.panel")))}
    out = {}
    for path in sorted(glob.glob(os.path.join(dtb_dir, "*.dtb"))):
        out[os.path.basename(path)[:-len(".dtb")]] = facts(parse(decompile(path)), panels)
    json.dump(out, sys.stdout, indent=1, sort_keys=True)
    print()


if __name__ == "__main__":
    main()
