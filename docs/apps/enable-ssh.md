# Enable SSH

**Apps → Enable SSH** (`rg35xxh-enable-ssh`) turns on the SSH server.

The image ships with SSH **off** and a publicly known default password (`rg35xxh`). The app opens a terminal, asks you to choose your own password first (`passwd`), then enables and starts the SSH server. If SSH is already on, it says so.

- Host keys are generated per device on first boot (`rg35xxh-ssh-keygen.service`), so no two devices share them.
- Useful alongside: `tmux` and `mosh` (survive dropped connections), Tailscale for access from anywhere ([tailscale-login.md](tailscale-login.md)).
- App icon: terminal saying "SSH" with a key (`tools/icons/gen_app_icons.py`).
