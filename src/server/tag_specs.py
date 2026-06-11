# Copyright 2026 Merck KGaA, Darmstadt, Germany and/or its affiliates.
# All rights reserved

# src/server/tag_specs.py
from typing import Any, Callable, Iterable, List, Optional, Sequence, Set, Tuple


class TagRegistry:
    """
    A tag_registry that collects raw tag specs via a decorator and expands
    composite types (COUNTER, TIMER, STRING) into their primitive sub-tags.

    Expansion is fully recursive: if an expander returns a tuple whose
    type_spec is itself a registered composite, that tuple is expanded in
    turn.  A ``seen`` set prevents infinite loops when a circular expander
    chain is accidentally registered.

    Usage
    -----
    In any file that can import the shared tag_registry instance::

        from tag_specs import tag_registry

        @tag_registry.register
        def _():
            return [
                ("I_TEXT",    "STRING",  ""),
                ("O_INCR",    "INT",      0),
                ("O_Updates", "COUNTER", 1000),
            ]

    Calling ``tag_registry.build()`` (or accessing ``tag_registry.specs`` /
    ``tag_registry.argv``) triggers expansion of all registered specs.

    Custom expanders
    ----------------
    Register a new composite type at any point before ``build()`` is called::

        @tag_registry.expander("MYFLOATARRAY")
        def expand_myfloatarray(name, preset):
            return [(f"{name}[{i}]", "REAL", preset) for i in range(4)]

    Nested expanders work automatically::

        @tag_registry.expander("CUSTOM_TYPE")
        def _expand_custom(name, preset):
            return [
                (f"{name}",           "STRING", preset),  # will be recursively expanded
                (f"{name}.SOMETHING", "DINT",   0),
            ]
    """

    def __init__(self) -> None:
        self._expanders: dict[str, Callable] = {}
        self._raw: List[Tuple[str, str, Any]] = []
        self._type_map: dict[str, str] | None = None

    def register(
        self,
        fn: Callable[[], Iterable[Tuple[str, str, Any]]],
    ) -> Callable[[], Iterable[Tuple[str, str, Any]]]:
        self._raw.extend(fn())
        self._type_map = None
        return fn

    def expander(
        self, type_spec: str
    ) -> Callable[[Callable], Callable]:
        def decorator(fn: Callable) -> Callable:
            self._expanders[type_spec.upper()] = fn
            return fn
        return decorator

    def _expand_one(
        self,
        name: str,
        type_spec: str,
        default: Any,
        seen: Optional[Set[str]] = None,
    ) -> List[Tuple[str, str, Any]]:
        key = type_spec.upper()
        expander = self._expanders.get(key)

        if expander is None:
            return [(name, type_spec, default)]

        if seen is None:
            seen = set()

        if key in seen:
            return [(name, type_spec, default)]

        seen = seen | {key}

        result: List[Tuple[str, str, Any]] = []
        for child_name, child_type, child_default in expander(name, default):
            result.extend(
                self._expand_one(child_name, child_type, child_default, seen)
            )
        return result

    def _expand_one_typed(
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
        for child_name, child_type, child_default in expander(name, default):
            result.extend(
                self._expand_one_typed(child_name, child_type, child_default, origin, seen)
            )
        return result

    def build_type_map(self) -> dict[str, str]:
        if self._type_map is not None:
            return self._type_map

        type_map: dict[str, str] = {}
        for name, type_spec, default in self._raw:
            origin = type_spec.upper()
            for prim_name, _, _, src in self._expand_one_typed(name, type_spec, default, origin):
                type_map[prim_name] = src

        self._type_map = type_map
        return self._type_map

    def invalidate_type_map(self) -> None:
        self._type_map = None

    def build(self) -> List[Tuple[str, str, Any]]:
        result: List[Tuple[str, str, Any]] = []
        for name, type_spec, default in self._raw:
            result.extend(self._expand_one(name, type_spec, default))
        return result

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
