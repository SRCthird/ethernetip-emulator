# Copyright 2026 Merck KGaA, Darmstadt, Germany and/or its affiliates.
# All rights reserved

# src/server/actions/lint.py
from __future__ import annotations
from typing import TYPE_CHECKING, Any
from src.server.device import actions

if TYPE_CHECKING:
    from src.server.actions import AttributeActions

@actions.datatype
class Lint:
    MAX = 9_223_372_036_854_775_807
    MIN = -9_223_372_036_854_775_808
    def __init__(self, parent: AttributeActions):
        self.parent = parent

    @staticmethod
    def type_validator(v: Any) -> int:
        n = int(v)
        if not (actions.lint.MIN <= n <= actions.lint.MAX):
            raise ValueError(f"LINT default {n} is outside [{actions.lint.MIN}, {actions.lint.MAX}]")
        return n
