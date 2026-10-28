Handtop (Debian desktop for the RG35XX H) - boot partition
===========================================================

Files you may edit on this partition (from Windows):
  wifi.txt               Wi-Fi network. Imported at next boot, password is then removed from the file.
  rg35xxh-input.conf     Controls (speeds, button actions). Applies after re-login/reboot.
  panel.txt              Screen panel: auto (default), regular or rev6.
  logs\boot-NNNN.txt     Diagnostic logs of the last 5 boots (written by the device).

Screen garbled or black?  RG35XX H units have one of two screens. The handheld picks
  the right one by itself and restarts once if it had to switch (logs\panel.txt).
  If the screen stays garbled, write rev6 (or regular) in panel.txt instead of auto
  (use "Safely remove" / Eject before taking the card out).

Login: user "rg", password "rg35xxh". SSH is off: turn it on with Apps > Enable SSH
(it asks you to choose your own password first).
Do not edit KERNEL, dtb*.img or extlinux\ unless you know what you are doing.

Disclaimer: Handtop is an unofficial hobby project, not affiliated with or endorsed by
Anbernic, ROCKNIX, Nintendo, Microsoft or anyone else named; product names are trademarks of
their owners. It comes "as is", without warranty: use it at your own risk (full text: README
on https://github.com/junsulee119/handtop).
