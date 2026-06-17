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
        if not isinstance(v, tuple) or len(v) != 2:
            raise TypeError(
                f"SSTRINGARRAY default must be a 2-tuple (values: tuple[str, ...], size: int), got {type(v).__name__!r}: {v!r}"
            )
        values, size = v
        if not isinstance(values, tuple):
            raise TypeError(
                f"SSTRINGARRAY default values must be a tuple of str, got {type(values).__name__!r}: {values!r}"
            )
        if not isinstance(size, int) or size <= 0:
            raise TypeError(
                f"SSTRINGARRAY size must be a positive int, got {type(size).__name__!r}: {size!r}"
            )
        if len(values) > size:
            raise ValueError(
                f"SSTRINGARRAY values length {len(values)} exceeds declared size {size}"
            )
        bad = [i for i, item in enumerate(values) if not isinstance(item, str)]
        if bad:
            raise TypeError(
                f"SSTRINGARRAY values must all be str; non-str at indices {bad}: "
                f"{[values[i] for i in bad]!r}"
            )
        return v


    @staticmethod
    @tag_registry.expander("SSTRINGARRAY")
    def _(name: str, preset):
        value, size = preset
        padded = list(value) + [""] * (size - len(value))
        return [
            (f"{name}", TypeSpec(f"SSTRING[{size}]", padded))
        ]

