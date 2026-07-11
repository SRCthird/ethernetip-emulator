# Copyright 2026 Merck KGaA, Darmstadt, Germany and/or its affiliates.
# All rights reserved

# example/raspberry_pi/tags.py

from src.ethernetip_emulator.server.tag_specs import tag_registry
from src.ethernetip_emulator.server.device import actions

@tag_registry.register
def _():
    return [
        ("O_INCR",            actions.type.INT(0)),

        ("GPIO_18",           actions.type.GPIO((
            18, False, "out"
        ))),
        ("GPIO_16",           actions.type.GPIO((
            16, False, "out"
        ))),
        ("GPIO_23",           actions.type.GPIO((
            23, False, "out"
        ))),

        ("GPIO_12",           actions.type.GPIO((
            12, True, "in"
        ))),
    ]
