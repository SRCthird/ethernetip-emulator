# Copyright 2026 Merck KGaA, Darmstadt, Germany and/or its affiliates.
# All rights reserved

# src/server/actions/uint.py
from __future__ import annotations
from typing import TYPE_CHECKING, Any
from src.server.device import actions

if TYPE_CHECKING:
    from src.server.actions import AttributeActions

@actions.datatype
class Uint:
    MAX = 65_535
    MIN = 0
    def __init__(self, parent: AttributeActions):
        self.parent = parent

    @staticmethod
    def type_validator(v: Any) -> int:
        n = int(v)
        if not (actions.uint.MIN <= n <= actions.uint.MAX):
            raise ValueError(f"UINT default {n} is outside [{actions.uint.MIN}, {actions.uint.MAX}]")
        return n
