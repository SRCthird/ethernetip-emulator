# Copyright 2026 Merck KGaA, Darmstadt, Germany and/or its affiliates.
# All rights reserved

# src/server/datatypes/templates/boolarray.py
from __future__ import annotations
from typing import TYPE_CHECKING, Any, List

if TYPE_CHECKING:
    from src.ethernetip_emulator.server.actions import AttributeActions

class BoolArray:
    def __init__(self, parent: AttributeActions):
        self.parent = parent

    def on_set_hook(self, tag_name: str, attr: Any, key: Any, value: Any) -> None:
        pass

    def on_change(self, name_prefix: str, callback=None, *, defer=False, key=None):
        return self.parent.on_change(name_prefix, callback, defer=defer, key=key)

    def get_val(self, name_prefix: str, key: slice | None = None) -> List[bool]:
        key = key or self._full_slice(name_prefix)
        data_tag = self.parent._lookup(name_prefix)
        if data_tag is None:
            return []
        return [bool(v) for v in data_tag[key]]

    def set_val(self, name_prefix: str, value: List[bool], key: slice | None = None) -> None:
        key = key or self._full_slice(name_prefix)
        data_tag = self.parent._lookup(name_prefix)
        if data_tag is None:
            return
        data_tag[key] = [int(v) for v in (value if isinstance(value, list) else [value])]

    def get_bit(self, name_prefix: str, index: int) -> bool | None:
        data_tag = self.parent._lookup(name_prefix)
        if data_tag is None:
            return None
        return bool(data_tag[slice(index, index + 1)][0])

    def set_bit(self, name_prefix: str, index: int, value: bool) -> None:
        self.set_val(name_prefix, [value], slice(index, index + 1))

    def toggle_bit(self, name_prefix: str, index: int) -> bool | None:
        current = self.get_bit(name_prefix, index)
        if current is None:
            return None
        self.set_bit(name_prefix, index, not current)
        return not current

    def size(self, name_prefix: str) -> int | None:
        data_tag = self.parent._lookup(name_prefix)
        if data_tag is None:
            return None
        return len(data_tag)

    def _full_slice(self, name_prefix: str) -> slice | None:
        n = self.size(name_prefix)
        return slice(0, n) if n is not None else None

    def append(self, name_prefix: str, value: bool, key: slice | None = None) -> bool:
        key = key or self._full_slice(name_prefix)
        lst = self.get_val(name_prefix, key)
        for i, item in enumerate(lst):
            if item == 0:
                self.set_val(name_prefix, [value], slice(i,i+1))
                return True
        return False

    def prepend(self, name_prefix: str, value: bool, key: slice | None = None) -> bool:
        key = key or self._full_slice(name_prefix)
        lst = self.get_val(name_prefix, key)
        for i in range(len(lst) - 1, -1, -1):
            if lst[i] == 0:
                self.set_val(name_prefix, [value], slice(i, i + 1))
                return True
        return False

    def pop(self, name_prefix: str, key: slice | None = None) -> int | None:
        key = key or self._full_slice(name_prefix)
        lst = self.get_val(name_prefix, key)
        for i in range(len(lst) - 1, -1, -1):
            if lst[i] != 0:
                self.set_val(name_prefix, [False], slice(i, i + 1))
                return lst[i]
        return None

    def insert(self, name_prefix: str, index: int, value: bool, key: slice | None = None) -> bool:
        key = key or self._full_slice(name_prefix)
        lst = self.get_val(name_prefix, key)
        if lst[-1] != 0:
            return False
        self.set_val(name_prefix, lst[index:-1], slice(index + 1, len(lst)))
        self.set_val(name_prefix, [value], slice(index, index + 1))
        return True

    def remove(self, name_prefix: str, index: int, key: slice | None = None) -> int | None:
        key = key or self._full_slice(name_prefix)
        lst = self.get_val(name_prefix, key)
        if lst[index] == 0:
            return None
        removed = lst[index]
        self.set_val(name_prefix, lst[index + 1:], slice(index, len(lst) - 1))
        self.set_val(name_prefix, [False], slice(len(lst) - 1, len(lst)))
        return removed

    def count(self, name_prefix: str, key: slice | None = None) -> int:
        key = key or self._full_slice(name_prefix)
        return sum(self.get_val(name_prefix, key))

    def count_clear(self, name_prefix: str, key: slice | None = None) -> int:
        key = key or self._full_slice(name_prefix)
        lst = self.get_val(name_prefix, key)
        return len(lst) - sum(lst)

    def has_any(self, name_prefix: str, key: slice | None = None) -> bool:
        key = key or self._full_slice(name_prefix)
        return any(self.get_val(name_prefix, key))

    def is_full(self, name_prefix: str, key: slice | None = None) -> bool:
        key = key or self._full_slice(name_prefix)
        return all(self.get_val(name_prefix, key))

    def is_empty(self, name_prefix: str, key: slice | None = None) -> bool:
        key = key or self._full_slice(name_prefix)
        return not any(self.get_val(name_prefix, key))

    def find(self, name_prefix: str, value: int, key: slice | None = None) -> int | None:
        key = key or self._full_slice(name_prefix)
        lst = self.get_val(name_prefix, key)
        for i, item in enumerate(lst):
            if item == value:
                return i
        return None

    def clear(self, name_prefix: str, key: slice | None = None) -> None:
        key = key or self._full_slice(name_prefix)
        lst = self.get_val(name_prefix, key)
        self.set_val(name_prefix, [False] * len(lst), slice(0, len(lst)))

    def invert(self, name_prefix: str, key: slice | None = None) -> None:
        key = key or self._full_slice(name_prefix)
        lst = self.get_val(name_prefix, key)
        self.set_val(name_prefix, [not v for v in lst], slice(0, len(lst)))
