# Copyright 2026 Merck KGaA, Darmstadt, Germany and/or its affiliates.
# All rights reserved

# src/server/actions/sstringarray.py
from __future__ import annotations
from typing import TYPE_CHECKING, Any
from src.server.device import actions
from src.server.actions import TypeSpec
from src.server.tag_specs import tag_registry

if TYPE_CHECKING:
    from src.server.actions import AttributeActions

@actions.datatype
class SstringArray:
    MAX = 127
    MIN = 0 

    def __init__(self, parent: AttributeActions):
        self.parent = parent

    @staticmethod
    def type_validator(v: Any):
        if (
            not isinstance(v, tuple)
            and len(v) == 2
            and isinstance(v[0], tuple)
            and isinstance(v[1], int) and v[1] > 0
            and len(v[0]) <= v[1]
            and all(isinstance(item, str) for item in v[0])
        ):
            return v
        raise TypeError(
            f"SSTRINGARRAY default must be (tuple, count: int) tuple where the count of tuple doesn't exceed the count of array, got {v!r}"
        )

    @staticmethod
    @tag_registry.expander("SSTRINGARRAY")
    def _(name: str, preset):
        value, size = preset
        padded = list(value) + [""] * (size - len(value))
        return [
            (f"{name}", TypeSpec(f"SSTRING[{size}]", padded))
        ]

