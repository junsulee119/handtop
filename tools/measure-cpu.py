#!/usr/bin/python3
"""CPU use per process and in total over a time window, for battery work (the battery's
current_now is useless on this unit: it reads a fixed 400 mA). Reads only /proc and sysfs.

  measure-cpu.py [seconds] [label]      (default 60 s; run as root to see every process)

Prints: total busy % (all 4 cores = 400 %), per-core busy %, time spent at each CPU frequency
(if cpufreq stats exist), context switches and interrupts per second, and the top processes and
kernel threads by CPU (% of one core). Appends the same to logs/cpu-<label>.txt on the boot
partition when a label is given.
"""
import os
import sys
import time

HZ = os.sysconf("SC_CLK_TCK")


def stat():
    cpus, other = {}, {}
    with open("/proc/stat") as f:
        for line in f:
            p = line.split()
            if p[0].startswith("cpu"):
                v = list(map(int, p[1:]))
                cpus[p[0]] = (sum(v) - v[3] - v[4], sum(v))     # busy (minus idle, iowait), total
            elif p[0] in ("ctxt", "intr"):
                other[p[0]] = int(p[1])
    return cpus, other


def procs():
    out = {}
    for pid in os.listdir("/proc"):
        if not pid.isdigit():
            continue
        try:
            with open(f"/proc/{pid}/stat") as f:
                s = f.read()
            with open(f"/proc/{pid}/cmdline", "rb") as f:
                cmd = f.read().replace(b"\0", b" ").decode(errors="replace").strip()
        except OSError:
            continue
        comm = s[s.index("(") + 1:s.rindex(")")]
        rest = s[s.rindex(")") + 2:].split()
        out[pid] = (int(rest[11]) + int(rest[12]), cmd or f"[{comm}]")
    return out


def freqs():
    res = {}
    for d in sorted(os.listdir("/sys/devices/system/cpu/cpufreq")) if os.path.isdir("/sys/devices/system/cpu/cpufreq") else []:
        p = f"/sys/devices/system/cpu/cpufreq/{d}/stats/time_in_state"
        try:
            with open(p) as f:
                res[d] = {int(a): int(b) for a, b in (l.split() for l in f)}
        except OSError:
            pass
    return res


def main():
    secs = float(sys.argv[1]) if len(sys.argv) > 1 else 60
    label = sys.argv[2] if len(sys.argv) > 2 else ""
    c0, o0, p0, f0, t0 = *stat(), procs(), freqs(), time.monotonic()
    time.sleep(secs)
    c1, o1, p1, f1, t1 = *stat(), procs(), freqs(), time.monotonic()
    dt = t1 - t0
    lines = [f"== {label or 'measurement'}  {time.strftime('%F %T')}  {dt:.0f} s"]
    busy = lambda k: 100.0 * (c1[k][0] - c0[k][0]) / max(1, c1[k][1] - c0[k][1])
    ncpu = len([k for k in c1 if k != "cpu"])
    lines.append(f"total busy: {busy('cpu') * ncpu:.1f} % of {ncpu * 100} %   per core: "
                 + "  ".join(f"{k[3:]}={busy(k):.0f}%" for k in sorted(c1) if k != "cpu"))
    lines.append(f"context switches/s: {(o1['ctxt'] - o0['ctxt']) / dt:.0f}   interrupts/s: {(o1['intr'] - o0['intr']) / dt:.0f}")
    for pol, st in f1.items():
        d = {fr: st[fr] - f0.get(pol, {}).get(fr, 0) for fr in st}
        tot = sum(d.values()) or 1
        lines.append(f"{pol} time at MHz: " + "  ".join(f"{fr // 1000}={100 * v / tot:.0f}%" for fr, v in sorted(d.items()) if v))
    rows = []
    for pid, (ticks, cmd) in p1.items():
        if pid in p0 and p0[pid][1] == cmd:
            d = ticks - p0[pid][0]
            if d > 0:
                rows.append((100.0 * d / HZ / dt, pid, cmd))
    lines.append("top (% of one core):")
    for pct, pid, cmd in sorted(rows, reverse=True)[:15]:
        lines.append(f"  {pct:5.1f}  {pid:>6}  {cmd[:90]}")
    text = "\n".join(lines)
    print(text, flush=True)
    if label:
        path = f"/boot/firmware/logs/cpu-{label}.txt"
        try:
            with open(path, "a") as f:
                f.write(text.replace("\n", "\r\n") + "\r\n\r\n")
        except OSError:
            pass


if __name__ == "__main__":
    main()
