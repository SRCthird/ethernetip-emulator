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
    def __init__(self, parent: AttributeActions):
        self.parent = parent

    @staticmethod
    def type_validator(v: Any):
        if not isinstance(v, tuple):
            raise TypeError(
                f"SSTRINGARRAY default values must be a tuple of str, got {type(v).__name__!r}: {v!r}"
            )
        if len(v) == 0:
            raise ValueError(
                f"SSTRINGARRAY values must not be empty"
            )
        bad = [i for i, item in enumerate(v) if not isinstance(item, str)]
        if bad:
            raise TypeError(
                f"SSTRINGARRAY values must all be str; non-str at indices {bad}: "
                f"{[v[i] for i in bad]!r}"
            )
        return v


    @staticmethod
    @tag_registry.expander("SSTRINGARRAY")
    def _(name: str, preset):
        return [
            (f"{name}", TypeSpec(f"SSTRING[{len(preset)}]", list(preset)))
        ]
