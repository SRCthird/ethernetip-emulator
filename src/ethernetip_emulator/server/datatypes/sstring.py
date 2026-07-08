# Copyright 2026 Merck KGaA, Darmstadt, Germany and/or its affiliates.
# All rights reserved

# src/server/datatypes/sstring.py
from __future__ import annotations
from typing import TYPE_CHECKING, Any
from src.ethernetip_emulator.server.datatypes.templates import Basic
from src.ethernetip_emulator.server.device import actions

if TYPE_CHECKING:
    from src.ethernetip_emulator.server.actions import AttributeActions

@actions.datatype
class Sstring(Basic):
    def __init__(self, parent: AttributeActions):
        super().__init__(parent)

    @staticmethod
    def type_validator(v: Any) -> str:
        if not isinstance(v, str):
            raise TypeError(f"SSTRING default must be str, got {type(v).__name__!r}: {v!r}")
        return v
