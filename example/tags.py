# Copyright 2026 Merck KGaA, Darmstadt, Germany and/or its affiliates.
# All rights reserved

# scope/tags.py
from typing import Any, List, Tuple

from src.server.tag_specs import tag_registry

@tag_registry.register
def _tags() -> List[Tuple[str, str, Any]]:
    return [
        # (tag_name,          type_spec,  default)
        ("I_TEXT",            "STRING",   ""),
        ("O_TEXT",            "STRING",   ""),

        ("O_INCR",            "INT",       0),
        ("O_Updates.LAZY",    "INT",       0),   # lazy counter (separate)

        # Sized integer / float types
        ("O_8Bit",            "SINT",      0),
        ("O_16Bit",           "INT",       0),
        ("O_32Bit",           "DINT",      0),
        ("O_32Bit_Float",     "REAL",      0.0),

        # Built-in composite types
        ("O_Updates",         "COUNTER",  1000),
        ("O_Timer",           "TIMER",    5000),
        ("O_String",          "STRING",   "HELLO"),
    ]

