# Re-center sticks

**Apps → Re-center sticks** (`rg35xxh-recenter-sticks`): fixes stick drift. Keep your hands off the sticks while it counts down.

## Stick drift (2026-10-16)

- **Cause:** the stick driver (`rocknix-singleadc-joypad`, from ROCKNIX) measures each axis' centre **once**, from a **single ADC reading**, when the device is first opened (`joypad_open()` → `adc->cal = adc->value`), and reports every later reading minus that value. If that one reading is off (bad first conversion right after the analog multiplexer switches, or the stick touched at that moment), the axis stays offset until the device is reopened. Seen once after flashing 20261001: left X centre ~1290/1800 off → cursor drifted left; a hands-off restart fixed it. The driver is unchanged between ROCKNIX 20260901 and 20261001 (one-line build fix only).
- **Fix: Apps → Re-center sticks** (`rg35xxh-recenter-sticks`). Shows "hands off" for 3 s, then sends `SIGUSR1` to the input daemon, which first stops and erases every vibration effect on the device (they belong to the open file handle; closing it with an effect playing would leave the motor to the kernel's teardown, see [../hardware-safety.md](../hardware-safety.md)), then closes and reopens the stick device (it is the only user, so the driver measures the centre again), uploads its own haptics again, re-applies vibration a PC still wants (Wired / BT Controller mode), samples the axes for 0.5 s, applies a software correction to any axis still off-centre (> 8 % of travel, steady), buzzes and shows a notification. Log: `re-centre:` lines in `~/.local/state/session/inputd.log`.
- Verified on the device: holding the stick during the countdown created a drift; a hands-off run removed it.

App icon: a drifted knob pulled back to the centre (`tools/icons/gen_app_icons.py`).
