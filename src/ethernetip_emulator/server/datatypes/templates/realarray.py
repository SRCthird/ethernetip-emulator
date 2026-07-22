# Copyright 2026 Merck KGaA, Darmstadt, Germany and/or its affiliates.
# All rights reserved

# src/ethernetip_emulator/server/datatypes/templates/realarray.py
from __future__ import annotations
from typing import TYPE_CHECKING, Any, List

if TYPE_CHECKING:
    from ...actions import AttributeActions

_ZERO = 0.0
_TOL = 1e-9


class RealArray:
    def __init__(self, parent: AttributeActions):
        self.parent = parent

    @staticmethod
    def type_validator(v: Any) -> Any:
        return v

    def _is_zero(self, v: float) -> bool:
        return abs(v) < _TOL

    def on_set_hook(
        self, tag_name: str, attr: Any, key: slice, value: List[Any]
    ) -> None:
        pass

    def on_change(self, name_prefix: str, callback=None, *, key=None, defer=False):
        if key is None:
            new_key = self._full_slice(name_prefix) or slice(0, 1)
        else:
            new_key = key
        return self.parent.on_change(name_prefix, callback, key=new_key, defer=defer)

    def get_val(self, name_prefix: str, key: slice | None = None) -> List[float]:
        key = key or self._full_slice(name_prefix)
        data_tag = self.parent._lookup(name_prefix)
        if data_tag is None:
            return []
        return data_tag[key]

    def set_val(self, name_prefix: str, value: List[float], key: slice | None = None):
        key = key or self._full_slice(name_prefix)
        data_tag = self.parent._lookup(name_prefix)
        if data_tag is None:
            return
        v = value if isinstance(value, list) else [value]
        self.type_validator(v)
        data_tag[key] = v

    def size(self, name_prefix: str) -> int | None:
        data_tag = self.parent._lookup(name_prefix)
        if data_tag is None:
            return None
        return len(data_tag)

    def _full_slice(self, name_prefix: str) -> slice | None:
        n = self.size(name_prefix)
        return slice(0, n) if n is not None else None

    def append(self, name_prefix: str, value: float, key: slice | None = None) -> bool:
        key = key or self._full_slice(name_prefix)
        lst = self.get_val(name_prefix, key)
        for i, item in enumerate(lst):
            if self._is_zero(item):
                self.set_val(name_prefix, [value], slice(i, i + 1))
                return True
        return False

    def prepend(self, name_prefix: str, value: float, key: slice | None = None) -> bool:
        key = key or self._full_slice(name_prefix)
        lst = self.get_val(name_prefix, key)
        for i in range(len(lst) - 1, -1, -1):
            if self._is_zero(lst[i]):
                self.set_val(name_prefix, [value], slice(i, i + 1))
                return True
        return False

    def pop(self, name_prefix: str, key: slice | None = None) -> float | None:
        key = key or self._full_slice(name_prefix)
        lst = self.get_val(name_prefix, key)
        for i in range(len(lst) - 1, -1, -1):
            if not self._is_zero(lst[i]):
                self.set_val(name_prefix, [_ZERO], slice(i, i + 1))
                return lst[i]
        return None

    def insert(
        self, name_prefix: str, index: int, value: float, key: slice | None = None
    ) -> bool:
        key = key or self._full_slice(name_prefix)
        lst = self.get_val(name_prefix, key)
        if not self._is_zero(lst[-1]):
            return False
        self.set_val(name_prefix, lst[index:-1], slice(index + 1, len(lst)))
        self.set_val(name_prefix, [value], slice(index, index + 1))
        return True

    def remove(
        self, name_prefix: str, index: int, key: slice | None = None
    ) -> float | None:
        key = key or self._full_slice(name_prefix)
        lst = self.get_val(name_prefix, key)
        if self._is_zero(lst[index]):
            return None
        removed = lst[index]
        self.set_val(name_prefix, lst[index + 1 :], slice(index, len(lst) - 1))
        self.set_val(name_prefix, [_ZERO], slice(len(lst) - 1, len(lst)))
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

    def find(
        self, name_prefix: str, value: float, key: slice | None = None
    ) -> int | None:
        key = key or self._full_slice(name_prefix)
        lst = self.get_val(name_prefix, key)
        for i, item in enumerate(lst):
            if abs(item - value) < _TOL:
                return i
        return None

    def clear(self, name_prefix: str, key: slice | None = None) -> None:
        key = key or self._full_slice(name_prefix)
        lst = self.get_val(name_prefix, key)
        self.set_val(name_prefix, [_ZERO] * len(lst), slice(0, len(lst)))
