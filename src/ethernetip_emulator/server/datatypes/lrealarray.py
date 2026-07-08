# Copyright 2026 Merck KGaA, Darmstadt, Germany and/or its affiliates.
# All rights reserved

# src/server/datatypes/lrealarray.py
from __future__ import annotations
from typing import TYPE_CHECKING, Any
from src.ethernetip_emulator.server.datatypes.templates import Basic
from src.ethernetip_emulator.server.device import actions
from src.ethernetip_emulator.server.actions import TypeSpec
from src.ethernetip_emulator.server.tag_specs import tag_registry

if TYPE_CHECKING:
    from src.ethernetip_emulator.server.actions import AttributeActions

@actions.datatype
class LrealArray(Basic):
    def __init__(self, parent: AttributeActions):
        super().__init__(parent)

    @staticmethod
    def type_validator(v: Any):
        if not isinstance(v, tuple):
            raise TypeError(
                f"LREALARRAY default must be a tuple of float, got {type(v).__name__!r}: {v!r}"
            )
        if len(v) == 0:
            raise ValueError("LREALARRAY values must not be empty")
        try:
            return tuple(float(i) for i in v)
        except (TypeError, ValueError) as exc:
            raise TypeError(
                f"LREAL default must be numeric, got {type(v).__name__!r}: {v!r}"
            ) from exc

    @staticmethod
    @tag_registry.expander("LREALARRAY")
    def _(name: str, preset):
        return [
            (f"{name}", TypeSpec(f"LREAL[{len(preset)}]", list(preset)))
        ]
