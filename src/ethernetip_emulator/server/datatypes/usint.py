# Copyright 2026 Merck KGaA, Darmstadt, Germany and/or its affiliates.
# All rights reserved

# src/server/datatypes/usint.py
from __future__ import annotations
from typing import TYPE_CHECKING, Any
from src.ethernetip_emulator.server.datatypes.templates import Basic
from src.ethernetip_emulator.server.device import actions

if TYPE_CHECKING:
    from src.ethernetip_emulator.server.actions import AttributeActions

@actions.datatype
class Usint(Basic):
    MAX = 255
    MIN = 0

    def __init__(self, parent: AttributeActions):
        super().__init__(parent)

    @staticmethod
    def type_validator(v: Any) -> int:
        n = int(v)
        if not (actions.usint.MIN <= n <= actions.usint.MAX):
            raise ValueError(f"USINT default {n} is outside [{actions.usint.MIN}, {actions.usint.MAX}]")
        return n
