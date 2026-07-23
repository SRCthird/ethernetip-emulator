# Copyright 2026 Merck KGaA, Darmstadt, Germany and/or its affiliates.
# All rights reserved

# src/ethernetip_emulator/server/datatypes/timer.py
from __future__ import annotations
from typing import TYPE_CHECKING, Any, Callable
import time
from ..device import actions
from ..tag_specs import tag_registry

if TYPE_CHECKING:
    from ..actions import AttributeActions


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
        if isinstance(v, bool) or not isinstance(v, int):
            raise TypeError(
                f"TIMER default must be int, got {type(v).__name__!r}: {v!r}"
            )
        return v

    @staticmethod
    @tag_registry.expander("TIMER")
    def _(name: str, preset: int):
        actions.timer.start(name, enable=f"{name}.EN")
        return [
            (f"{name}.PRE", actions.type.DINT(preset)),
            (f"{name}.ACC", actions.type.DINT(0)),
            (f"{name}.EN", actions.type.BOOL(False)),
            (f"{name}.TT", actions.type.BOOL(False)),
            (f"{name}.DN", actions.type.BOOL(False)),
        ]

    def on_set_hook(self, tag_name: str, attr: Any, key: Any, value: Any) -> None:
        pass

    def get_preset(self, tag_prefix: str, key: slice | None = slice(0, 1)):
        return actions.dint.get_val(f"{tag_prefix}.PRE", key)

    def set_preset(self, tag_prefix: str, value: int, key: slice | None = slice(0, 1)):
        actions.dint.set_val(f"{tag_prefix}.PRE", value, key)

    def get_accumulator(self, tag_prefix: str, key: slice | None = slice(0, 1)):
        return actions.dint.get_val(f"{tag_prefix}.ACC", key)

    def set_accumulator(
        self, tag_prefix: str, value: int, key: slice | None = slice(0, 1)
    ):
        actions.dint.set_val(f"{tag_prefix}.ACC", value, key)

    def is_enabled(
        self,
        tag_prefix: str,
        *,
        defer=False,
    ) -> TimerIsEnabled:
        tag = f"{tag_prefix}.EN"
        value = actions.bool.get_val(tag)

        def register_fn(fn: Callable) -> None:
            self.parent.on_change(tag, fn, defer=defer)

        return TimerIsEnabled(value, register_fn)

    def is_done(
        self,
        tag_prefix: str,
        *,
        defer=False,
    ) -> TimerIsDone:
        tag = f"{tag_prefix}.DN"
        value = actions.bool.get_val(tag)

        def register_fn(fn: Callable) -> None:
            self.parent.on_change(tag, fn, defer=defer)

        return TimerIsDone(value, register_fn)

    def is_timing(
        self,
        tag_prefix: str,
        *,
        defer=False,
    ) -> TimerIsTiming:
        tag = f"{tag_prefix}.TT"
        value = actions.bool.get_val(tag)

        def register_fn(fn: Callable) -> None:
            self.parent.on_change(tag, fn, defer=defer)

        return TimerIsTiming(value, register_fn)

    def start(
        self,
        tag_prefix: str,
        *,
        period: float = 0.05,
        preset_ms: int | None = None,
        initial_delay: float = 1.0,
        enable: str | Callable[[], bool] | None = None,
    ) -> "AttributeActions":
        def _launch() -> None:
            def worker() -> None:
                self.run_worker(
                    tag_prefix=tag_prefix,
                    period=period,
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
        preset_ms: int | None,
        initial_delay: float,
        enable: str | Callable[[], bool] | None = None,
    ) -> None:
        if initial_delay > 0:
            self.parent._sleep(initial_delay)

        if preset_ms is not None:
            self.set_preset(tag_prefix, preset_ms)

        was_enabled = False
        t_start: float | None = None
        prev_gate: bool = False

        while not self.parent._stop.is_set():
            if enable is None:
                gate_open = True
            elif callable(enable):
                gate_open = bool(enable())
            else:
                gate_open = actions.bool.get_val(enable)

            if prev_gate and not gate_open:
                t_start = None
                was_enabled = False
                actions.dint.set_val(f"{tag_prefix}.ACC", 0)
                actions.bool.set_val(f"{tag_prefix}.TT", False)
                actions.bool.set_val(f"{tag_prefix}.DN", False)
                prev_gate = False
                self.parent._sleep(period)
                continue

            prev_gate = gate_open

            if not gate_open:
                self.parent._sleep(period)
                continue

            if not was_enabled:
                t_start = time.monotonic()
                was_enabled = True

            pre = self.get_preset(tag_prefix)
            elapsed_ms = (
                int((time.monotonic() - t_start) * 1000) if t_start is not None else 0
            )
            acc = min(elapsed_ms, pre) if pre > 0 else elapsed_ms
            self.set_accumulator(tag_prefix, acc)

            if pre > 0 and elapsed_ms >= pre:
                actions.bool.set_val(f"{tag_prefix}.TT", False)
                actions.bool.set_val(f"{tag_prefix}.DN", True)
            else:
                actions.bool.set_val(f"{tag_prefix}.TT", True)
                actions.bool.set_val(f"{tag_prefix}.DN", False)

            self.parent._sleep(period)

    def reset(self, tag_prefix: str) -> None:
        actions.dint.set_val(f"{tag_prefix}.ACC", 0)
        actions.bool.set_val(f"{tag_prefix}.EN", False)
        actions.bool.set_val(f"{tag_prefix}.TT", False)
        actions.bool.set_val(f"{tag_prefix}.DN", False)
