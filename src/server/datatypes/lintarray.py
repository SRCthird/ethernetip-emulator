# Copyright 2026 Merck KGaA, Darmstadt, Germany and/or its affiliates.
# All rights reserved

# src/server/actions/lintarray.py
from __future__ import annotations
from typing import TYPE_CHECKING, Any
from src.server.device import actions
from src.server.actions import TypeSpec
from src.server.tag_specs import tag_registry

if TYPE_CHECKING:
    from src.server.actions import AttributeActions

@actions.datatype
class LintArray:
    def __init__(self, parent: AttributeActions):
        self.parent = parent

    @staticmethod
    def type_validator(v: Any):
        if not isinstance(v, tuple):
            raise TypeError(
                f"LINTARRAY default values must be a tuple of int, got {type(v).__name__!r}: {v!r}"
            )
        if len(v) == 0:
            raise ValueError(
                f"LINTARRAY values must not be empty"
            )
        not_int = [i for i, n in enumerate(v) if not isinstance(n, int)]
        if not_int:
            raise TypeError(
                f"LINTARRAY values must all be int; non-int at indices {not_int}: "
                f"{[v[i] for i in not_int]!r}"
            )
        out_of_range = [i for i, n in enumerate(v) if not (actions.lint.MIN <= n <= actions.lint.MAX)]
        if out_of_range:
            raise ValueError(
                f"LINTARRAY values outside [{actions.lint.MIN}, {actions.lint.MAX}] at indices {out_of_range}: "
                f"{[v[i] for i in out_of_range]!r}"
            )
        return v


    @staticmethod
    @tag_registry.expander("LINTARRAY")
    def _(name: str, preset):
        return [
            (f"{name}", TypeSpec(f"LINT[{len(preset)}]", list(preset)))
        ]
