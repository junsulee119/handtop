#!/usr/bin/python3
"""Motor stress test, through the same path as the external controller modes: pretends to be an
external-controller service (rg35xxh-btpad / -usbpad / -switchbt), lets the input daemon connect
(SIGUSR2, like the External Controller app) and sends it "rumble <big> <small>" requests in a
chosen pattern. The daemon drives the motor through its gate exactly as in a real session.

WARNING: written to find what freezes the handheld (2026-10-28: Mario Kart vibration in Switch
Controller mode over Bluetooth). A pattern can lock up the whole device with the motor on; the
way out is holding Power ~10 s, and the power chip may then need the battery disconnected
(docs/flashing.md). Run `sync` first. Never run it in the build chroot or on the build host.

  sudo motor-stress.py <pattern> <seconds>
  patterns: steady (level 8), flip (2<->6 every 0.1 s), onoff (0<->5 every 0.1 s),
            random (any level every 50 ms, like a game), randomslow (any level every 0.5 s)

Every step is marked in the kernel log (/dev/kmsg, "motor-stress:") and appended, fsync'ed, to
logs/motor-stress.txt on the boot partition, so the last thing before a freeze survives.
Needs: the input daemon running, no external controller mode on. Ctrl+C / SIGTERM stops cleanly
(closing the socket makes the daemon stop the motor).
"""
import grp
import os
import random
import signal
import socket
import subprocess
import sys
import threading
import time

SOCK = "/run/rg35xxh-extpad.sock"
LOG = "/boot/firmware/logs/motor-stress.txt"
PATTERNS = {
    "steady":     (1.0, lambda i: 255),
    "flip":       (0.1, lambda i: (64, 191)[i % 2]),
    "onoff":      (0.1, lambda i: (0, 160)[i % 2]),
    "random":     (0.05, lambda i: random.randrange(0, 256)),
    "randomslow": (0.5, lambda i: random.randrange(0, 256)),
}


def mark(msg):
    line = time.strftime("%H:%M:%S ") + f"{time.monotonic():.3f} motor-stress: {msg}"
    print(line, flush=True)
    try:
        with open("/dev/kmsg", "w") as k:
            k.write(f"<5>motor-stress: {msg}\n")
    except OSError:
        pass
    try:
        os.makedirs(os.path.dirname(LOG), exist_ok=True)
        with open(LOG, "a") as f:
            f.write(line + "\r\n")
            f.flush()
            os.fsync(f.fileno())
    except OSError:
        pass


def main():
    if os.geteuid() != 0 or len(sys.argv) != 3 or sys.argv[1] not in PATTERNS:
        sys.exit(__doc__)
    name, seconds = sys.argv[1], float(sys.argv[2])
    step, level = PATTERNS[name]
    if os.path.exists(SOCK):
        sys.exit("an external controller mode is on (socket exists): stop it first")
    srv = socket.socket(socket.AF_UNIX, socket.SOCK_SEQPACKET)
    srv.bind(SOCK)
    os.chown(SOCK, 0, grp.getgrnam("input").gr_gid)
    os.chmod(SOCK, 0o660)
    srv.listen(1)
    srv.settimeout(10)
    stop = threading.Event()
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *a: stop.set())
    conn = None
    try:
        if subprocess.run(["pkill", "-USR2", "-x", "-f", r"python3 -m rg35xxh_inputd\.daemon"]).returncode:
            sys.exit("input daemon not running")
        conn, _ = srv.accept()
        conn.send(b"hello bt")

        def drain():                     # pad events from the daemon: read and drop
            while not stop.is_set():
                try:
                    if not conn.recv(64):
                        stop.set()
                except socket.timeout:
                    continue
                except OSError:
                    stop.set()
        conn.settimeout(0.5)
        threading.Thread(target=drain, daemon=True).start()
        mark(f"start pattern={name} step={step}s duration={seconds}s")
        t0, i, last_mark = time.monotonic(), 0, 0.0
        while not stop.is_set() and time.monotonic() - t0 < seconds:
            v = level(i)
            conn.send(f"rumble {v} {v}".encode())
            i += 1
            now = time.monotonic() - t0
            if now - last_mark >= 5:
                last_mark = now
                mark(f"{name} t={now:.0f}s requests={i} last={v}")
            time.sleep(step)
        conn.send(b"rumble 0 0")
        mark(f"end pattern={name} requests={i}")
    finally:
        stop.set()
        for s in (conn, srv):
            if s:
                s.close()
        try:
            os.unlink(SOCK)
        except FileNotFoundError:
            pass


if __name__ == "__main__":
    main()
