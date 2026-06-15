# Copyright 2026 Merck KGaA, Darmstadt, Germany and/or its affiliates.
# All rights reserved

# src/server/actions/actions.py
from __future__ import annotations

import threading
import time
import weakref
from typing import Any, Callable, overload, Type


# ---------------------------------------------------------------------------
# Built-in type validators
# ---------------------------------------------------------------------------

def _v_string(v: Any) -> str:
    if not isinstance(v, str):
        raise TypeError(f"SSTRING default must be str, got {type(v).__name__!r}: {v!r}")
    return v

def _v_sint(v: Any) -> int:
    n = int(v)
    if not (-128 <= n <= 127):
        raise ValueError(f"SINT default {n} is outside [-128, 127]")
    return n

def _v_int(v: Any) -> int:
    n = int(v)
    if not (-32_768 <= n <= 32_767):
        raise ValueError(f"INT default {n} is outside [-32768, 32767]")
    return n

def _v_dint(v: Any) -> int:
    n = int(v)
    if not (-2_147_483_648 <= n <= 2_147_483_647):
        raise ValueError(f"DINT default {n} is outside [-2147483648, 2147483647]")
    return n

def _v_real(v: Any) -> float:
    try:
        return float(v)
    except (TypeError, ValueError) as exc:
        raise TypeError(
            f"REAL default must be numeric, got {type(v).__name__!r}: {v!r}"
        ) from exc

def _v_bool(v: Any) -> float:
    try:
        return bool(v)
    except (TypeError, ValueError) as exc:
        raise TypeError(
            f"BOOL default must be boolean, got {type(v).__name__!r}: {v!r}"
        ) from exc


_TYPE_VALIDATORS: dict[str, Callable[[Any], Any] | None] = {
    "SSTRING": _v_string,
    "SINT":    _v_sint,
    "INT":     _v_int,
    "DINT":    _v_dint,
    "REAL":    _v_real,
    "BOOL":    _v_bool,
}


# ---------------------------------------------------------------------------
# TypeSpec
# ---------------------------------------------------------------------------

class TypeSpec:
    """
    A validated type descriptor returned by ``actions.type.<TYPE>(default)``.

    Validates *default* against the registered validator for *type_name* at
    construction time.  Supports two-element unpacking::

        type_name, default = TypeSpec("INT", 0)
    """

    __slots__ = ("type_name", "default")

    def __init__(self, type_name: str, default: Any) -> None:
        key = type_name.upper()
        validator = _TYPE_VALIDATORS.get(key)
        self.type_name: str = key
        self.default: Any = validator(default) if validator is not None else default

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
        return hash((self.type_name, self.default))


# ---------------------------------------------------------------------------
# TypeNamespace
# ---------------------------------------------------------------------------

class TypeNamespace:
    """
    Exposes every registered PLC type as a callable factory::

        actions.type.INT(0)      # -> TypeSpec('INT', 0)
        actions.type.SSTRING("") # -> TypeSpec('SSTRING', '')

    Holds a live reference to ``_TYPE_VALIDATORS`` so types registered via
    :meth:`register_type` (or automatically through
    ``AttributeActions.register_datatype``) are immediately available.
    """

    def __init__(self, validators: dict[str, Callable[[Any], Any] | None]) -> None:
        # Live reference — mutations via register_type() are reflected instantly
        self._types = validators

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
        def factory(default: Any) -> TypeSpec:
            return TypeSpec(key, default)
        factory.__name__ = key
        factory.__qualname__ = f"TypeNamespace.{key}"
        return factory

    def __repr__(self) -> str:
        return f"TypeNamespace(types={sorted(self._types)})"

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
        self._datatypes: dict[str, Any] = {
            "type": TypeNamespace(_TYPE_VALIDATORS),
        }

        if thread_factory is None:
            thread_factory = lambda **kw: threading.Thread(**kw)
        self._thread_factory = thread_factory

    # ------------------------------------------------------------------
    # Datatype registration
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Context-manager lifecycle
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Attribute helpers
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Change listeners
    # ------------------------------------------------------------------

    @overload
    def on_change(
        self, tag_name: str, callback: Callable[[Any, Any, Any], None], *, key: Any | None = ...
    ) -> "AttributeActions": ...

    @overload
    def on_change(
        self, tag_name: str, callback: None = ..., *, key: Any | None = ...
    ) -> Callable[[Callable[[Any, Any, Any], None]], Callable[[Any, Any, Any], None]]: ...

    def on_change(
        self,
        tag_name: str,
        callback: Callable[[Any, Any, Any], None] | None = None,
        *,
        key: Any | None = None,
    ) -> "AttributeActions | Callable":
        def _register(fn: Callable) -> None:
            with self._listener_lock:
                self._listeners.setdefault(tag_name, []).append((fn, key))

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

    def _fire_listeners(self, tag_name: str, attr: Any, key: Any, value: Any) -> None:
        with self._listener_lock:
            entries = list(self._listeners.get(tag_name, []))
        for callback, key_filter in entries:
            if key_filter is not None and key_filter != key:
                continue
            try:
                callback(attr, key, value)
            except Exception as exc:
                self._logger(f"AttributeActions: listener error for {tag_name}: {exc}")

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def stop(self) -> None:
        self._stop.set()
        self._listeners.clear()

    def join(self, timeout: float | None = None) -> None:
        for t in self._threads:
            t.join(timeout=timeout)

    def is_running(self) -> bool:
        return any(t.is_alive() for t in self._threads)

    # ------------------------------------------------------------------
    # Tag-set hook
    # ------------------------------------------------------------------

    def on_set(self, attr: Any, key: Any, value: Any) -> None:
        from src.server.tag_specs import tag_registry

        tag_name = getattr(attr, "name", None)
        if tag_name is None:
            return

        origin_type = tag_registry.build_type_map().get(tag_name)
        if origin_type is not None:
            dt = self._datatypes.get(origin_type.lower())
            if dt is not None:
                hook = getattr(dt, "on_set_hook", None)
                if hook is not None:
                    hook(tag_name, attr, key, value)

        self._fire_listeners(tag_name, attr, key, value)


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------
actions = AttributeActions()
