# Hardware safety rules

Rules for any change to code that holds hardware (gamepad, vibration motor, power button, USB gadget, Bluetooth / Wi-Fi radio, framebuffer, backlight, CPU cores), changes power states, or starts and stops the processes that do. On this handheld, a mistake there does not just crash one program: the kernel can lock up (input, Wi-Fi and SSH all gone) and, after a forced power-off, the power chip can stay latched until the battery is disconnected ([flashing.md](flashing.md#if-something-is-wrong)).

Where they come from:
- **Log-out freeze, 2026-10-26:** a new session killed the old input daemon while the new one was taking over the gamepad and motor. Full write-up: [services/input-daemon.md](services/input-daemon.md#incident-freeze-at-log-out-2026-10-26).
- **Motor lock-ups, earlier:** re-uploading vibration effects many times a second, and effects with no end, locked the system up three times (`MOTOR_INTERVAL` in `src/inputd/rg35xxh_inputd/daemon.py`).
- **Review of all hardware-facing code, 2026-10-26:** the findings below marked *(review)*.

## 1. One owner, handed over cleanly

1. **One owner per device at a time, enforced by a lock, not by timing.** For example, the input daemon takes `flock` on `$XDG_RUNTIME_DIR/rg35xxh-inputd.lock` before opening any device. The kernel drops a lock only when its holder has really ended, so a new owner never overlaps an old one, however slow or stuck the old one is.
2. **Stop means: ask (`SIGTERM`), wait until the process is gone, and only then start the next one.** Use `SIGKILL` only as a last resort after a bounded wait. Never start a replacement "right after" a kill.
3. **Before stopping a process or a process group, look at what is actually in it** (`ps -eo user,pid,ppid,pgid,args`). Don't assume who runs as which user or who belongs to which group. The input daemon runs as the desktop user, inside the session autostart's process group.

## 2. Every exit path releases the hardware

1. **Every program that holds hardware has a clean exit that releases it in order:** stop what is running first (motor, USB transfers, advertising), then free it (erase effects, remove the gadget), then let go (ungrab, close).
2. **The clean exit runs on every way out:** `SIGTERM`/`SIGINT`/`SIGHUP`, errors, a lost device, a lost connection. Install the signal handling before taking hardware, and make the release step idempotent: run it twice, or after a partial set-up, without harm.
3. **A failed set-up unwinds itself.** Wrap the whole set-up, not only the main loop, so a failure halfway releases what was already taken (*review: Wired controller mode*). Also clean up leftovers of an earlier run before starting.
4. **Re-opening a device is an exit too.** Release before close, then reset everything that belonged to the old handle, such as effect IDs (*review: Re-center sticks*).

## 3. Nothing may end or freeze a hardware owner behind its back

1. **No display connection in a process that holds hardware.** GDK ends its process with `_exit()` the moment the Wayland display goes away (every log-out), with no cleanup. Windows and other UI go in a child process, driven by messages (see `ui.py`). The same goes for any library that can `abort()` or `_exit()` on its own.
2. **No `Gtk.main()`.** Quitting it from a signal handler deadlocks; use `GLib.MainLoop`.
3. **Nothing on the input path blocks without a bound.** Every subprocess gets a `timeout=`, and writes to helper processes are non-blocking (drop the message rather than wait).
4. **Whatever takes the power button must be watched.** The input daemon grabs the power key, so logind's "hold to power off" backup never sees it. If the daemon hangs, the only way out is the hardware power cut, which is the one that latched the power chip. A process that grabs input needs a watchdog that restarts it when it stops responding (*review*).

## 4. Signals reach exactly the intended process

1. **Find targets exactly:** an exact command line (`^python3 -m rg35xxh_inputd\.daemon$`), a PID file, or the lock holder. Never a loose `pkill -f`/`pgrep -f` prefix that can also match a helper, or the command you are typing (*review*).
2. **Send a process only signals it handles.** An unhandled `SIGUSR1`/`SIGUSR2` or real-time signal kills it by default.
3. **Real-time signals only to a Waybar that has been running for at least 3 s** (it dies on one that arrives before its handlers are installed). Every sender checks the process age.
4. **Scripts that run under `/bin/sh` are dash:** `kill -- -PGID` fails there. Test such scripts with `dash`, not `bash`.

## 5. Motor

1. **Every vibration effect has a fixed length**; no endless effects (length 0). Long vibrations are re-triggered while wanted.
2. **Hardware updates go through the motor gate:** at most one per `MOTOR_INTERVAL`, strengths rounded to `MOTOR_LEVELS`, and effects uploaded once and then only played or stopped.
3. **Stop before erase, erase before close**, on every path (see 2).

## 6. Power states and radios

1. **Power-state changes check the others.** Before suspending, turning the screen off, taking CPU cores offline or switching a controller mode, check which of the others is active. Either combine them deliberately and test the combination, or refuse. Example: auto-sleep must not suspend while Screen off has cores 1–3 offline unless that combination has been tested (*review*).
2. **Restore on every path:** a power state entered by one session must be undone if that session ends (log-out, crash).
3. **Do as little to the radio as possible.** Wi-Fi and Bluetooth share one chip (RTL8821CS, rtw88). Power-cycling Bluetooth or restarting `bluetoothd` can stall Wi-Fi, which takes SSH with it. Changes there get a stress test (enter and leave 10 times while pinging the handheld) (*review*).
4. **Nothing writes to the power chip, regulators or charging limits** (`axp*`, `regulator`, `input_current_limit`, `/dev/mem`, `i2cset`) without a documented reason and a recovery plan. As of 2026-10-26, nothing in Handtop does.

## 7. Testing on the device

1. **Test the stop and start path by hand first:** stop the piece several times, check its log and that input still works, and only then test a log-out, a mode switch or a reboot.
2. **Run `sync` before any test that may freeze the device**, and say so beforehand.
3. **One change at a time**, each tested before the next. **Commit after the device test**, not before.
4. **If it freezes, keep the card.** Read its journal (`/var/log/journal` is persistent) before re-flashing; re-flashing erases the evidence.

## Checklist for a change

Use it when a change touches anything in the first paragraph:

- [ ] Who owns the device before, during and after the change? Can two owners ever overlap? (1)
- [ ] What happens on `SIGTERM`, on an error, on a lost device, on log-out? Does each release the hardware, motor first? (2)
- [ ] Can anything end or freeze the process without its clean exit: display loss, a blocking call, a library `_exit`? (3)
- [ ] Do all signals go to exactly one, intended process that handles them? (4)
- [ ] Vibration: fixed length, through the gate? (5)
- [ ] Which other power states or modes can be active at the same time, and is that combination tested? (6)
- [ ] Hand test of the stop/start path done, `sync` before the risky test, committed only after it passed? (7)
