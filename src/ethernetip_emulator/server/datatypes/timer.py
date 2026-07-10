# Copyright 2026 Merck KGaA, Darmstadt, Germany and/or its affiliates.
# All rights reserved

# src/ethernetip_emulator/server/datatypes/timer.py
from __future__ import annotations
from typing import TYPE_CHECKING, Any, Callable, List
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
        self,
        fn: Callable[[Any, Any, Any], None],
        *,
        rising_edge: bool = True,
    ) -> Callable[[Any, Any, Any], None]:
        if rising_edge:
            def _guarded(attr: Any, key: Any, value: Any) -> None:
                if not value[0]:
                    return
                fn(attr, key, value)
            _guarded.__name__ = getattr(fn, "__name__", "_guarded")
            self._register_fn(_guarded)
            return fn
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

    def get_preset(self, tag_prefix: str, key: slice | None = slice(0, 1)):
        return actions.dint.get_val(f"{tag_prefix}.PRE", key)

    def set_preset(self, tag_prefix: str, value: int, key: slice | None = slice(0, 1)):
        actions.dint.set_val(f"{tag_prefix}.PRE", value, key)

    def get_accumulator(self, tag_prefix: str, key: slice | None = slice(0, 1)):
        return actions.dint.get_val(f"{tag_prefix}.ACC", key)

    def set_accumulator(self, tag_prefix: str, value: int, key: slice | None = slice(0, 1)):
        actions.dint.set_val(f"{tag_prefix}.ACC", value, key)

    def is_enabled(
        self,
        tag_prefix: str,
        *,
        key: slice = slice(0, 1),
        defer = False,
    ) -> TimerIsEnabled:
        tag = f"{tag_prefix}.EN"

        attr = self.parent._lookup(tag)
        raw = self.parent._read_attr(attr, key) if attr is not None else None
        value = bool(raw[0]) if raw is not None else False

        def register_fn(fn: Callable) -> None:
            self.parent.on_change(tag, fn, defer=defer)

        return TimerIsEnabled(value, register_fn)

    def is_done(
        self,
        tag_prefix: str,
        *,
        defer = False,
    ) -> TimerIsDone:
        tag = f"{tag_prefix}.DN"
        value = bool(actions.bool.get_val(tag))

        def register_fn(fn: Callable) -> None:
            self.parent.on_change(tag, fn, defer=defer)

        return TimerIsDone(value, register_fn)

    def is_timing(
        self,
        tag_prefix: str,
        *,
        key: slice = slice(0, 1),
        defer = False,
    ) -> TimerIsTiming:
        tag = f"{tag_prefix}.TT"

        attr = self.parent._lookup(tag)
        raw = self.parent._read_attr(attr, key) if attr is not None else None
        value = bool(raw[0]) if raw is not None else False

        def register_fn(fn: Callable) -> None:
            self.parent.on_change(tag, fn, defer=defer)

        return TimerIsTiming(value, register_fn)

    def start(
        self,
        tag_prefix: str,
        *,
        period: float = 0.1,
        key: slice = slice(0, 1),
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
        key: slice,
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
                self.parent._write_attr(pre_attr, key, [preset_ms])

        was_enabled = False
        t_start: float | None = None

        acc_attr = None
        pre_attr = None
        en_attr  = None
        tt_attr  = None
        dn_attr  = None
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
                raw = self.parent._read_attr(gate_attr, key) if gate_attr is not None else None
                gate_open = bool(raw[0]) if raw is not None else False

            if was_enabled and not gate_open:
                t_start = None
                for attr, val in [
                    (acc_attr, 0), (en_attr, 0), (tt_attr, 0), (dn_attr, 0),
                ]:
                    if attr is not None:
                        self.parent._write_attr(attr, key, [val])
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
                    self.parent._write_attr(en_attr, key, [1])

            pre_raw = self.parent._read_attr(pre_attr, key)
            pre = int(pre_raw[0]) if pre_raw is not None else 0
            elapsed_ms = int((time.monotonic() - t_start) * 1000) if t_start is not None else 0
            acc = min(elapsed_ms, pre) if pre > 0 else elapsed_ms
            self.parent._write_attr(acc_attr, key, [acc])

            if pre > 0 and elapsed_ms >= pre:
                if tt_attr is not None:
                    self.parent._write_attr(tt_attr, key, [0])
                if dn_attr is not None:
                    self.parent._write_attr(dn_attr, key, [1])
            else:
                if tt_attr is not None:
                    self.parent._write_attr(tt_attr, key, [1])
                if dn_attr is not None:
                    self.parent._write_attr(dn_attr, key, [0])

            self.parent._sleep(period)

        for attr in [acc_attr, en_attr, tt_attr, dn_attr]:
            if attr is not None:
                self.parent._write_attr(attr, key, [0])

    def reset(self, tag_prefix: str, *, key: slice = slice(0, 1)) -> None:
        for tag in [
            f"{tag_prefix}.ACC",
            f"{tag_prefix}.EN",
            f"{tag_prefix}.TT",
            f"{tag_prefix}.DN",
            f"{tag_prefix}.RES",
        ]:
            attr = self.parent._lookup(tag)
            if attr is not None:
                self.parent._write_attr(attr, key, [0])
