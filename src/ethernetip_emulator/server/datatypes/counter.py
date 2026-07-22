# Copyright 2026 Merck KGaA, Darmstadt, Germany and/or its affiliates.
# All rights reserved


# src/ethernetip_emulator/server/actions/counter.py
from __future__ import annotations
from typing import TYPE_CHECKING, Any, Callable
from ..device import actions
from ..tag_specs import tag_registry

if TYPE_CHECKING:
    from ..actions import AttributeActions


class CounterSignal:
    def __init__(self, value: bool, register_fn: Callable) -> None:
        self._value = value
        self._register_fn = register_fn

    def __bool__(self) -> bool:
        return self._value

    def __call__(
        self,
        fn: Callable[[Any, Any, Any], None] | None = None,
        *,
        rising_edge: bool = True,
    ) -> Callable:
        def _apply(f):
            if rising_edge:

                def _guarded(attr, key, value):
                    if not value[0]:
                        return
                    f(attr, key, value)

                _guarded.__name__ = getattr(f, "__name__", "_guarded")
                self._register_fn(_guarded)
                return f
            self._register_fn(f)
            return f

        if fn is not None:
            return _apply(fn)
        return _apply


class CounterIsDone(CounterSignal):
    pass


class CounterIsReset(CounterSignal):
    pass


@actions.datatype
class Counter:
    def __init__(self, parent: AttributeActions):
        self.parent = parent

    @staticmethod
    def type_validator(v: Any) -> int:
        if isinstance(v, bool) or not isinstance(v, int):
            raise TypeError(
                f"COUNTER default must be int, got {type(v).__name__!r}: {v!r}"
            )
        return v

    @staticmethod
    @tag_registry.expander("COUNTER")
    def _(name: str, preset: int):
        return [
            (f"{name}.PRE", actions.type.DINT(preset)),
            (f"{name}.ACC", actions.type.DINT(0)),
            (f"{name}.CU", actions.type.BOOL(False)),
            (f"{name}.CD", actions.type.BOOL(False)),
            (f"{name}.DN", actions.type.BOOL(False)),
            (f"{name}.OV", actions.type.BOOL(False)),
            (f"{name}.UN", actions.type.BOOL(False)),
            (f"{name}.RES", actions.type.BOOL(False)),
        ]

    def on_set_hook(self, tag_name: str, attr: Any, key: slice, value: Any) -> None:
        if tag_name.endswith(".RES"):
            if not value[0]:
                return
            name_prefix = tag_name[: -len(".RES")]
            self.reset(name_prefix)

    def get_preset_value(self, name_prefix: str, key: slice = slice(0, 1, None)) -> int:
        return actions.dint.get_val(f"{name_prefix}.PRE", key)

    def set_preset_value(
        self, name_prefix: str, value: Any, key: slice = slice(0, 1, None)
    ):
        return actions.dint.set_val(f"{name_prefix}.PRE", value, key)

    def get_accumulated_value(
        self, name_prefix: str, key: slice = slice(0, 1, None)
    ) -> int:
        return actions.dint.get_val(f"{name_prefix}.ACC", key)

    def _set_accumulated_value(
        self, name_prefix: str, value: Any, key: slice = slice(0, 1, None)
    ):
        return actions.dint.set_val(f"{name_prefix}.ACC", value, key)

    def get_count_up_bit(
        self, name_prefix: str, key: slice = slice(0, 1, None)
    ) -> bool:
        return actions.bool.get_val(f"{name_prefix}.CU", key)

    def _set_count_up_bit(
        self, name_prefix: str, value: bool, key: slice = slice(0, 1, None)
    ) -> bool:
        return actions.bool.set_val(f"{name_prefix}.CU", value, key)

    def get_count_down_bit(
        self, name_prefix: str, key: slice = slice(0, 1, None)
    ) -> bool:
        return actions.bool.get_val(f"{name_prefix}.CD", key)

    def get_done_bit(self, name_prefix: str, key: slice = slice(0, 1, None)) -> bool:
        return actions.bool.get_val(f"{name_prefix}.DN", key)

    def _set_done_bit(
        self, name_prefix: str, value: bool, key: slice = slice(0, 1, None)
    ) -> bool:
        return actions.bool.set_val(f"{name_prefix}.DN", value, key)

    def get_overflow_bit(
        self, name_prefix: str, key: slice = slice(0, 1, None)
    ) -> bool:
        return actions.bool.get_val(f"{name_prefix}.OV", key)

    def _set_overflow_bit(
        self, name_prefix: str, value: bool, key: slice = slice(0, 1, None)
    ) -> bool:
        return actions.bool.set_val(f"{name_prefix}.OV", value, key)

    def get_underflow_bit(
        self, name_prefix: str, key: slice = slice(0, 1, None)
    ) -> bool:
        return actions.bool.get_val(f"{name_prefix}.UN", key)

    def _set_underflow_bit(
        self, name_prefix: str, value: bool, key: slice = slice(0, 1, None)
    ) -> bool:
        return actions.bool.set_val(f"{name_prefix}.UN", value, key)

    def get_reset_bit(self, name_prefix: str, key: slice = slice(0, 1, None)) -> bool:
        return actions.bool.get_val(f"{name_prefix}.RES", key)

    def _set_reset_bit(
        self, name_prefix: str, value: bool, key: slice = slice(0, 1, None)
    ) -> bool:
        return actions.bool.set_val(f"{name_prefix}.RES", value, key)

    def is_done(self, tag_prefix: str, *, defer=False) -> CounterIsDone:
        tag = f"{tag_prefix}.DN"
        value = bool(actions.bool.get_val(tag))

        def register_fn(fn: Callable) -> None:
            self.parent.on_change(tag, fn, defer=defer)

        return CounterIsDone(value, register_fn)

    def is_reset(self, tag_prefix: str, *, defer=False) -> CounterIsReset:
        tag = f"{tag_prefix}.RES"
        value = bool(actions.bool.get_val(tag))

        def register_fn(fn: Callable) -> None:
            self.parent.on_change(tag, fn, defer=defer)

        return CounterIsReset(value, register_fn)

    def start(
        self,
        tag_prefix: str,
        *,
        period: float = 1.0,
        preset: int | None = None,
        initial_delay: float = 1.0,
        enable: str | Callable[[], bool] | None = None,
    ) -> AttributeActions:
        def worker() -> None:
            self.run_worker(
                tag_prefix=tag_prefix,
                period=period,
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
        preset: int | None,
        initial_delay: float,
        enable: str | Callable[[], bool] | None = None,
    ) -> None:
        if initial_delay > 0:
            self.parent._sleep(initial_delay)

        if preset is not None:
            self.set_preset_value(tag_prefix, preset)

        self._set_count_up_bit(tag_prefix, True)

        while not self.parent._stop.is_set():
            acc = self.get_accumulated_value(tag_prefix)
            pre = self.get_preset_value(tag_prefix)

            if enable is not None:
                if callable(enable):
                    gate_open = bool(enable())
                else:
                    gate_open = actions.bool.get_val(enable)

                if not gate_open:
                    self.parent._sleep(period)
                    continue

            if acc >= actions.dint.MAX:
                self._set_overflow_bit(tag_prefix, True)
                self._set_accumulated_value(tag_prefix, 0)
                self.parent._sleep(period)
                self._set_overflow_bit(tag_prefix, False)
                continue

            acc += 1
            self._set_accumulated_value(tag_prefix, acc)

            if pre > 0 and acc >= pre:
                self._set_done_bit(tag_prefix, True)
                self.parent._sleep(period)
                self._set_accumulated_value(tag_prefix, 0)
                self._set_done_bit(tag_prefix, False)
                continue

            self.parent._sleep(period)

        self._set_count_up_bit(tag_prefix, False)

    def increment(self, tag_prefix: str) -> None:
        acc = self.get_accumulated_value(tag_prefix)
        pre = self.get_preset_value(tag_prefix)

        if acc >= actions.dint.MAX:
            self._set_overflow_bit(tag_prefix, True)
            self._set_accumulated_value(tag_prefix, 0)
            return

        acc += 1
        self._set_accumulated_value(tag_prefix, acc)

        if self.get_overflow_bit(tag_prefix):
            self._set_overflow_bit(tag_prefix, False)

        if pre > 0 and acc >= pre:
            self._set_done_bit(tag_prefix, True)

    def decrement(self, tag_prefix: str) -> None:
        acc = self.get_accumulated_value(tag_prefix)
        pre = self.get_preset_value(tag_prefix)

        if acc <= actions.dint.MIN:
            self._set_underflow_bit(tag_prefix, True)
            self._set_accumulated_value(tag_prefix, 0)
            return

        acc -= 1
        self._set_accumulated_value(tag_prefix, acc)

        if self.get_underflow_bit(tag_prefix):
            self._set_underflow_bit(tag_prefix, False)

        if pre > 0 and acc < pre:
            self._set_done_bit(tag_prefix, False)

    def reset(self, tag_prefix: str) -> None:
        self._set_accumulated_value(tag_prefix, 0)
        self._set_done_bit(tag_prefix, False)
        self._set_overflow_bit(tag_prefix, False)
        self._set_underflow_bit(tag_prefix, False)
        self._set_reset_bit(tag_prefix, False)
