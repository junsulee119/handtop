# Audits

Reviews of the whole codebase, kept so that findings, decisions and fixes can be traced. Plan: one about every minor release.

Each audit is added here **once its High-severity findings are fixed or decided**, so that the public repository never describes an open security problem before there is a fix. Until then it lives outside the repository, and its findings are worked through one PR at a time.

| Audit | By | Against | Findings | Status |
|---|---|---|---|---|
| [2026-10-30](2026-10-30/HANDTOP_CODEBASE_AUDIT_2026-10-30.md) (Korean) | Codex (external), reviewed 2026-11-02 (section 9 of the report) | v0.3.5 (`6ef72a9`) | 2 High, 13 Medium, 3 Low; all confirmed in review (H02 rated Medium-High, M09 Low) | **All 18 fixed** (below) |

Fix PRs name the finding they address (for example "audit 2026-10-30, H01") in the code comment, the doc and the commit message.

## 2026-10-30: fixes

The report and its evidence folder are kept as delivered (`audit-evidence-20261030/`, checked against its `manifest.json`); the review is its section 9. Fix status is kept here, not in the report.

| Finding | What | Fixed in |
|---|---|---|
| H01 | FFmpeg built on 7.1.3 while Debian had 7.1.5 (two CVEs), shown as Debian's version and held | `79c4f2e` |
| H02 | Bluetooth controller modes accepted every pairing and service; BT Xbox trusted any paired device | `ea8959f` |
| M01 | A Bluetooth report the busy link refused counted as sent (last release lost) | `224da45` |
| M02 | A game's vibration still queued when gamepad mode ended | `4d91840` |
| M03 | A reopened L2CAP channel left the old socket's GLib watch | `224da45` |
| M04 | Input config: bad numbers, yes/no values and key names not rejected | `4d91840` |
| M05 | An error in the input loop stopped input while the watchdog saw a live daemon | `4d91840` |
| M06 | `SYN_DROPPED` ignored: a release lost in a queue overflow left a button held | `42b49b5` |
| M07 | A gamepad whose grab failed was still used | `4d91840` |
| M08 | USB mode: `SIGTERM` during gadget set-up skipped the clean-up | `224da45` |
| M09 | Extend layout used the monitor's physical size (gap at scale ≠ 1) | `1be60b4` |
| M10 | Display Test switch-back counted ticks; commands had no time limit | `1be60b4` |
| M11 | Wi-Fi import deleted the old profile before adding the new one | `9a40291` |
| M12 | Screen off's low-power state survived a log-out | `47ed8d1` |
| M13 | Kernel compiler always the x86_64-hosted build | `c397c31` |
| L01 | Image build ran 29 of 31 input tests | `859e369` |
| L02 | Edited kernel patches not picked up by an existing kernel tree | `c397c31` |
| L03 | `$NMCLI` unquoted; the Wi-Fi test broke in paths with spaces | `859e369` |
| (review) | Input daemon's code in the image owned by the desktop user | `4d91840` |

Not counted as findings (report section 6): BlueZ, Go module and ROCKNIX advisories, and Moonlight's bundled FFmpeg. ROCKNIX and Go are in the weekly drift check ([../upstreams.md](../upstreams.md)); BlueZ comes from Debian; Moonlight's FFmpeg is for its upstream to fix.
