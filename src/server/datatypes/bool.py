# Copyright 2026 Merck KGaA, Darmstadt, Germany and/or its affiliates.
# All rights reserved

# src/server/actions/bool.py
from __future__ import annotations
from typing import TYPE_CHECKING, Any
from src.server.device import actions

if TYPE_CHECKING:
    from src.server.actions import AttributeActions

@actions.datatype
class Bool:
    def __init__(self, parent: AttributeActions):
        self.parent = parent

    @staticmethod
    def type_validator(v: Any) -> bool:
        try:
            return bool(v)
        except (TypeError, ValueError) as exc:
            raise TypeError(
                f"BOOL default must be boolean, got {type(v).__name__!r}: {v!r}"
            ) from exc

    def on_set_hook(self, tag_name: str, attr: Any, key: Any, value: Any) -> None:
        pass

    def on_change(self, name_prefix: str, callback=None, *, key=None):
        return self.parent.on_change(name_prefix, callback, key=key)

    def get_val(self, name_prefix: str, key: Any):
        data_tag = self.parent._lookup(name_prefix)
        if data_tag is None:
            return None
        return data_tag[key]

    def set_val(self, name_prefix: str, key: Any, value: bool):
        data_tag = self.parent._lookup(name_prefix)
        if data_tag is None:
            return
        data_tag[key] = value if isinstance(value, list) else [value]

