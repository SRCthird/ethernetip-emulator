# Copyright 2026 Merck KGaA, Darmstadt, Germany and/or its affiliates.
# All rights reserved

# src/server/tag_specs.py
from __future__ import annotations

from typing import Any, Callable, Iterable, List, Optional, Sequence, Set, Tuple


class TagRegistry:
    """
    A registry that collects raw tag specs via a decorator and expands
    composite types (COUNTER, TIMER, STRING) into their primitive sub-tags.

    Each entry must be a two-element tuple ``(tag_name, spec)`` where *spec*
    is any object exposing ``.type_name`` and ``.default`` — i.e. a
    ``TypeSpec`` returned by ``actions.type.<TYPE>(default)``.

    Expansion is fully recursive; a ``seen`` set prevents infinite loops.

    Usage
    -----
    ::

        from tag_specs import tag_registry

        @tag_registry.register
        def _():
            return [
                ("I_TEXT",    actions.type.STRING("")),
                ("O_INCR",    actions.type.INT(0)),
                ("O_Updates", actions.type.COUNTER(1000)),
            ]

    Custom expanders
    ----------------
    ::

        @tag_registry.expander("MYFLOATARRAY")
        def expand_myfloatarray(name, preset):
            return [(f"{name}[{i}]", "REAL", preset) for i in range(4)]
    """

    def __init__(self) -> None:
        self._expanders: dict[str, Callable] = {}
        self._raw: List[Tuple[str, str, Any]] = []
        self._built: List[Tuple[str, str, Any]] | None = None
        self._type_map: dict[str, str] | None = None

    @staticmethod
    def _normalise(entry: tuple) -> Tuple[str, str, Any]:
        """
        Accept a two-element tuple ``(name, spec)`` where *spec* exposes
        ``.type_name`` and ``.default`` (i.e. ``actions.TypeSpec``).
        Returns a normalised ``(name, type_str, default)`` triple.
        """
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
                self._raw.extend(
                    (f"{prefix}.{name}", type_spec, default)
                    for name, type_spec, default in (
                        self._normalise(entry) for entry in fn()
                    )
                )
                self.invalidate()
                return fn
            return decorator
        else:
            fn = fn_or_prefix
            self._raw.extend(
                self._normalise(entry) for entry in fn()
            )
            self.invalidate()
            return fn

    def expander(
        self, type_spec: str
    ) -> Callable[[Callable], Callable]:
        def decorator(fn: Callable) -> Callable:
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
            return [(name, type_spec, default, origin)]

        seen = seen | {key}
        result: List[Tuple[str, str, Any, str]] = []
        for raw_child in expander(name, default):
            child_name, child_type, child_default = self._normalise(raw_child)
            result.extend(
                self._expand_one(child_name, child_type, child_default, origin, seen)
            )
        return result

    def _ensure_built(self) -> None:
        if self._built is not None:
            return

        built: List[Tuple[str, str, Any]] = []
        type_map: dict[str, str] = {}

        for name, type_spec, default in self._raw:
            origin = type_spec.upper()
            for prim_name, prim_type, prim_default, src in self._expand_one(
                name, type_spec, default, origin
            ):
                built.append((prim_name, prim_type, prim_default))
                type_map[prim_name] = src

        self._built = built
        self._type_map = type_map

    def build_type_map(self) -> dict[str, str]:
        self._ensure_built()
        return self._type_map

    def invalidate(self) -> None:
        self._built = None
        self._type_map = None

    invalidate_type_map = invalidate

    def build(self) -> List[Tuple[str, str, Any]]:
        self._ensure_built()
        return self._built

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


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------
tag_registry = TagRegistry()
