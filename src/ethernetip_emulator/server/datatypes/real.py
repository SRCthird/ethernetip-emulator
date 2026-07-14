# Copyright 2026 Merck KGaA, Darmstadt, Germany and/or its affiliates.
# All rights reserved

# src/ethernetip_emulator/server/datatypes/real.py
from __future__ import annotations
from typing import TYPE_CHECKING, Any
from .templates import Basic
from ..device import actions

if TYPE_CHECKING:
    from ..actions import AttributeActions

@actions.datatype
class Real(Basic):
    def __init__(self, parent: AttributeActions):
        super().__init__(parent)

    @staticmethod
    def type_validator(v: Any) -> float:
        try:
            return float(v)
        except (TypeError, ValueError) as exc:
            raise TypeError(
                f"REAL default must be numeric, got {type(v).__name__!r}: {v!r}"
            ) from exc
