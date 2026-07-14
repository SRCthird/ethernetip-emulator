# Copyright 2026 Merck KGaA, Darmstadt, Germany and/or its affiliates.
# All rights reserved

# src/ethernetip_emulator/server/datatypes/dintarray.py
from __future__ import annotations
from typing import TYPE_CHECKING, Any
from . import templates
from ..device import actions
from ..actions import TypeSpec
from ..tag_specs import tag_registry

if TYPE_CHECKING:
    from ..actions import AttributeActions

@actions.datatype
class DintArray(templates.NumericArray):
    def __init__(self, parent: AttributeActions):
        super().__init__(parent)

    @staticmethod
    def type_validator(v: Any):
        if not isinstance(v, tuple):
            raise TypeError(
                f"DINTARRAY default values must be a tuple of int, got {type(v).__name__!r}: {v!r}"
            )
        if len(v) == 0:
            raise ValueError(
                f"DINTARRAY values must not be empty"
            )
        not_int = [i for i, n in enumerate(v) if not isinstance(n, int)]
        if not_int:
            raise TypeError(
                f"DINTARRAY values must all be int; non-int at indices {not_int}: "
                f"{[v[i] for i in not_int]!r}"
            )
        out_of_range = [i for i, n in enumerate(v) if not (actions.int.MIN <= n <= actions.int.MAX)]
        if out_of_range:
            raise ValueError(
                f"DINTARRAY values outside [{actions.dint.MIN}, {actions.dint.MAX}] at indices {out_of_range}: "
                f"{[v[i] for i in out_of_range]!r}"
            )
        return v


    @staticmethod
    @tag_registry.expander("DINTARRAY")
    def _(name: str, preset):
        return [
            (f"{name}", TypeSpec(f"DINT[{len(preset)}]", list(preset)))
        ]
