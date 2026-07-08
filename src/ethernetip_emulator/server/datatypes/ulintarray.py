# Copyright 2026 Merck KGaA, Darmstadt, Germany and/or its affiliates.
# All rights reserved

# src/server/datatypes/ulintarray.py
from __future__ import annotations
from typing import TYPE_CHECKING, Any
from src.ethernetip_emulator.server.datatypes.templates import Basic
from src.ethernetip_emulator.server.device import actions
from src.ethernetip_emulator.server.actions import TypeSpec
from src.ethernetip_emulator.server.tag_specs import tag_registry

if TYPE_CHECKING:
    from src.ethernetip_emulator.server.actions import AttributeActions

@actions.datatype
class UlintArray(Basic):
    def __init__(self, parent: AttributeActions):
        super().__init__(parent)

    @staticmethod
    def type_validator(v: Any):
        if not isinstance(v, tuple):
            raise TypeError(
                f"ULINTARRAY default values must be a tuple of int, got {type(v).__name__!r}: {v!r}"
            )
        if len(v) == 0:
            raise ValueError(
                f"ULINTARRAY values must not be empty"
            )
        not_int = [i for i, n in enumerate(v) if not isinstance(n, int)]
        if not_int:
            raise TypeError(
                f"ULINTARRAY values must all be int; non-int at indices {not_int}: "
                f"{[v[i] for i in not_int]!r}"
            )
        out_of_range = [i for i, n in enumerate(v) if not (actions.ulint.MIN <= n <= actions.ulint.MAX)]
        if out_of_range:
            raise ValueError(
                f"ULINTARRAY values outside [{actions.ulint.MIN}, {actions.ulint.MAX}] at indices {out_of_range}: "
                f"{[v[i] for i in out_of_range]!r}"
            )
        return v


    @staticmethod
    @tag_registry.expander("ULINTARRAY")
    def _(name: str, preset):
        return [
            (f"{name}", TypeSpec(f"ULINT[{len(preset)}]", list(preset)))
        ]
