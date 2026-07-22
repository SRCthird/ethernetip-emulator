# Copyright 2026 Merck KGaA, Darmstadt, Germany and/or its affiliates.
# All rights reserved

# src/ethernetip_emulator/server/actions/dint.py
from __future__ import annotations
from typing import TYPE_CHECKING, Any
from .templates import Basic
from ..device import actions

if TYPE_CHECKING:
    from ..actions import AttributeActions


@actions.datatype
class Dint(Basic):
    MAX: int = 2_147_483_647
    MIN: int = -2_147_483_648

    def __init__(self, parent: AttributeActions):
        super().__init__(parent)

    @staticmethod
    def type_validator(v: Any) -> int:
        n = int(v)
        if not (actions.dint.MIN <= n <= actions.dint.MAX):
            raise ValueError(
                f"DINT default {n} is outside [{actions.dint.MIN}, {actions.dint.MAX}]"
            )
        return n
