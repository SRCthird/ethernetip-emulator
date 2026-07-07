# Copyright 2026 Merck KGaA, Darmstadt, Germany and/or its affiliates.
# All rights reserved

# src/server/datatypes/realarray.py
from __future__ import annotations
from typing import TYPE_CHECKING, Any
from src.server.datatypes.templates import Basic
from src.server.device import actions
from src.server.actions import TypeSpec
from src.server.tag_specs import tag_registry

if TYPE_CHECKING:
    from src.server.actions import AttributeActions

@actions.datatype
class RealArray(Basic):
    def __init__(self, parent: AttributeActions):
        self.parent = parent

    @staticmethod
    def type_validator(v: Any):
        if not isinstance(v, tuple):
            raise TypeError(
                f"REALARRAY default must be a tuple of float, got {type(v).__name__!r}: {v!r}"
            )
        if len(v) == 0:
            raise ValueError("REALARRAY values must not be empty")
        try:
            return tuple(float(i) for i in v)
        except (TypeError, ValueError) as exc:
            raise TypeError(
                f"REAL default must be numeric, got {type(v).__name__!r}: {v!r}"
            ) from exc

    @staticmethod
    @tag_registry.expander("REALARRAY")
    def _(name: str, preset):
        return [
            (f"{name}", TypeSpec(f"REAL[{len(preset)}]", list(preset)))
        ]
