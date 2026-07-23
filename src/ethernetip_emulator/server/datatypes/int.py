# Copyright 2026 Merck KGaA, Darmstadt, Germany and/or its affiliates.
# All rights reserved

# src/ethernetip_emulator/server/datatypes/int.py
from __future__ import annotations
from typing import TYPE_CHECKING, Any
from .templates import Basic
from ..device import actions

if TYPE_CHECKING:
    from ..actions import AttributeActions


@actions.datatype
class Int(Basic):
    MAX = 32_767
    MIN = -32_768

    def __init__(self, parent: AttributeActions):
        super().__init__(parent)

    @staticmethod
    def type_validator(v: Any) -> int:
        n = int(v)
        if not (actions.int.MIN <= n <= actions.int.MAX):
            raise ValueError(
                f"INT default {n} is outside [{actions.int.MIN}, {actions.int.MAX}]"
            )
        return n
