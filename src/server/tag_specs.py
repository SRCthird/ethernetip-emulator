# Copyright 2026 Merck KGaA, Darmstadt, Germany and/or its affiliates.
# All rights reserved

# src/server/tag_specs.py
from typing import Any, Iterable, List, Sequence, Tuple

# TAG_SPECS is expected to be: List[Tuple[str, str, Any]]
#   name: str
#   type_spec: str (e.g., "INT", "BOOL", etc.)
#   default: Any (or None)


def build_tag_specs_argv(
    tag_specs: Iterable[Tuple[str, str, Any]],
    base_args: Sequence[str] | None = None,
) -> List[str]:
    """
    Build an argv-like list from tag specs.

    Args:
        tag_specs:
            Iterable of (name, type_spec, default) tuples.
        base_args:
            Optional sequence of base arguments to prepend
            (e.g., ["--print"]).

    Returns:
        A list of arguments such as:
            ["--print", "I_TEXT=BOOL", "O_TEXT=BOOL", "O_INCR=DINT"]
    """
    if base_args is None:
        base_args = []

    argv: List[str] = list(base_args)
    argv.extend(f"{name}={type_spec}" for (name, type_spec, _) in tag_specs)
    return argv


# Default tag specifications.
# You can still replace TAG_SPECS in tests, or bypass this constant entirely
# by calling build_tag_specs_argv with your own tag_specs.
TAG_SPECS: List[Tuple[str, str, Any]] = [
    # Example:
    ("I_TEXT", "BOOL", 0),
    ("O_TEXT", "BOOL", 0),
    ("O_INCR", "DINT", 0),
]

# Convenience module-level argv built from TAG_SPECS.
# For tests, use build_tag_specs_argv directly with test data.
TAG_ARGV: List[str] = build_tag_specs_argv(TAG_SPECS, base_args=["--print"])
