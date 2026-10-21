#!/bin/bash
# Run all rootfs build steps in order.
set -euo pipefail
cd "$(dirname "$0")"
bash ./00-host-deps.sh
bash ./01-fetch-rocknix.sh
bash ./02-extract-rocknix.sh
bash ./03-debootstrap.sh
bash ./04-install-packages.sh
bash ./04b-nwg-drawer.sh
bash ./05-configure-base.sh
bash ./06-hardware.sh
bash ./06b-cedrus.sh
bash ./06c-ffs-xinput.sh
bash ./07-desktop.sh
bash ./08-input.sh
bash ./09-services.sh
