# Copyright 2026 Merck KGaA, Darmstadt, Germany and/or its affiliates.
# All rights reserved

# src/server/datatypes/udint.py
from __future__ import annotations
from typing import TYPE_CHECKING, Any
from src.ethernetip_emulator.server.datatypes.templates import Basic
from src.ethernetip_emulator.server.device import actions

if TYPE_CHECKING:
    from src.ethernetip_emulator.server.actions import AttributeActions

@actions.datatype
class Udint(Basic):
    MAX: int = 4_294_967_295
    MIN: int = 0 

    def __init__(self, parent: AttributeActions):
        super().__init__(parent)

    @staticmethod
    def type_validator(v: Any) -> int:
        n = int(v)
        if not (actions.udint.MIN <= n <= actions.udint.MAX):
            raise ValueError(f"UDINT default {n} is outside [{actions.udint.MIN}, {actions.udint.MAX}]")
        return n
