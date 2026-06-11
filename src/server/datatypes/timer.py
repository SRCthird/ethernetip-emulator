# Copyright 2026 Merck KGaA, Darmstadt, Germany and/or its affiliates.
# All rights reserved

# src/server/actions/timer.py
from __future__ import annotations
from typing import TYPE_CHECKING, Any, Callable, List, Tuple
import time
from src.server.device import actions

from src.server.tag_specs import tag_registry

if TYPE_CHECKING:
    from src.server.actions import AttributeActions

@actions.datatype
class Timer:
    def __init__(self, parent):
        self.parent = parent

    @staticmethod
    @tag_registry.expander("TIMER")
    def _(name: str, preset: int) -> List[Tuple[str, str, Any]]:
        return [
            (f"{name}.PRE", "DINT", preset),
            (f"{name}.ACC", "DINT", 0),
            (f"{name}.EN",  "BOOL", 0),
            (f"{name}.TT",  "BOOL", 0),
            (f"{name}.DN",  "BOOL", 0),
        ]

    def on_set_hook(self, tag_name: str, attr: Any, key: Any, value: Any) -> None:
        pass

    def start(
        self,
        tag_prefix: str,
        *,
        period: float = 0.1,
        key: Any = 0,
        preset_ms: int | None = None,
        initial_delay: float = 1.0,
        enable: str | Callable[[], bool] | None = None,
    ) -> "AttributeActions":
        def worker() -> None:
            self.run_worker(
                tag_prefix=tag_prefix,
                period=period,
                key=key,
                preset_ms=preset_ms,
                initial_delay=initial_delay,
                enable=enable,
            )
        return self.parent._start_worker(f"{tag_prefix}-timer", worker)

    def run_worker(
        self,
        *,
        tag_prefix: str,
        period: float,
        key: Any,
        preset_ms: int | None,
        initial_delay: float,
        enable: str | Callable[[], bool] | None = None,
    ) -> None:
        acc_tag = f"{tag_prefix}.ACC"
        pre_tag = f"{tag_prefix}.PRE"
        en_tag  = f"{tag_prefix}.EN"
        tt_tag  = f"{tag_prefix}.TT"
        dn_tag  = f"{tag_prefix}.DN"

        if initial_delay > 0:
            self.parent._sleep(initial_delay)

        if preset_ms is not None:
            pre_attr = self.parent._lookup(pre_tag)
            if pre_attr is not None:
                self.parent._write_attr(pre_attr, key, preset_ms)

        was_enabled = False
        t_start: float | None = None

        acc_attr = 0
        pre_attr = 0
        en_attr  = 0
        tt_attr  = 0
        dn_attr  = 0
        while not self.parent._stop.is_set():
            acc_attr = self.parent._lookup(acc_tag)
            pre_attr = self.parent._lookup(pre_tag)
            en_attr  = self.parent._lookup(en_tag)
            tt_attr  = self.parent._lookup(tt_tag)
            dn_attr  = self.parent._lookup(dn_tag)

            if acc_attr is None or pre_attr is None:
                self.parent._sleep(period)
                continue

            if enable is None:
                gate_open = True
            elif callable(enable):
                gate_open = bool(enable())
            else:
                gate_attr = self.parent._lookup(enable)
                gate_open = bool(self.parent._read_attr(gate_attr, key)) if gate_attr is not None else False

            if was_enabled and not gate_open:
                t_start = None
                for attr, val in [
                    (acc_attr, 0), (en_attr, 0), (tt_attr, 0), (dn_attr, 0),
                ]:
                    if attr is not None:
                        self.parent._write_attr(attr, key, val)
                was_enabled = False
                self.parent._sleep(period)
                continue

            if not gate_open:
                self.parent._sleep(period)
                continue

            if not was_enabled:
                t_start = time.monotonic()
                was_enabled = True
                if en_attr is not None:
                    self.parent._write_attr(en_attr, key, 1)

            pre = self.parent._read_attr(pre_attr, key) or 0
            elapsed_ms = int((time.monotonic() - t_start) * 1000) if t_start is not None else 0
            acc = min(elapsed_ms, pre) if pre > 0 else elapsed_ms
            self.parent._write_attr(acc_attr, key, acc)

            if pre > 0 and elapsed_ms >= pre:
                if tt_attr is not None:
                    self.parent._write_attr(tt_attr, key, 0)
                if dn_attr is not None:
                    self.parent._write_attr(dn_attr, key, 1)
            else:
                if tt_attr is not None:
                    self.parent._write_attr(tt_attr, key, 1)
                if dn_attr is not None:
                    self.parent._write_attr(dn_attr, key, 0)

            self.parent._sleep(period)

        for attr in [acc_attr, en_attr, tt_attr, dn_attr]:
            if attr is not None:
                self.parent._write_attr(attr, key, 0)

    def reset(self, tag_prefix: str, *, key: Any = 0) -> None:
        for tag in [
            f"{tag_prefix}.ACC",
            f"{tag_prefix}.EN",
            f"{tag_prefix}.TT",
            f"{tag_prefix}.DN",
            f"{tag_prefix}.RES",
        ]:
            attr = self.parent._lookup(tag)
            if attr is not None:
                self.parent._write_attr(attr, key, 0)

