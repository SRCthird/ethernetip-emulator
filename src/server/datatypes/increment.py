# Copyright 2026 Merck KGaA, Darmstadt, Germany and/or its affiliates.
# All rights reserved

# src/server/actions/increment.py
from __future__ import annotations
from typing import TYPE_CHECKING, Any
from src.server.device import actions

if TYPE_CHECKING:
    from src.server.actions import AttributeActions

@actions.datatype
class Increment:
    def __init__(self, parent):
        self.parent = parent

    @staticmethod
    def type_validator(v: Any) -> int:
        raise TypeError(f"INCREMENT is not a valid type. Use SINT, INT, or DINT instead.")

    def on_set_hook(self, tag_name: str, attr: Any, key: Any, value: Any) -> None:
        pass

    def start(
        self,
        tag_name: str,
        *,
        period: float = 1.0,
        key: Any = 0,
        increment: int = 1,
        wrap: int | None = None,
        initial_delay: float = 1.0,
        start: int | None = None,
    ) -> "AttributeActions":
        def worker() -> None:
            self.run_worker(
                tag_name=tag_name,
                period=period,
                key=key,
                start=start,
                increment=increment,
                wrap=wrap,
                initial_delay=initial_delay,
            )
        return self.parent._start_worker(f"{tag_name}-increment", worker)

    def run_worker(
        self,
        *,
        tag_name: str,
        period: float,
        key: Any,
        start: int | None,
        increment: int,
        wrap: int | None,
        initial_delay: float,
    ) -> None:
        if initial_delay > 0:
            self.parent._sleep(initial_delay)

        n: int | None = start

        while not self.parent._stop.is_set():
            attr = self.parent._lookup(tag_name)
            if attr is None:
                self.parent._sleep(period)
                continue

            if n is None:
                n = self.parent._read_attr(attr, key) or 0

            n += increment

            if wrap is not None:
                n %= wrap

            self.parent._write_attr(attr, key, n)
            self.parent._sleep(period)

    def increment(self, tag_name: str, *, increment: int = 1, key: Any = 0) -> None:
        attr = self.parent._lookup(tag_name)
        n: int = self.parent._read_attr(attr, key) or 0
        n += increment
        if attr:
            self.parent._write_attr(attr, key, n)

    def decrement(self, tag_name: str, decrement: int = 1, *, key: Any = 0) -> None:
        attr = self.parent._lookup(tag_name)
        n: int = self.parent._read_attr(attr, key) or 0
        n -= decrement
        if attr:
            self.parent._write_attr(attr, key, n)

    def reset(self, tag_name: str, *, default: int = 0, key: Any = 0) -> None:
        attr = self.parent._lookup(tag_name)
        if attr:
            self.parent._write_attr(attr, key, default)

