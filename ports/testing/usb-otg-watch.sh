#!/bin/sh
# Read-only watcher for usb-otg-host.md: prints a line whenever the ID pin, the MUSB mode, the
# port's 5 V regulator, charger power or the USB device list changes. Changes nothing. Stops by
# itself after 10 minutes (or Ctrl+C). Run as root so the ID pin is visible:
#   sudo sh usb-otg-watch.sh
end=$(( $(date +%s) + 600 ))
last=""
while [ "$(date +%s)" -lt "$end" ]; do
	id=$(grep -i -E 'usb0_id|id_det|PI4 ' /sys/kernel/debug/gpio 2>/dev/null | tr -s ' ' | tr '\n' ';')
	mode=$(cat /sys/bus/platform/devices/*musb*/mode 2>/dev/null)
	vbus=""
	for r in /sys/class/regulator/regulator.*; do
		[ "$(cat "$r/name" 2>/dev/null)" = usb0-vbus ] && vbus=$(cat "$r/state" 2>/dev/null)
	done
	chg=$(cat /sys/class/power_supply/axp20x-usb/online 2>/dev/null)
	devs=$(lsusb 2>/dev/null | grep -v -c 'root hub')
	now="id[$id] mode=$mode usb0-vbus=$vbus charger=$chg usb-devices=$devs"
	if [ "$now" != "$last" ]; then
		echo "$(date +%T) $now"
		last=$now
	fi
	sleep 1
done
echo "$(date +%T) watcher finished"
dmesg | grep -i -E 'musb|sun4i-usb-phy|usb [0-9]|input:' | tail -n 15
