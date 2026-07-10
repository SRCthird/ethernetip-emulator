# Copyright 2026 Merck KGaA, Darmstadt, Germany and/or its affiliates.
# All rights reserved

# src/ethernetip_emulator/server/datatypes/boolarray.py
from __future__ import annotations
from typing import TYPE_CHECKING, Any
from src.ethernetip_emulator.server.datatypes import templates
from src.ethernetip_emulator.server.device import actions
from src.ethernetip_emulator.server.actions import TypeSpec
from src.ethernetip_emulator.server.tag_specs import tag_registry

if TYPE_CHECKING:
    from src.ethernetip_emulator.server.actions import AttributeActions

@actions.datatype
class BoolArray(templates.BoolArray):
    def __init__(self, parent: AttributeActions):
        super().__init__(parent)

    @staticmethod
    def type_validator(v: Any):
        if not isinstance(v, tuple):
            raise TypeError(
                f"BOOLARRAY default must be a tuple of bool, got {type(v).__name__!r}: {v!r}"
            )
        if len(v) == 0:
            raise ValueError("BOOLARRAY values must not be empty")
        not_bool = [i for i, n in enumerate(v) if not isinstance(n, bool)]
        if not_bool:
            raise TypeError(
                f"BOOLARRAY values must all be bool; non-bool at indices {not_bool}: "
                f"{[v[i] for i in not_bool]!r}"
            )
        return v

    @staticmethod
    @tag_registry.expander("BOOLARRAY")
    def _(name: str, preset):
        return [
            (f"{name}", TypeSpec(f"BOOL[{len(preset)}]", list(preset)))
        ]
