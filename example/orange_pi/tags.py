# Copyright 2026 Merck KGaA, Darmstadt, Germany and/or its affiliates.
# All rights reserved

# example/orange_pi/tags.py

from ethernetip_emulator.server.tag_specs import tag_registry
from ethernetip_emulator.server.device import actions


@tag_registry.register
def _():
    return [
        ("GPIO_18", actions.type.GPIO(("PH04", False, "out"))),
        ("GPIO_40", actions.type.GPIO(("PI03", True, "in"))),
    ]
