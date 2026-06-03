# Copyright 2026 Merck KGaA, Darmstadt, Germany and/or its affiliates.
# All rights reserved

# src/server/actions/counter.py
from __future__ import annotations
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from src.server.actions.actions import AttributeActions

class String:
    def __init__(self, parent: AttributeActions):
        self.parent = parent

    def get_val(self, name_prefix: str, key: Any):
        data_tag = self.parent._lookup(f"{name_prefix}.DATA")
        if data_tag is None:
            return None
        return data_tag[key]
        
    
    def set_val(self, name_prefix: str, key: Any, value: str):
        data_tag = self.parent._lookup(f"{name_prefix}.DATA")
        if data_tag is None:
            return
        data_tag[key] = value
        self._len_helper(name_prefix, key, value)

    def get_len(self, name_prefix: str, key: Any) -> int:
        len_tag = self.parent._lookup(f"{name_prefix}.LEN")
        if len_tag is None:
            return 0
        len_value = len_tag[key]
        return len_value[0] if isinstance(len_value, list) else len_value

    def _len_helper(self, name_prefix: str, key: Any, value: str) -> None:
        data_tag = self.parent._lookup(f"{name_prefix}.DATA")
        len_tag = self.parent._lookup(f"{name_prefix}.LEN")

        if data_tag is None or len_tag is None:
            return

        new_value = value[0] if isinstance(value, list) else value

        try:
            len_tag[key] = len(new_value) 
        except Exception:
            if hasattr(len_tag, "value"):
                len_tag.value =len(new_value) 

