# Copyright 2026 Merck KGaA, Darmstadt, Germany and/or its affiliates.
# All rights reserved

# example/raspberry_pi/actions.py

from src.ethernetip_emulator.server.device import actions

actions.increment.start(tag_name="O_INCR", start=32_757, wrap=actions.int.MAX)

@actions.int.on_change("O_INCR")
def on_incr_change(attr, key, value):
    if value[0] % 2 == 0:
        actions.gpio.write_pin("GPIO_18", True)
        actions.gpio.write_pin("GPIO_16", False)
    else:
        actions.gpio.write_pin("GPIO_18", False)
        actions.gpio.write_pin("GPIO_16", True)

actions.gpio.start_polling("GPIO_12")

@actions.gpio.on_change("GPIO_12")
def on_button_press(attr, key, value):
    if not value[0]:
        actions.gpio.write_pin("GPIO_23", True)
    else:
        actions.gpio.write_pin("GPIO_23", False)

