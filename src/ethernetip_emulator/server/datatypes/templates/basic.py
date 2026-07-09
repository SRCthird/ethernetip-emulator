# Copyright 2026 Merck KGaA, Darmstadt, Germany and/or its affiliates.
# All rights reserved

# src/server/datatypes/templates/basic.py
from __future__ import annotations
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from src.ethernetip_emulator.server.actions import AttributeActions

class Basic:
    def __init__(self, parent: AttributeActions):
        self.parent = parent

    def on_set_hook(self, tag_name: str, attr: Any, key: Any, value: Any) -> None:
        pass

    def on_change(self, name_prefix: str, callback=None, *, key=None, defer=False):
        return self.parent.on_change(name_prefix, callback, key=key, defer=defer)

    def get_val(self, name_prefix: str, key: slice | None = slice(0, 1, None)) -> Any:
        data_tag = self.parent._lookup(name_prefix)
        if data_tag is None:
            return None
        if len(data_tag[key]) == 1:
            return data_tag[key][0]
        return data_tag[key]

    def set_val(self, name_prefix: str, value: Any, key: slice | None = slice(0, 1, None)):
        data_tag = self.parent._lookup(name_prefix)
        if data_tag is None:
            return
        data_tag[key] = value if isinstance(value, list) else [value]
