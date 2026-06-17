# Copyright 2026 Merck KGaA, Darmstadt, Germany and/or its affiliates.
# All rights reserved

# src/server/actions/sstringarray.py
from __future__ import annotations
from typing import TYPE_CHECKING, Any
from src.server.device import actions
from src.server.actions import TypeSpec
from src.server.tag_specs import tag_registry

if TYPE_CHECKING:
    from src.server.actions import AttributeActions

@actions.datatype
class SstringArray:
    MAX = 127
    MIN = 0 

    def __init__(self, parent: AttributeActions):
        self.parent = parent

    @staticmethod
    def type_validator(v: Any) -> int:
        n = int(v)
        if not (actions.sstringarray.MIN <= n <= actions.sstringarray.MAX):
            raise ValueError(f"STRINGARRAY default size {n} is outside [0, 127]")
        return n

    @staticmethod
    @tag_registry.expander("SSTRINGARRAY")
    def _(name: str, preset):
        return [
            (f"{name}", TypeSpec(f"SSTRING[{preset}]", None))
        ]
