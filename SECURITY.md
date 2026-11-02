# Security

## Reporting a problem

Please report security problems **privately**, not in a public issue: on GitHub, open the repository's **Security** tab and choose **Report a vulnerability**. Include what you found, how to reproduce it, and which Handtop version (and DDR3 / DDR4 unit) you used.

## What to expect

Handtop is a small spare-time project. Reports are answered as soon as possible, and a fix goes into the next release, with a CHANGELOG line saying that it carries a security fix.

## How updates reach handhelds

Today, fixes in the parts Handtop builds itself (FFmpeg, the VA-API driver, the kernel modules, the kernel and firmware from ROCKNIX) reach a handheld **only by flashing a new image**. Debian packages get Debian's security updates through apt as usual (`sudo apt update && sudo apt upgrade`). Updates without reflashing are planned.

What is tracked and how: [docs/upstreams.md](docs/upstreams.md) (pinned pieces, weekly drift check) and [docs/audits/](docs/audits/README.md) (codebase audits).
