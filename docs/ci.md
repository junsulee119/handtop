# CI

Every push and pull request runs **`tools/ci-checks.sh`** in GitHub Actions (`.github/workflows/ci.yml`, Ubuntu 24.04 with Python 3.13, Debian trixie's version). Run the same script locally before opening a PR:

```
tools/ci-checks.sh
```

It needs bash, dash, shellcheck, Python 3 with pytest and git; no root, no hardware, no image build. Scratch files go to `work/ci-checks/` and are removed afterwards.

## What it checks

| Check | Why |
|---|---|
| `dash -n` on every `/bin/sh` script (by shebang, or a `# shellcheck shell=sh` line in sourced files) | On the device `/bin/sh` is dash; bash-only syntax there breaks at run time (AGENTS.md) |
| `bash -n` on every bash script and `*.sh` | Syntax errors |
| `shellcheck -S warning` on all of them | Errors and warnings fail CI. The ones that were in the tree in 2026-11 are silenced line by line with `# shellcheck disable=SCxxxx  # reason` (or fixed when that changed nothing), so a new warning stands out. A disable needs a reason on the same line. Info and style hints (`a && b \|\| c`, unfollowed `source`) are not enforced |
| `py_compile` on every `*.py` and Python script | Syntax errors in code that only runs on the device |
| Input daemon tests: `pytest` on all of `src/inputd/tests` (`test_core.py`: the pure logic and the config file; `test_daemon.py`: failure paths in `daemon.py` with evdev and GLib faked), and the direct run of `test_core.py` that the image build uses (`build/08-input.sh`), with **the same number of tests in that file** | The build once ran 29 of 31 tests because two were defined after the `if __name__ == "__main__"` block (audit 2026-10-30, L01) |
| `pytest` on `tests/` (`test_controller_services.py`: failure paths in `rg35xxh-btpad`, `rg35xxh-switchbt`, `rg35xxh-usbpad` with D-Bus, evdev and GLib faked; nothing touches Bluetooth or USB) | Audit 2026-10-30 M01 (a report the busy link refused counted as sent), M03 (watch left on a replaced channel), M08 (stop during the USB set-up skipped the clean-up) |
| `tools/test-wifi-import.sh` from a copy of the repo whose path contains a space | The Wi-Fi import ran a command path unquoted (audit 2026-10-30, L03) |

Files sourced by other scripts have no shebang; they carry a `# shellcheck shell=bash` (or `sh`) line near the top so that shellcheck and this script know their shell.

## What it does not cover

- **The image build** (root, qemu, about 1.5 hours): build it as in [building.md](building.md).
- **Anything on the device:** hardware, power, the session and controller modes still need a test on a real RG35XX H before merging (AGENTS.md).
- **Upstream updates:** that is the weekly drift check, [upstreams.md](upstreams.md).
