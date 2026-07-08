# Copyright 2026 Merck KGaA, Darmstadt, Germany and/or its affiliates.
# All rights reserved

# example/raspberry_pi/tags.py

from src.ethernetip_emulator.server.tag_specs import tag_registry
from src.ethernetip_emulator.server.device import actions

@tag_registry.register
def _():
    return [
        ("GPIO_18",           actions.type.GPIO((
            18, False, "out"
        ))),
        ("GPIO_40",           actions.type.GPIO((
            40, True, "in"
        ))),
    ]
