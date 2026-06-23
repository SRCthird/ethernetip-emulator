# Copyright 2026 Merck KGaA, Darmstadt, Germany and/or its affiliates.
# All rights reserved

# src/server/actions/lreal.py
from __future__ import annotations
from typing import TYPE_CHECKING, Any
from src.server.device import actions

if TYPE_CHECKING:
    from src.server.actions import AttributeActions

@actions.datatype
class LReal:
    def __init__(self, parent: AttributeActions):
        self.parent = parent

    @staticmethod
    def type_validator(v: Any) -> float:
        try:
            return float(v)
        except (TypeError, ValueError) as exc:
            raise TypeError(
                    f"LREAL default must be numeric, got {type(v).__name__!r}: {v!r}"
            ) from exc
