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

    # ------------------------------------------------------------------
    # Decorator API
    # ------------------------------------------------------------------

    def register(
        self,
        fn: Callable[[], Iterable[Tuple[str, str, Any]]],
    ) -> Callable[[], Iterable[Tuple[str, str, Any]]]:
        """
        Decorator: call ``fn`` immediately and collect its tag specs.

        The decorated function is returned unchanged so it can still be
        called directly (useful in tests).

            @tag_registry.register
            def _():
                return [("MY_TAG", "INT", 0)]
        """
        self._raw.extend(fn())
        return fn

    def expander(
        self, type_spec: str
    ) -> Callable[[Callable], Callable]:
        """
        Decorator factory: register a custom composite-type expander.

            @tag_registry.expander("MYFLOATARRAY")
            def expand_myfloatarray(name, preset):
                return [(f"{name}[{i}]", "REAL", preset) for i in range(4)]
        """
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

    def build(self) -> List[Tuple[str, str, Any]]:
        """
        Recursively expand all registered raw specs into primitive tag tuples.

        Returns:
            Flat list of ``(name, type_spec, default)`` containing only
            primitive types.
        """
        result: List[Tuple[str, str, Any]] = []
        for name, type_spec, default in self._raw:
            result.extend(self._expand_one(name, type_spec, default))
        return result

    def build_argv(
        self,
        base_args: Sequence[str] | None = None,
    ) -> List[str]:
        """
        Build an argv-like list from the expanded tag specs.

        Args:
            base_args: Optional sequence of arguments to prepend
                       (e.g., ``["--print"]``).

        Returns:
            List of strings such as::

                ["--print", "I_TEXT.LEN=DINT", "I_TEXT.DATA=SSTRING[82]", ...]
        """
        expanded = self.build()
        argv: List[str] = list(base_args or [])
        argv.extend(f"{name}={type_spec}" for name, type_spec, _ in expanded)
        return argv

    # ------------------------------------------------------------------
    # Convenience properties
    # ------------------------------------------------------------------

    @property
    def specs(self) -> List[Tuple[str, str, Any]]:
        """Expanded primitive tag specs (built fresh on every access)."""
        return self.build()

    @property
    def argv(self) -> List[str]:
        """argv with ``--print`` prepended (built fresh on every access)."""
        return self.build_argv(base_args=["--print"])


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------
tag_registry = TagRegistry()
