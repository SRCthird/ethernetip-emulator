# Copyright 2026 Merck KGaA, Darmstadt, Germany and/or its affiliates.
# All rights reserved

# scope/tags.py
from src.server.tag_specs import tag_registry
from src.server.device import actions

@tag_registry.register
def _tags():
    return [
        # (tag_name,          type_spec(default))
        ("I_TEXT",            actions.type.STRING("")),
        ("O_TEXT",            actions.type.STRING("")),


        ("O_INCR",            actions.type.INT(0)),
        ("O_Updates.LAZY",    actions.type.INT(0)),   # lazy counter (separate)

        ("I_BOOL",            actions.type.BOOL(0)),

        # Sized integer / float types
        ("O_8Bit",            actions.type.SINT(0)),
        ("O_16Bit",           actions.type.INT(0)),
        ("O_32Bit",           actions.type.DINT(0)),
        ("O_32Bit_Float",     actions.type.REAL(0.0)),

        # Arrays
        ("O_StringArray",     actions.type.SSTRINGARRAY((
            "A", "B", "B", "C"
        ))),
        ("O_SintArray",       actions.type.SINTARRAY((
            1, 2, 3, 4
        ))),
        ("O_IntArray",       actions.type.INTARRAY((
            5, 6, 7, 8
        ))),
        ("O_DintArray",       actions.type.DINTARRAY((
            9, 10, 11, 12
        ))),
        ("O_BoolArray",       actions.type.BOOLARRAY((
            True, True, False, True
        ))),
        ("O_RealArray",       actions.type.REALARRAY((
            1.2, 3.4, 5.6, 7.8
        ))),

        # Built-in composite types
        ("O_Updates",         actions.type.COUNTER(1000)),
        ("O_Timer",           actions.type.TIMER(5000)),
        ("O_String",          actions.type.STRING("HELLO")),

        # Custom composite type
        ("O_Container",       actions.type.MFGCONTAINER(("1011", "LOT001", "CONT001"))),
    ]
