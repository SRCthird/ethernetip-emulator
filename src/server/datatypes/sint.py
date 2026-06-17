# Copyright 2026 Merck KGaA, Darmstadt, Germany and/or its affiliates.
# All rights reserved

# src/server/actions/sint.py
from __future__ import annotations
from typing import TYPE_CHECKING, Any
from src.server.device import actions

if TYPE_CHECKING:
    from src.server.actions import AttributeActions

@actions.datatype
class Sint:
    def __init__(self, parent: AttributeActions):
        self.parent = parent

    @staticmethod
    def type_validator(v: Any) -> int:
        n = int(v)
        if not (-128 <= n <= 127):
            raise ValueError(f"SINT default {n} is outside [-128, 127]")
        return n
