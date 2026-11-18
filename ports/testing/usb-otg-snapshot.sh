#!/bin/sh
# Read-only snapshot for usb-otg-host.md, taken while a device is plugged into the OTG port:
# the ID and 5 V enable pins, the 5 V regulator and the host controllers' port registers.
# Changes nothing. Run as root:  sudo sh usb-otg-snapshot.sh
date
echo "--- GPIO lines (ID detect, 5 V enable)"
grep -i -E 'id_det|vbus|usb' /sys/kernel/debug/gpio 2>/dev/null
echo "--- regulators"
grep -i -E 'usb|vbus' /sys/kernel/debug/regulator/regulator_summary 2>/dev/null
echo "--- EHCI (5101000.usb) registers"
grep -i -E 'portsc|status|command' /sys/kernel/debug/usb/ehci/5101000.usb/registers 2>/dev/null
echo "--- OHCI (5101400.usb) registers"
grep -i -E 'roothub|portstatus|control' /sys/kernel/debug/usb/ohci/5101400.usb/registers 2>/dev/null
echo "--- PI16 pin state"
grep -i -B1 -A1 'PI16' /sys/kernel/debug/pinctrl/*/pinmux-pins 2>/dev/null | head -n 6
grep -i 'PI16' /sys/kernel/debug/pinctrl/*/pinconf-pins 2>/dev/null | head -n 2
