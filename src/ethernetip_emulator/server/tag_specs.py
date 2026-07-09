# Copyright 2026 Merck KGaA, Darmstadt, Germany and/or its affiliates.
# All rights reserved

# src/ethernetip_emulator/server/tag_specs.py
from __future__ import annotations

import threading
from typing import Any, Callable, Iterable, List, Optional, Sequence, Set, Tuple


class TagRegistry:

    def __init__(self) -> None:
        self._expanders: dict[str, Callable] = {}
        self._raw: List[Tuple[str, str, Any]] = []
        self._built: List[Tuple[str, str, Any]] | None = None
        self._type_map: dict[str, str] | None = None
        self._lock = threading.RLock()

    @staticmethod
    def _normalise(entry: tuple) -> Tuple[str, str, Any]:
        if len(entry) != 2:
            raise ValueError(
                f"Tag entry must be a 2-tuple (name, TypeSpec), got {len(entry)} elements: {entry!r}"
            )
        name, spec = entry
        type_name = getattr(spec, "type_name", None)
        if type_name is None:
            raise TypeError(
                f"Tag entry second element must be a TypeSpec (has .type_name); "
                f"got {type(spec)!r}"
            )
        return name, type_name, spec.default

    def register(
        self,
        fn_or_prefix: Callable[[], Iterable[tuple]] | str,
    ) -> Any:
        if isinstance(fn_or_prefix, str):
            prefix = fn_or_prefix
            def decorator(fn):
                staged = [
                    (f"{prefix}.{name}", type_spec, default)
                    for name, type_spec, default in (
                        self._normalise(entry) for entry in fn()
                    )
                ]
                with self._lock:
                    self._raw.extend(staged)
                    self.invalidate()
                return fn
            return decorator
        else:
            fn = fn_or_prefix
            staged = list(self._normalise(entry) for entry in fn())
            with self._lock:
                self._raw.extend(staged)
                self.invalidate()
            return fn

    def expander(
        self, type_spec: str
    ) -> Callable[[Callable], Callable]:
        def decorator(fn: Callable) -> Callable:
            with self._lock:
                self._expanders[type_spec.upper()] = fn
                self.invalidate()
            return fn
        return decorator

    def _expand_one(
        self,
        name: str,
        type_spec: str,
        default: Any,
        origin: str,
        seen: Optional[Set[str]] = None,
    ) -> List[Tuple[str, str, Any, str]]:
        key = type_spec.upper()
        expander = self._expanders.get(key)

        if expander is None:
            return [(name, type_spec, default, origin)]

        if seen is None:
            seen = set()
        if key in seen:
            raise RuntimeError(
                f"TagRegistry: cycle detected expanding type {key!r} "
                f"(seen chain: {sorted(seen)}) for tag {name!r}"
            )

        seen = seen | {key}
        result: List[Tuple[str, str, Any, str]] = []
        for raw_child in expander(name, default):
            child_name, child_type, child_default = self._normalise(raw_child)
            result.extend(
                self._expand_one(child_name, child_type, child_default, origin, seen)
            )
        return result

    def _ensure_built(self) -> None:
        with self._lock:
            if self._built is not None:
                return

            built: List[Tuple[str, str, Any]] = []
            type_map: dict[str, str] = {}

            for name, type_spec, default in self._raw:
                origin = type_spec.upper()
                for prim_name, prim_type, prim_default, src in self._expand_one(
                    name, type_spec, default, origin
                ):
                    if prim_name in type_map:
                        raise ValueError(
                            f"TagRegistry: duplicate tag name {prim_name!r} "
                            f"(already registered with type {type_map[prim_name]!r}, "
                            f"now seeing type {src!r})"
                        )
                    built.append((prim_name, prim_type, prim_default))
                    type_map[prim_name] = src

            self._built = built
            self._type_map = type_map

    def build_type_map(self) -> dict[str, str]:
        self._ensure_built()
        with self._lock:
            return dict(self._type_map)

    def invalidate(self) -> None:
        with self._lock:
            self._built = None
            self._type_map = None

    invalidate_type_map = invalidate

    def build(self) -> List[Tuple[str, str, Any]]:
        self._ensure_built()
        with self._lock:
            return list(self._built)

    def build_argv(
        self,
        base_args: Sequence[str] | None = None,
    ) -> List[str]:
        expanded = self.build()
        argv: List[str] = list(base_args or [])
        argv.extend(f"{name}={type_spec}" for name, type_spec, _ in expanded)
        return argv

    @property
    def specs(self) -> List[Tuple[str, str, Any]]:
        return self.build()

    @property
    def argv(self) -> List[str]:
        return self.build_argv(base_args=["--print"])

tag_registry = TagRegistry()
