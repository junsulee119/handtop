#!/usr/bin/env python3
"""Print the boot partition's rg35xxh-input.conf for a new image (build/10-image.sh): the system
input.conf with every setting commented out, under the rescue header.
Usage: boot-input-conf.py overlay/etc/rg35xxh/input.conf"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src", "inputd"))
from rg35xxh_inputd.config import boot_template  # noqa: E402

with open(sys.argv[1], encoding="utf-8") as f:
    sys.stdout.write(boot_template(f.read()))
