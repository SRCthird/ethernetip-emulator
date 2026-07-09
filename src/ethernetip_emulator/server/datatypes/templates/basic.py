# Copyright 2026 Merck KGaA, Darmstadt, Germany and/or its affiliates.
# All rights reserved

# src/server/datatypes/templates/basic.py
from __future__ import annotations
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from src.ethernetip_emulator.server.actions import AttributeActions

class Basic:
    def __init__(self, parent: AttributeActions):
        self.parent = parent

    def on_set_hook(self, tag_name: str, attr: Any, value: Any, key: slice | None = None) -> None:
        pass

    def on_change(self, name_prefix: str, callback: Callable[[Any, Any, Any], None] | None = None, *, defer=False, key: slice | None = None):
        return self.parent.on_change(name_prefix, callback, defer=defer, key=key)

    def get_val(self, name_prefix: str, key: slice | None = None):
        data_tag = self.parent._lookup(name_prefix)
        if data_tag is None:
            return None
        if key is None:
            key = slice(0, len(data_tag))
        return data_tag[key][0]

    def set_val(self, name_prefix: str, value: Any, key: slice | None = None):
        data_tag = self.parent._lookup(name_prefix)
        if data_tag is None:
            return
        if key is None:
            key = slice(0, len(data_tag))
        data_tag[key] = value if isinstance(value, list) else [value]
