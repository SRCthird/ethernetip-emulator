# Copyright 2026 Merck KGaA, Darmstadt, Germany and/or its affiliates.
# All rights reserved

# example/tags.py
from src.ethernetip_emulator.server.tag_specs import tag_registry
from src.ethernetip_emulator.server.device import actions

@tag_registry.register
def _tags():
    return [
        # (tag_name,          type_spec(default))
        ("I_TEXT",            actions.type.STRING("")),
        ("O_TEXT",            actions.type.STRING("")),


        ("O_INCR",            actions.type.INT(0)),
        ("O_Updates.LAZY",    actions.type.INT(0)),   # lazy counter (separate)

        # Signed integers
        ("O_SINT",            actions.type.SINT(0)),
        ("O_INT",             actions.type.INT(0)),
        ("O_DINT",            actions.type.DINT(0)),
        ("O_LINT",            actions.type.LINT(0)),

        # Unsigned integers
        ("O_USINT",           actions.type.USINT(0)),
        ("O_UINT",            actions.type.UINT(0)),
        ("O_UDINT",           actions.type.UDINT(0)),
        ("O_ULINT",           actions.type.ULINT(0)),

        # Bool
        ("O_BOOL",            actions.type.BOOL(0)),

        # Float/Double
        ("O_REAL",            actions.type.REAL(0.0)), # 32 bit
        ("O_LREAL",           actions.type.LREAL(0.0)), # 64 bit

        # Arrays
        ("O_StringArray",     actions.type.SSTRINGARRAY((
            "A", "B", "B", "C"
        ))),
        ("O_SintArray",       actions.type.SINTARRAY((
            -1, 2, -3, 4
        ))),
        ("O_UsintArray",      actions.type.USINTARRAY((
            1, 2, 3, 4
        ))),
        ("O_IntArray",        actions.type.INTARRAY((
            -5, 6, -7, 8
        ))),
        ("O_UintArray",       actions.type.UINTARRAY((
            5, 6, 7, 8
        ))),
        ("O_DintArray",       actions.type.DINTARRAY((
            -9, 10, -11, 12
        ))),
        ("O_UdintArray",      actions.type.UDINTARRAY((
            9, 10, 11, 12
        ))),
        ("O_LintArray",       actions.type.LINTARRAY((
            -9, 10, -11, 12
        ))),
        ("O_UlintArray",      actions.type.ULINTARRAY((
            9, 10, 11, 12
        ))),
        ("O_BoolArray",       actions.type.BOOLARRAY((
            True, True, False, True
        ))),
        ("O_RealArray",       actions.type.REALARRAY((
            1.2, 3.4, 5.6, 7.8
        ))),
        ("O_LrealArray",      actions.type.LREALARRAY((
            1.2, 3.4, 5.6, 7.8
        ))),

        # Built-in composite types
        ("O_Updates",         actions.type.COUNTER(1000)),
        ("O_Timer",           actions.type.TIMER(5000)),
        ("O_String",          actions.type.STRING("HELLO")),

        # Custom composite type
        ("O_Container",       actions.type.MFGCONTAINER((
            "1011", "LOT001", "CONT001"
        ))),

    ]

# GPIO Tag
try:
    import OPi.GPIO as GPIO
    @tag_registry.register
    def _opi_tags():
        return [
            ("GPIO_18",           actions.type.GPIO((
                "PH04", False, "out"
            ))),
            ("GPIO_40",           actions.type.GPIO((
                "PI03", True, "in"
            ))),
        ]
except ImportError:
    try:
        import RPi.GPIO as GPIO
        @tag_registry.register
        def _rpi_tags():
            return [
                ("GPIO_18",           actions.type.GPIO((
                    18, False, "out"
                ))),
                ("GPIO_40",           actions.type.GPIO((
                    40, True, "in"
                ))),
            ]
    except ImportError:
        pass
