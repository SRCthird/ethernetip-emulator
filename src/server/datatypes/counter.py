# Copyright 2026 Merck KGaA, Darmstadt, Germany and/or its affiliates.
# All rights reserved

# src/server/actions/counter.py
from __future__ import annotations
from typing import TYPE_CHECKING, Any, Callable, List, Tuple
from src.server.device import actions
from src.server.tag_specs import tag_registry

if TYPE_CHECKING:
    from src.server.actions import AttributeActions

@actions.datatype
class Counter:
    def __init__(self, parent: AttributeActions):
        self.parent = parent

    @staticmethod
    @tag_registry.expander("COUNTER")
    def _(name: str, preset: int) -> List[Tuple[str, str, Any]]:
        return [
            (f"{name}.PRE", "DINT", preset),
            (f"{name}.ACC", "DINT", 0),
            (f"{name}.CU",  "BOOL", 0),
            (f"{name}.CD",  "BOOL", 0),
            (f"{name}.DN",  "BOOL", 0),
            (f"{name}.OV",  "BOOL", 0),
            (f"{name}.UN",  "BOOL", 0),
            (f"{name}.RES", "BOOL", 0),
        ]

    def on_set_hook(self, tag_name: str, attr: Any, key: Any, value: Any) -> None:
        if tag_name.endswith(".RES"):
            name_prefix = tag_name[: -len(".RES")]
            self.reset(name_prefix, key=key)

    def start(
        self,
        tag_prefix: str,
        *,
        period: float = 1.0,
        key: Any = 0,
        preset: int | None = None,
        initial_delay: float = 1.0,
        enable: str | Callable[[], bool] | None = None,
    ) -> AttributeActions:
        def worker() -> None:
            self.run_worker(
                tag_prefix=tag_prefix,
                period=period,
                key=key,
                preset=preset,
                initial_delay=initial_delay,
                enable=enable,
            )
        return self.parent._start_worker(f"{tag_prefix}-counter", worker)

    def run_worker(
        self,
        *,
        tag_prefix: str,
        period: float,
        key: Any,
        preset: int | None,
        initial_delay: float,
        enable: str | Callable[[], bool] | None = None,
    ) -> None:
        acc_tag = f"{tag_prefix}.ACC"
        pre_tag = f"{tag_prefix}.PRE"
        cu_tag  = f"{tag_prefix}.CU"
        dn_tag  = f"{tag_prefix}.DN"
        ov_tag  = f"{tag_prefix}.OV"

        if initial_delay > 0:
            self.parent._sleep(initial_delay)

        if preset is not None:
            pre_attr = self.parent._lookup(pre_tag)
            if pre_attr is not None:
                self.parent._write_attr(pre_attr, key, preset)

        cu_attr = self.parent._lookup(cu_tag)
        if cu_attr is not None:
            self.parent._write_attr(cu_attr, key, 1)

        acc_attr = self.parent._lookup(acc_tag)
        acc: int = self.parent._read_attr( acc_attr, key ) or 0

        while not self.parent._stop.is_set():
            acc_attr = self.parent._lookup(acc_tag)
            pre_attr = self.parent._lookup(pre_tag)
            dn_attr  = self.parent._lookup(dn_tag)
            ov_attr  = self.parent._lookup(ov_tag)

            if acc_attr is None or pre_attr is None:
                self.parent._sleep(period)
                continue

            pre: int = self.parent._read_attr(pre_attr, key) or 0

            if enable is not None:
                if callable(enable):
                    gate_open = bool(enable())
                else:
                    gate_attr = self.parent._lookup(enable)
                    gate_open = bool(self.parent._read_attr(gate_attr, key)) if gate_attr is not None else False

                if not gate_open:
                    self.parent._sleep(period)
                    continue

            if acc >= self.parent.DINT_MAX:
                if ov_attr is not None:
                    self.parent._write_attr(ov_attr, key, 1)
                acc = 0
                self.parent._write_attr(acc_attr, key, acc)
                self.parent._sleep(period)
                if ov_attr is not None:
                    self.parent._write_attr(ov_attr, key, 0)
                continue

            acc += 1
            self.parent._write_attr(acc_attr, key, acc)

            if pre > 0 and acc >= pre:
                if dn_attr is not None:
                    self.parent._write_attr(dn_attr, key, 1)
                self.parent._sleep(period)
                acc = 0
                self.parent._write_attr(acc_attr, key, acc)
                if dn_attr is not None:
                    self.parent._write_attr(dn_attr, key, 0)
                continue

            self.parent._sleep(period)

        cu_attr = self.parent._lookup(cu_tag)
        if cu_attr is not None:
            self.parent._write_attr(cu_attr, key, 0)


    def increment(self, tag_prefix: str, *, key: Any = 0) -> None:
        acc_attr = self.parent._lookup(f"{tag_prefix}.ACC")
        pre_attr = self.parent._lookup(f"{tag_prefix}.PRE")
        dn_attr  = self.parent._lookup(f"{tag_prefix}.DN")
        ov_attr  = self.parent._lookup(f"{tag_prefix}.OV")

        if acc_attr is None or pre_attr is None:
            self.parent._logger(f"AttributeActions.counter_increment: essential tags missing for {tag_prefix}")
            return

        acc = self.parent._read_attr(acc_attr, key) or 0
        pre = self.parent._read_attr(pre_attr, key) or 0

        if acc >= self.parent.DINT_MAX:
            if ov_attr is not None:
                self.parent._write_attr(ov_attr, key, 1)
            acc = 0
            self.parent._write_attr(acc_attr, key, acc)
            return

        acc += 1
        self.parent._write_attr(acc_attr, key, acc)

        if ov_attr is not None:
            self.parent._write_attr(ov_attr, key, 0)

        if pre > 0 and acc >= pre:
            if dn_attr is not None:
                self.parent._write_attr(dn_attr, key, 1)

    def decrement(self, tag_prefix: str, *, key: Any = 0) -> None:
        acc_attr = self.parent._lookup(f"{tag_prefix}.ACC")
        pre_attr = self.parent._lookup(f"{tag_prefix}.PRE")
        dn_attr  = self.parent._lookup(f"{tag_prefix}.DN")
        un_attr  = self.parent._lookup(f"{tag_prefix}.UN")

        if acc_attr is None:
            self.parent._logger(f"AttributeActions.counter.decrement: ACC tag missing for {tag_prefix}")
            return

        acc = self.parent._read_attr(acc_attr, key) or 0
        pre = self.parent._read_attr(pre_attr, key) or 0 if pre_attr is not None else 0

        if acc <= self.parent.DINT_MIN:
            if un_attr is not None:
                self.parent._write_attr(un_attr, key, 1)
            acc = 0
            self.parent._write_attr(acc_attr, key, acc)
            return

        acc -= 1
        self.parent._write_attr(acc_attr, key, acc)

        if un_attr is not None:
            self.parent._write_attr(un_attr, key, 0)

        if dn_attr is not None and pre > 0 and acc < pre:
            self.parent._write_attr(dn_attr, key, 0)

    def reset(self, tag_prefix: str, *, key: Any = 0) -> None:
        for tag, value in [
            (f"{tag_prefix}.ACC", 0),
            (f"{tag_prefix}.DN",  0),
            (f"{tag_prefix}.OV",  0),
            (f"{tag_prefix}.UN",  0),
            (f"{tag_prefix}.RES", 0),
        ]:
            attr = self.parent._lookup(tag)
            if attr is not None:
                self.parent._write_attr(attr, key, value)

