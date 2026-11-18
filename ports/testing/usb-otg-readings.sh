#!/bin/sh
# Read-only readings for usb-otg-host.md. Changes nothing. Runs as the desktop user; the
# ID pin (debugfs) is only shown when run as root:
#   sh usb-otg-readings.sh      or      sudo sh usb-otg-readings.sh
date
echo "--- ID / VBUS pins (debugfs gpio)"
grep -i -E 'usb0|id_det|vbus' /sys/kernel/debug/gpio 2>/dev/null || echo "(debugfs not readable)"
echo "--- MUSB mode"
for f in /sys/bus/platform/devices/*musb*/mode; do
	[ -r "$f" ] && echo "$f: $(cat "$f")"
done
echo "--- USB 5 V regulators"
for r in /sys/class/regulator/regulator.*; do
	n=$(cat "$r/name" 2>/dev/null)
	case "$n" in
	*usb*|*vbus*) echo "$n: $(cat "$r/state" 2>/dev/null), users $(cat "$r/num_users" 2>/dev/null)" ;;
	esac
done
for f in /sys/bus/platform/devices/*musb*/vbus; do
	[ -r "$f" ] && echo "musb vbus: $(cat "$f")"
done
echo "--- USB devices"
lsusb -t 2>/dev/null
echo "--- power supplies online"
for f in /sys/class/power_supply/*/online; do
	[ -r "$f" ] && echo "$f: $(cat "$f")"
done
echo "--- recent kernel lines"
dmesg | grep -i -E 'musb|sun4i-usb-phy|usb [0-9]' | tail -n 8
