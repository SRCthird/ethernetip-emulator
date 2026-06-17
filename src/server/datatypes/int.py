# Copyright 2026 Merck KGaA, Darmstadt, Germany and/or its affiliates.
# All rights reserved

# src/server/actions/int.py
from __future__ import annotations
from typing import TYPE_CHECKING, Any
from src.server.device import actions

if TYPE_CHECKING:
    from src.server.actions import AttributeActions

@actions.datatype
class Int:
    def __init__(self, parent: AttributeActions):
        self.parent = parent

    @staticmethod
    def type_validator(v: Any) -> int:
        n = int(v)
        if not (-32_768 <= n <= 32_767):
            raise ValueError(f"INT default {n} is outside [-32768, 32767]")
        return n
