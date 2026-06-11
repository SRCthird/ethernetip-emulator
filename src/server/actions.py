# Copyright 2026 Merck KGaA, Darmstadt, Germany and/or its affiliates.
# All rights reserved

# src/server/actions/actions.py
from __future__ import annotations

import threading
import time
import weakref
from typing import Any, Callable, overload, Type

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
        self._pending: list[Callable[[], None]] = []
        self._entered: bool = False
        self._datatypes: dict[str, Any] = {}

        if thread_factory is None:
            def default_thread_factory(**kwargs: Any) -> threading.Thread:
                return threading.Thread(**kwargs)
            thread_factory = default_thread_factory
        self._thread_factory = thread_factory

    def register_datatype(
        self,
        name: str,
        cls: Type[Any],
    ) -> "AttributeActions":
        instance = cls(self)
        self._datatypes[name] = instance
        return self

    def datatype(
        self,
        name_or_cls: str | Type[Any],
    ) -> "AttributeActions | Callable[[Type[Any]], Type[Any]]":
        if isinstance(name_or_cls, str):
            name = name_or_cls
            def decorator(cls: Type[Any]) -> Type[Any]:
                self.register_datatype(name, cls)
                return cls
            return decorator
        else:
            cls = name_or_cls
            self.register_datatype(cls.__name__.lower(), cls)
            return cls

    def __getattr__(self, name: str) -> Any:
        datatypes = self.__dict__.get("_datatypes", {})
        if name in datatypes:
            return datatypes[name]
        raise AttributeError(
            f"{type(self).__name__!r} has no attribute {name!r}. "
            f"Registered datatypes: {list(datatypes)}"
        )

    def __enter__(self) -> "AttributeActions":
        if self._stop.is_set():
            self._stop.clear()
        self._entered = True
        for thunk in self._pending:
            thunk()
        self._pending.clear()
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
        self._stop.clear()
        self._threads.clear()
        self._entered = False

    def bind(self, attr_class: type) -> "AttributeActions":
        self._attr_class_ref = weakref.ref(attr_class)
        return self

    def _get_attr_class(self) -> Any | None:
        return self._attr_class_ref() if self._attr_class_ref else None

    def _read_attr(self, attr: Any, key: Any) -> int | None:
        try:
            return int(attr[key])
        except Exception as e:
            val = getattr(attr, "value", None)
            if val is not None:
                return int(val)
            self._logger(f"Failed to read {key} from attr: {e}")
            return None

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

    @overload
    def on_change(
        self,
        tag_name: str,
        callback: Callable[[Any, Any, Any], None],
        *,
        key: Any | None = ...,
    ) -> "AttributeActions": ...

    @overload
    def on_change(
        self,
        tag_name: str,
        callback: None = ...,
        *,
        key: Any | None = ...,
    ) -> Callable[[Callable[[Any, Any, Any], None]], Callable[[Any, Any, Any], None]]: ...

    def on_change(
        self,
        tag_name: str,
        callback: Callable[[Any, Any, Any], None] | None = None,
        *,
        key: Any | None = None,
    ) -> "AttributeActions | Callable":
        if callback is not None:
            with self._listener_lock:
                self._listeners.setdefault(tag_name, []).append((callback, key))
            return self

        def decorator(
            fn: Callable[[Any, Any, Any], None],
        ) -> Callable[[Any, Any, Any], None]:
            with self._listener_lock:
                self._listeners.setdefault(tag_name, []).append((fn, key))
            return fn

        return decorator

    def remove_listeners(self, tag_name: str) -> "AttributeActions":
        with self._listener_lock:
            self._listeners.pop(tag_name, None)
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

    def stop(self) -> None:
        self._stop.set()
        self._listeners.clear()

    def join(self, timeout: float | None = None) -> None:
        for t in self._threads:
            t.join(timeout=timeout)

    def is_running(self) -> bool:
        return any(t.is_alive() for t in self._threads)

    def on_set(self, attr, key, value):
        tag_name = getattr(attr, "name", None)
        if tag_name is None:
            return
        for dt in self._datatypes.values():
            hook = getattr(dt, "on_set_hook", None)
            if hook is not None:
                hook(tag_name, attr, key, value)
        self._fire_listeners(tag_name, attr, key, value)

    # def on_set(self, attr: Any, key: Any, value: Any) -> None:
    #     tag_name = getattr(attr, "name", None)
    #     if tag_name is None:
    #         return
    #     if tag_name.endswith(".DATA"):
    #         name_prefix = tag_name[: -len(".DATA")]
    #         self.string._len_helper(name_prefix, key, value)
    #     self._fire_listeners(tag_name, attr, key, value)
