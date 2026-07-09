# Copyright 2026 Merck KGaA, Darmstadt, Germany and/or its affiliates.
# All rights reserved

# src/server/datatypes/string.py
from __future__ import annotations
from typing import TYPE_CHECKING, Any, override
from src.ethernetip_emulator.server.datatypes.templates import Basic
from src.ethernetip_emulator.server.tag_specs import tag_registry
from src.ethernetip_emulator.server.device import actions

if TYPE_CHECKING:
    from src.ethernetip_emulator.server.actions import AttributeActions

@actions.datatype
class String(Basic):
    def __init__(self, parent: AttributeActions):
        super().__init__(parent)

    @staticmethod
    def type_validator(v: Any) -> str:
        if not isinstance(v, str):
            raise TypeError(f"STRING default must be str, got {type(v).__name__!r}: {v!r}")
        return v
        
    @staticmethod
    @tag_registry.expander("STRING")
    def _(name: str, preset: str):
        return [
            (f"{name}.LEN", actions.type.DINT(len(preset))),
            (f"{name}.DATA", actions.type.SSTRING(preset)),
        ]

    @override
    def on_set_hook(self, tag_name: str, attr: Any, value: Any, key: slice | None = None) -> None:
        if tag_name.endswith(".DATA"):
            name_prefix = tag_name[: -len(".DATA")]
            self._len_helper(name_prefix, value, key)

    @override
    def on_change(self, name_prefix: str, callback=None, *, defer=False, key=None):
        return self.parent.on_change(f"{name_prefix}.DATA", callback, defer=defer, key=key)

    @override
    def get_val(self, name_prefix: str, key: slice | None = None) -> str:
        data_tag = self.parent._lookup(f"{name_prefix}.DATA")
        if data_tag is None:
            return ""
        return data_tag[0]
    
    @override
    def set_val(self, name_prefix: str, value: str, key: slice | None = None):
        try:
            super().set_val(f"{name_prefix}.DATA", value, key)
        except TypeError as e:
            pass
        self._len_helper(name_prefix, value, key)

    def get_len(self, name_prefix: str, key: slice | None = None) -> int:
        len_tag = self.parent._lookup(f"{name_prefix}.LEN")
        if len_tag is None:
            return 0
        len_value = len_tag[key]
        return len_value[0] if isinstance(len_value, list) else len_value

    def _len_helper(self, name_prefix: str, value: str, key: slice | None = None) -> None:
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
