#!/bin/sh
# Read-only readings for usb-otg-host.md. Changes nothing. Run as root on the handheld:
#   sudo sh usb-otg-readings.sh
date
echo "--- ID / VBUS pins (debugfs gpio)"
grep -i -E 'usb0|id_det|vbus' /sys/kernel/debug/gpio 2>/dev/null || echo "(debugfs not readable)"
echo "--- MUSB mode"
for f in /sys/bus/platform/devices/*musb*/mode; do
	[ -r "$f" ] && echo "$f: $(cat "$f")"
done
echo "--- usb0-vbus regulator"
grep -i -A1 'usb0-vbus' /sys/kernel/debug/regulator/regulator_summary 2>/dev/null || echo "(not found)"
echo "--- USB devices"
lsusb -t 2>/dev/null
echo "--- power supplies online"
for f in /sys/class/power_supply/*/online; do
	[ -r "$f" ] && echo "$f: $(cat "$f")"
done
echo "--- recent kernel lines"
dmesg | grep -i -E 'musb|sun4i-usb-phy|usb [0-9]' | tail -n 8
