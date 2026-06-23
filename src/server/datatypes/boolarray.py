# Copyright 2026 Merck KGaA, Darmstadt, Germany and/or its affiliates.
# All rights reserved

# src/server/actions/boolarray.py
from __future__ import annotations
from typing import TYPE_CHECKING, Any
from src.server.device import actions
from src.server.actions import TypeSpec
from src.server.tag_specs import tag_registry

if TYPE_CHECKING:
    from src.server.actions import AttributeActions

@actions.datatype
class BoolArray:
    def __init__(self, parent: AttributeActions):
        self.parent = parent

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
