# Copyright 2026 Merck KGaA, Darmstadt, Germany and/or its affiliates.
# All rights reserved

# example/mfg_line/tags.py
from src.ethernetip_emulator.server.tag_specs import tag_registry
from src.ethernetip_emulator.server.device import actions

@tag_registry.register
def _():
    return [
        # Custom composite type
        ("O_Container",       actions.type.MFGCONTAINER((
            "1011", "LOT001", "CONT001"
        ))),

    ]

