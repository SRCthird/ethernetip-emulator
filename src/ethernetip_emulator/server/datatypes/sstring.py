# Copyright 2026 Merck KGaA, Darmstadt, Germany and/or its affiliates.
# All rights reserved

# src/ethernetip_emulator/server/datatypes/sstring.py
from __future__ import annotations
from typing import TYPE_CHECKING, Any
from .templates import Basic
from ..device import actions

if TYPE_CHECKING:
    from ..actions import AttributeActions


@actions.datatype
class Sstring(Basic):
    def __init__(self, parent: AttributeActions):
        super().__init__(parent)

    @staticmethod
    def type_validator(v: Any) -> str:
        if not isinstance(v, str):
            raise TypeError(
                f"SSTRING default must be str, got {type(v).__name__!r}: {v!r}"
            )
        return v
