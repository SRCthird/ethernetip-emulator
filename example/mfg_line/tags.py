# Copyright 2026 Merck KGaA, Darmstadt, Germany and/or its affiliates.
# All rights reserved

# example/mfg_line/tags.py
from src.ethernetip_emulator.server.tag_specs import tag_registry
from src.ethernetip_emulator.server.device import actions

@tag_registry.register
def _inputTags():
    return [
        ("I_LotNumber", actions.type.STRING(("LOT001"))),
        ("I_CatalogNumber", actions.type.STRING(("CAT001"))),
        ("I_SerialNumber", actions.type.UINT((0))),

        ("I_ProcessUnit", actions.type.BOOL((False))),
        ("I_ClearLine", actions.type.BOOL((False))),
    ]

@tag_registry.register
def _outputTags():
    return [
        ("O_Container", actions.type.MFGCONTAINER((
            "0", "", ""
        ))),
        ("O_Step", actions.type.BOOLARRAY(
            (False,False,False)
        )),
        ("O_Passed", actions.type.UINTARRAY(
            (0,)*10 # Tuple of size 10
        )),
        ("O_Failed", actions.type.UINTARRAY(
            (0,)*10 # Tuple of size 10
        )),
    ]
