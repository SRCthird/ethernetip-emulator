# Copyright 2026 Merck KGaA, Darmstadt, Germany and/or its affiliates.
# All rights reserved

# src/ethernetip_emulator/server/datatypes/realarray.py
from __future__ import annotations
from typing import TYPE_CHECKING, Any
from . import templates
from ..device import actions
from ..actions import TypeSpec
from ..tag_specs import tag_registry

if TYPE_CHECKING:
    from ..actions import AttributeActions


@actions.datatype
class RealArray(templates.NumericArray):
    def __init__(self, parent: AttributeActions):
        self.parent = parent

    @staticmethod
    def type_validator(v: Any):
        if not isinstance(v, list):
            raise TypeError(
                f"REALARRAY default must be a list of float, got {type(v).__name__!r}: {v!r}"
            )
        if len(v) == 0:
            raise ValueError("REALARRAY values must not be empty")
        try:
            return [float(i) for i in v]
        except (TypeError, ValueError) as exc:
            raise TypeError(
                f"REAL default must be numeric, got {type(v).__name__!r}: {v!r}"
            ) from exc

    @staticmethod
    @tag_registry.expander("REALARRAY")
    def _(name: str, preset):
        return [(f"{name}", TypeSpec(f"REAL[{len(preset)}]", list(preset)))]
