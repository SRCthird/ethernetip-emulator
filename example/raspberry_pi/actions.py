# Copyright 2026 Merck KGaA, Darmstadt, Germany and/or its affiliates.
# All rights reserved

# example/raspberry_pi/actions.py

from ethernetip_emulator.server.device import actions

actions.increment.start(tag_name="O_INCR", wrap=actions.usint.MAX)


@actions.int.on_change("O_INCR")
def on_incr_change(attr, key, value):
    if value[0] % 2 == 0:
        actions.gpio.write_pin("O_GreenLed", True)
        actions.gpio.write_pin("O_RedLed", False)
    else:
        actions.gpio.write_pin("O_GreenLed", False)
        actions.gpio.write_pin("O_RedLed", True)


actions.gpio.start_polling("I_Button")


@actions.gpio.on_change("I_Button")
def on_button_press(attr, key, value):
    if not value[0]:
        actions.gpio.write_pin("O_BlueLed", True)
    else:
        actions.gpio.write_pin("O_BlueLed", False)
