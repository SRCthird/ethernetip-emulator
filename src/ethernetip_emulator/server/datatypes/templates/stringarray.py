# Copyright 2026 Merck KGaA, Darmstadt, Germany and/or its affiliates.
# All rights reserved

# src/server/datatypes/templates/stringarray.py
from __future__ import annotations
from typing import TYPE_CHECKING, Any, List

if TYPE_CHECKING:
    from src.ethernetip_emulator.server.actions import AttributeActions

class StringArray:
    def __init__(self, parent: AttributeActions):
        self.parent = parent

    def _is_zero(self, v: str) -> bool:
        return v == ""

    def on_set_hook(self, tag_name: str, attr: Any, key: Any, value: Any) -> None:
        pass

    def on_change(self, name_prefix: str, callback=None, *, defer=False, key=None):
        return self.parent.on_change(name_prefix, callback, defer=defer, key=key)

    def get_val(self, name_prefix: str, key: slice | None) -> List[str]:
        key = key or self._full_slice(name_prefix)
        data_tag = self.parent._lookup(name_prefix)
        if data_tag is None:
            return []
        return data_tag[key]

    def set_val(self, name_prefix: str, key: slice | None, value: List[str]):
        key = key or self._full_slice(name_prefix)
        data_tag = self.parent._lookup(name_prefix)
        if data_tag is None:
            return
        data_tag[key] = value if isinstance(value, list) else [value]

    def size(self, name_prefix: str) -> int | None:
        data_tag = self.parent._lookup(name_prefix)
        if data_tag is None:
            return None
        return len(data_tag)

    def _full_slice(self, name_prefix: str) -> slice | None:
        n = self.size(name_prefix)
        return slice(0, n) if n is not None else None

    def append(self, name_prefix: str, value: str, key: slice | None = None) -> bool:
        key = key or self._full_slice(name_prefix)
        lst = self.get_val(name_prefix, key)
        for i, item in enumerate(lst):
            if self._is_zero(item):
                self.set_val(name_prefix, slice(i, i + 1), [value])
                return True
        return False

    def prepend(self, name_prefix: str, value: str, key: slice | None = None) -> bool:
        key = key or self._full_slice(name_prefix)
        lst = self.get_val(name_prefix, key)
        for i in range(len(lst) - 1, -1, -1):
            if self._is_zero(lst[i]):
                self.set_val(name_prefix, slice(i, i + 1), [value])
                return True
        return False

    def pop(self, name_prefix: str, key: slice | None = None) -> str | None:
        key = key or self._full_slice(name_prefix)
        lst = self.get_val(name_prefix, key)
        for i in range(len(lst) - 1, -1, -1):
            if not self._is_zero(lst[i]):
                self.set_val(name_prefix, slice(i, i + 1), [""])
                return lst[i]
        return None

    def insert(self, name_prefix: str, index: int, value: str, key: slice | None = None) -> bool:
        key = key or self._full_slice(name_prefix)
        lst = self.get_val(name_prefix, key)
        if not self._is_zero(lst[-1]):
            return False
        self.set_val(name_prefix, slice(index + 1, len(lst)), lst[index:-1])
        self.set_val(name_prefix, slice(index, index + 1), [value])
        return True

    def remove(self, name_prefix: str, index: int, key: slice | None = None) -> str | None:
        key = key or self._full_slice(name_prefix)
        lst = self.get_val(name_prefix, key)
        if self._is_zero(lst[index]):
            return None
        removed = lst[index]
        self.set_val(name_prefix, slice(index, len(lst) - 1), lst[index + 1:])
        self.set_val(name_prefix, slice(len(lst) - 1, len(lst)), [""])
        return removed

    def count(self, name_prefix: str, key: slice | None = None) -> int:
        key = key or self._full_slice(name_prefix)
        return sum(1 for i in self.get_val(name_prefix, key) if not self._is_zero(i))

    def is_full(self, name_prefix: str, key: slice | None = None) -> bool:
        key = key or self._full_slice(name_prefix)
        return all(not self._is_zero(i) for i in self.get_val(name_prefix, key))

    def is_empty(self, name_prefix: str, key: slice | None = None) -> bool:
        key = key or self._full_slice(name_prefix)
        return all(self._is_zero(i) for i in self.get_val(name_prefix, key))

    def find(self, name_prefix: str, value: str, key: slice | None = None) -> int | None:
        key = key or self._full_slice(name_prefix)
        lst = self.get_val(name_prefix, key)
        for i, item in enumerate(lst):
            if item == value:
                return i
        return None

    def clear(self, name_prefix: str, key: slice | None = None) -> None:
        key = key or self._full_slice(name_prefix)
        lst = self.get_val(name_prefix, key)
        self.set_val(name_prefix, slice(0, len(lst)), [""] * len(lst))
