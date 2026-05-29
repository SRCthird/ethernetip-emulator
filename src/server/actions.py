# Copyright 2026 Merck KGaA, Darmstadt, Germany and/or its affiliates.
# All rights reserved

# src/server/actions.py
from __future__ import annotations

import threading
import time
import weakref
from typing import Any, Callable


class AttributeActions:
    DINT_MAX: int = 2_147_483_647
    DINT_MIN: int = -2_147_483_648

    def __init__(
        self,
        *,
        sleep_fn: Callable[[float], None] = time.sleep,
        thread_factory: Callable[..., Any] | None = None,
        logger: Callable[[str], None] = (lambda _: None),
    ) -> None:
        self._stop = threading.Event()
        self._threads: list[threading.Thread] = []
        self._attr_class_ref: weakref.ref[Any] | None = None
        self._sleep = sleep_fn
        self._logger = logger
        self._listeners: dict[
            str, list[tuple[Callable[[Any, Any, Any], None], Any | None]]
        ] = {}
        self._listener_lock = threading.Lock()

        if thread_factory is None:
            def default_thread_factory(**kwargs: Any) -> threading.Thread:
                return threading.Thread(**kwargs)
            thread_factory = default_thread_factory

        self._thread_factory = thread_factory

        self.increment = self.Increment(self)
        self.counter = self.Counter(self)
        self.timer = self.Timer(self)

    def __enter__(self) -> "AttributeActions":
        return self

    def __exit__(
        self,
        exc_type: type | None,
        exc_val: BaseException | None,
        exc_tb: Any | None,
    ) -> None:
        self.stop()
        for t in self._threads:
            t.join()

    def bind(self, attr_class: type) -> "AttributeActions":
        self._attr_class_ref = weakref.ref(attr_class)
        return self

    def _get_attr_class(self) -> Any | None:
        return self._attr_class_ref() if self._attr_class_ref else None

    def _read_attr(self, attr: Any, key: Any) -> int | None:
        try:
            return int(attr[key])
        except Exception:
            val = getattr(attr, "value", None)
            return int(val) if val is not None else None

    def _write_attr(self, attr: Any, key: Any, value: int) -> None:
        try:
            attr[key] = value
        except (TypeError, KeyError, IndexError):
            if hasattr(attr, "value"):
                setattr(attr, "value", value)
            else:
                raise

    def _lookup(self, tag_name: str) -> Any | None:
        attr_class = self._get_attr_class()
        if attr_class is None:
            self._logger(f"AttributeActions: attr_class is None for {tag_name}")
            return None
        attr = getattr(attr_class, "registry", {}).get(tag_name)
        if attr is None:
            self._logger(f"AttributeActions: attr is None for {tag_name}")
        return attr

    def _start_worker(self, name: str, fn: Callable[[], None]) -> "AttributeActions":
        t = self._thread_factory(target=fn, daemon=True, name=name)
        t.start()
        self._threads.append(t)
        return self

    def on_change(
        self,
        tag_name: str,
        callback: Callable[[Any, Any, Any], None],
        *,
        key: Any | None = None,
    ) -> "AttributeActions":
        with self._listener_lock:
            self._listeners.setdefault(tag_name, []).append((callback, key))
        return self

    def remove_listener(
        self,
        tag_name: str,
        callback: Callable[[Any, Any, Any], None],
    ) -> "AttributeActions":
        with self._listener_lock:
            entries = self._listeners.get(tag_name, [])
            self._listeners[tag_name] = [
                (cb, k) for cb, k in entries if cb is not callback
            ]
        return self

    def _fire_listeners(self, tag_name: str, attr: Any, key: Any, value: Any) -> None:
        with self._listener_lock:
            entries = list(self._listeners.get(tag_name, []))

        for callback, key_filter in entries:
            if key_filter is not None and key_filter != key:
                continue
            try:
                callback(attr, key, value)
            except Exception as exc:
                self._logger(
                    f"AttributeActions: listener error for {tag_name}: {exc}"
                )

    class Increment:
        def __init__(self, parent):
            self.parent = parent

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

    class Counter:
        def __init__(self, parent):
            self.parent = parent

        def start(
            self,
            tag_prefix: str,
            *,
            period: float = 1.0,
            key: Any = 0,
            preset: int | None = None,
            initial_delay: float = 1.0,
            enable: str | Callable[[], bool] | None = None,
        ) -> "AttributeActions":
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

    class Timer:
        def __init__(self, parent):
            self.parent = parent

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

    def stop(self) -> None:
        self._stop.set()

    def on_set(self, attr: Any, key: Any, value: Any) -> None:
        tag_name = getattr(attr, "name", None)
        if tag_name is not None:
            self._fire_listeners(tag_name, attr, key, value)
