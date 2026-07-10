# Copyright 2026 Merck KGaA, Darmstadt, Germany and/or its affiliates.
# All rights reserved

# src/ethernetip_emulator/server/actions.py
from __future__ import annotations

import threading
import time
import weakref
from typing import Any, Callable, List, overload, Type


class TypeSpec:
    __slots__ = ("type_name", "default")

    def __init__(self, type_name: str, default: Any, namespace: "TypeNamespace | None" = None) -> None:
        key = type_name.upper()
        validator = namespace._types.get(key) if namespace is not None else None
        self.type_name: str = key
        if validator is not None:
            try:
                self.default: Any = validator(default)
            except Exception as exc:
                raise ValueError(
                    f"TypeSpec: validator for {key!r} rejected default {default!r}: {exc}"
                ) from exc
        else:
            self.default: Any = default

    def __iter__(self):
        yield self.type_name
        yield self.default

    def __repr__(self) -> str:
        return f"TypeSpec({self.type_name!r}, {self.default!r})"

    def __eq__(self, other: object) -> bool:
        if isinstance(other, TypeSpec):
            return self.type_name == other.type_name and self.default == other.default
        return NotImplemented

    def __hash__(self) -> int:
        try:
            return hash((self.type_name, self.default))
        except TypeError:
            return hash((self.type_name, id(self.default)))


class TypeNamespace:
    def __init__(self) -> None:
        self._types: dict[str, Callable[[Any], Any] | None] = {}

    def register_type(
        self,
        name: str,
        validator: Callable[[Any], Any] | None = None,
    ) -> None:
        self._types[name.upper()] = validator

    def __getattr__(self, name: str) -> Callable[[Any], TypeSpec]:
        key = name.upper()
        types = object.__getattribute__(self, "_types")
        if key not in types:
            raise AttributeError(
                f"Unknown PLC type {name!r}. Registered types: {sorted(types)}"
            )
        ns = self
        def factory(default: Any) -> TypeSpec:
            return TypeSpec(key, default, ns)
        factory.__name__ = key
        factory.__qualname__ = f"TypeNamespace.{key}"
        return factory

    def __repr__(self) -> str:
        return f"TypeNamespace(types={sorted(self._types)})"


class AttributeActions:

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
        self._datatypes: dict[str, Any] = {
            "type": TypeNamespace(),
        }

        if thread_factory is None:
            thread_factory = lambda **kw: threading.Thread(**kw)
        self._thread_factory = thread_factory

    def register_datatype(self, name: str, cls: Type[Any]) -> "AttributeActions":
        self._datatypes[name] = cls(self)
        self._datatypes["type"].register_type(name, getattr(cls, "type_validator", None))
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

    def _read_attr(self, attr: Any, key: slice = slice(0,1)) -> List[Any] | None:
        try:
            return attr[key]
        except Exception as e:
            val = getattr(attr, "value", None)
            if val is not None:
                return val
            self._logger(f"Failed to read {key} from attr: {e}")
            return None

    def _write_attr(self, attr: Any, key: slice, value: List[Any]) -> None:
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
        self, tag_name: str, callback: Callable[[Any, Any, Any], None], *, key: slice = ..., defer = ...
    ) -> "AttributeActions": ...

    @overload
    def on_change(
        self, tag_name: str, callback: None = ..., *, key: slice = ..., defer= ...
    ) -> Callable[[Callable[[Any, Any, Any], None]], Callable[[Any, Any, Any], None]]: ...

    def on_change(
        self,
        tag_name: str,
        callback: Callable[[Any, Any, Any], None] | None = None,
        *,
        key: slice = slice(0,1),
        defer: bool = False,
    ) -> "AttributeActions | Callable":
        def _wrap(fn: Callable) -> Callable:
            if not defer:
                return fn
            def deferred(attr, k, value):
                t = self._thread_factory(target=lambda: fn(attr, k, value), daemon=True)
                self._threads.append(t)
                t.start()
            deferred.__name__ = getattr(fn, "__name__", "deferred")
            return deferred

        def _register(fn: Callable) -> None:
            with self._listener_lock:
                self._listeners.setdefault(tag_name, []).append((_wrap(fn), key))

        if callback is not None:
            _register(callback)
            return self

        def decorator(fn: Callable[[Any, Any, Any], None]) -> Callable[[Any, Any, Any], None]:
            _register(fn)
            return fn

        return decorator


    def remove_listeners(self, tag_name: str) -> "AttributeActions":
        with self._listener_lock:
            self._listeners.pop(tag_name, None)
        return self

    def _fire_listeners(self, tag_name: str, attr: Any, key: slice, value: Any) -> None:
        with self._listener_lock:
            entries = list(self._listeners.get(tag_name, []))
        for callback, key_filter in entries:
            if key_filter is not None and key_filter != key:
                continue
            try:
                callback(attr, value, key)
            except Exception as exc:
                self._logger(f"AttributeActions: listener error for {tag_name}: {exc}")

    def stop(self) -> None:
        self._stop.set()
        if self._entered:
            self._listeners.clear()

    def join(self, timeout: float | None = None) -> None:
        for t in self._threads:
            t.join(timeout=timeout)

    def is_running(self) -> bool:
        return any(t.is_alive() for t in self._threads)

    def on_set(self, attr: Any, key: slice, value: Any) -> None:
        from src.ethernetip_emulator.server.tag_specs import tag_registry

        tag_name = getattr(attr, "name", None)
        if tag_name is None:
            return

        origin_type = tag_registry.build_type_map().get(tag_name)
        if origin_type is not None:
            dt = self._datatypes.get(origin_type.lower())
            if dt is not None:
                hook = getattr(dt, "on_set_hook", None)
                if hook is not None:
                    hook(tag_name, attr, value, key)

        if origin_type is None and tag_name not in self._listeners:
            self._logger(
                f"AttributeActions.on_set: tag {tag_name!r} not in registry "
                f"and has no listeners — skipping."
            )
            return

        self._fire_listeners(tag_name, attr, key, value)
