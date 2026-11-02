# Audits

Reviews of the whole codebase, kept so that findings, decisions and fixes can be traced. Plan: one about every minor release.

Each audit is added here **once its High-severity findings are fixed or decided**, so that the public repository never describes an open security problem before there is a fix. Until then it lives outside the repository, and its findings are worked through one PR at a time.

| Audit | By | Against | Findings | Status |
|---|---|---|---|---|
| 2026-10-30 | Codex (external), reviewed 2026-11-02 | v0.3.5 (`6ef72a9`) | 2 High, 13 Medium, 3 Low; all confirmed in review | Being fixed: H01 (FFmpeg base) and L01, L03 done; the report is added here when H02 (Bluetooth pairing) is decided |

Fix PRs name the finding they address (for example "audit 2026-10-30, H01") in the code comment, the doc and the commit message.
