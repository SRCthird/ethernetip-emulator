# Copyright 2026 Merck KGaA, Darmstadt, Germany and/or its affiliates.
# All rights reserved

# src/server/actions/ulint.py
from __future__ import annotations
from typing import TYPE_CHECKING, Any
from src.server.device import actions

if TYPE_CHECKING:
    from src.server.actions import AttributeActions

@actions.datatype
class Ulint:
    MAX = 18_446_744_073_709_551_615
    MIN = 0
    def __init__(self, parent: AttributeActions):
        self.parent = parent

    @staticmethod
    def type_validator(v: Any) -> int:
        n = int(v)
        if not (actions.ulint.MIN <= n <= actions.ulint.MAX):
            raise ValueError(f"ULINT default {n} is outside [{actions.ulint.MIN}, {actions.ulint.MAX}]")
        return n
