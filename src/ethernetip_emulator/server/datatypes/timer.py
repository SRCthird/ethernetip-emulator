# Copyright 2026 Merck KGaA, Darmstadt, Germany and/or its affiliates.
# All rights reserved

# src/server/datatypes/timer.py
from __future__ import annotations
from typing import TYPE_CHECKING, Any, Callable
import time
from src.ethernetip_emulator.server.device import actions
from src.ethernetip_emulator.server.tag_specs import tag_registry

if TYPE_CHECKING:
    from src.ethernetip_emulator.server.actions import AttributeActions

class TimerIsDoingSomething:
    def __init__(self, dn_value: bool, register_fn: Callable) -> None:
        self._dn_value = dn_value
        self._register_fn = register_fn

    def __bool__(self) -> bool:
        return self._dn_value

    def __call__(
        self, fn: Callable[[Any, Any, Any], None]
    ) -> Callable[[Any, Any, Any], None]:
        self._register_fn(fn)
        return fn

class TimerIsTiming(TimerIsDoingSomething):
    pass

class TimerIsDone(TimerIsDoingSomething):
    pass

class TimerIsEnabled(TimerIsDoingSomething):
    pass


@actions.datatype
class Timer:
    def __init__(self, parent: "AttributeActions"):
        self.parent = parent

    @staticmethod
    def type_validator(v: Any) -> int:
        if not isinstance(v, int):
            raise TypeError(f"TIMER default must be int, got {type(v).__name__!r}: {v!r}")
        return v

    @staticmethod
    @tag_registry.expander("TIMER")
    def _(name: str, preset: int):
        actions.timer.start(name, enable=f"{name}.EN")
        return [
            (f"{name}.PRE", actions.type.DINT(preset)),
            (f"{name}.ACC", actions.type.DINT(0)),
            (f"{name}.EN",  actions.type.BOOL(False)),
            (f"{name}.TT",  actions.type.BOOL(False)),
            (f"{name}.DN",  actions.type.BOOL(False)),
        ]

    def on_set_hook(self, tag_name: str, attr: Any, value: Any, key: slice | None = None) -> None:
        pass

    def get_preset(self, tag_prefix: str, key: Any):
        data_tag = self.parent._lookup(f"{tag_prefix}.PRE")
        if data_tag is None:
            return None
        return data_tag[0]

    def set_preset(self, tag_prefix: str, key: Any, value: int):
        attr = self.parent._lookup(f"{tag_prefix}.PRE")
        if attr:
            self.parent._write_attr(attr, value, key)

    def get_accumulator(self, tag_prefix: str, key: slice | None = None):
        data_tag = self.parent._lookup(f"{tag_prefix}.ACC")
        if data_tag is None:
            return None
        return data_tag[0]

    def is_enabled(
        self,
        tag_prefix: str,
        *,
        key: slice | None = None,
    ) -> TimerIsEnabled:
        tag = f"{tag_prefix}.EN"

        attr = self.parent._lookup(tag)
        value = bool(self.parent._read_attr(attr, key)) if attr is not None else False

        def register_fn(fn: Callable) -> None:
            self.parent.on_change(tag, fn)

        return TimerIsEnabled(value, register_fn)

    def is_done(
        self,
        tag_prefix: str,
        *,
        key: slice | None = None,
    ) -> TimerIsDone:
        tag = f"{tag_prefix}.DN"

        attr = self.parent._lookup(tag)
        value = bool(self.parent._read_attr(attr, key)) if attr is not None else False

        def register_fn(fn: Callable) -> None:
            self.parent.on_change(tag, fn)

        return TimerIsDone(value, register_fn)

    def is_timing(
        self,
        tag_prefix: str,
        *,
        key: slice | None = None,
    ) -> TimerIsTiming:
        tag = f"{tag_prefix}.TT"

        attr = self.parent._lookup(tag)
        value = bool(self.parent._read_attr(attr, key)) if attr is not None else False

        def register_fn(fn: Callable) -> None:
            self.parent.on_change(tag, fn)

        return TimerIsTiming(value, register_fn)

    def start(
        self,
        tag_prefix: str,
        *,
        period: float = 0.1,
        key: slice | None = None,
        preset_ms: int | None = None,
        initial_delay: float = 1.0,
        enable: str | Callable[[], bool] | None = None,
    ) -> "AttributeActions":
        def _launch() -> None:
            def worker() -> None:
                self.run_worker(
                    tag_prefix=tag_prefix,
                    period=period,
                    key=key,
                    preset_ms=preset_ms,
                    initial_delay=initial_delay,
                    enable=enable,
                )
            self.parent._start_worker(f"{tag_prefix}-timer", worker)

        if self.parent._entered:
            _launch()
        else:
            self.parent._pending.append(_launch)

        return self.parent

    def run_worker(
        self,
        *,
        tag_prefix: str,
        period: float,
        key: slice | None = None,
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
                self.parent._write_attr(pre_attr, preset_ms, key)

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
                        self.parent._write_attr(attr, val, key)
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
                    self.parent._write_attr(en_attr, 1, key)

            pre = self.parent._read_attr(pre_attr, key) or 0
            elapsed_ms = int((time.monotonic() - t_start) * 1000) if t_start is not None else 0
            acc = min(elapsed_ms, pre) if pre > 0 else elapsed_ms
            self.parent._write_attr(acc_attr, acc, key)

            if pre > 0 and elapsed_ms >= pre:
                if tt_attr is not None:
                    self.parent._write_attr(tt_attr, 0, key)
                if dn_attr is not None:
                    self.parent._write_attr(dn_attr, 1, key)
            else:
                if tt_attr is not None:
                    self.parent._write_attr(tt_attr, 1, key)
                if dn_attr is not None:
                    self.parent._write_attr(dn_attr, 0, key)

            self.parent._sleep(period)

        for attr in [acc_attr, en_attr, tt_attr, dn_attr]:
            if attr is not None:
                self.parent._write_attr(attr, 0, key)

    def reset(self, tag_prefix: str, *, key: slice | None = None) -> None:
        for tag in [
            f"{tag_prefix}.ACC",
            f"{tag_prefix}.EN",
            f"{tag_prefix}.TT",
            f"{tag_prefix}.DN",
            f"{tag_prefix}.RES",
        ]:
            attr = self.parent._lookup(tag)
            if attr is not None:
                self.parent._write_attr(attr, 0, key)
