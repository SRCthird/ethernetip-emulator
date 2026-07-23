# Copyright 2026 Merck KGaA, Darmstadt, Germany and/or its affiliates.
# All rights reserved

# example/raspberry_pi/tags.py

from ethernetip_emulator.server.tag_specs import tag_registry
from ethernetip_emulator.server.device import actions


@tag_registry.register
def _():
    return [
        ("O_INCR", actions.type.USINT(0)),
        ("O_GreenLed", actions.type.GPIO((18, False, "out"))),
        ("O_RedLed", actions.type.GPIO((16, False, "out"))),
        ("O_BlueLed", actions.type.GPIO((23, False, "out"))),
        ("I_Button", actions.type.GPIO((12, True, "in"))),
    ]
