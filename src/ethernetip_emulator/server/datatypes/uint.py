# Copyright 2026 Merck KGaA, Darmstadt, Germany and/or its affiliates.
# All rights reserved

# src/ethernetip_emulator/server/datatypes/uint.py
from __future__ import annotations
from typing import TYPE_CHECKING, Any
from .templates import Basic
from ..device import actions

if TYPE_CHECKING:
    from ..actions import AttributeActions


@actions.datatype
class Uint(Basic):
    MAX = 65_535
    MIN = 0

    def __init__(self, parent: AttributeActions):
        super().__init__(parent)

    @staticmethod
    def type_validator(v: Any) -> int:
        n = int(v)
        if not (actions.uint.MIN <= n <= actions.uint.MAX):
            raise ValueError(
                f"UINT default {n} is outside [{actions.uint.MIN}, {actions.uint.MAX}]"
            )
        return n
