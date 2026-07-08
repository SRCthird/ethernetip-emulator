# Copyright 2026 Merck KGaA, Darmstadt, Germany and/or its affiliates.
# All rights reserved

# src/server/datatypes/ulint.py
from __future__ import annotations
from typing import TYPE_CHECKING, Any
from src.ethernetip_emulator.server.datatypes.templates import Basic
from src.ethernetip_emulator.server.device import actions

if TYPE_CHECKING:
    from src.ethernetip_emulator.server.actions import AttributeActions

@actions.datatype
class Ulint(Basic):
    MAX = 18_446_744_073_709_551_615
    MIN = 0
    def __init__(self, parent: AttributeActions):
        super().__init__(parent)

    @staticmethod
    def type_validator(v: Any) -> int:
        n = int(v)
        if not (actions.ulint.MIN <= n <= actions.ulint.MAX):
            raise ValueError(f"ULINT default {n} is outside [{actions.ulint.MIN}, {actions.ulint.MAX}]")
        return n
