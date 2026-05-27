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
TAG_SPECS = [
    # (tag_name,    type_spec,  default)

    ("I_TEXT", "SSTRING[255]", ""),
    ("O_TEXT", "SSTRING[255]", ""),

    ("O_INCR", "DINT", 0),

    # COUNTER tag architecture
    ("O_Updates.PRE",  "DINT",     10),   # Preset: count target (adjust as needed)
    ("O_Updates.ACC",  "DINT",     0),    # Accumulator: current count
    ("O_Updates.CU",   "BOOL",     0),    # Count-Up enable
    ("O_Updates.CD",   "BOOL",     0),    # Count-Down enable
    ("O_Updates.DN",   "BOOL",     0),    # Done (ACC >= PRE)
    ("O_Updates.OV",   "BOOL",     0),    # Overflow
    ("O_Updates.UN",   "BOOL",     0),    # Underflow
]

# Convenience module-level argv built from TAG_SPECS.
# For tests, use build_tag_specs_argv directly with test data.
TAG_ARGV: List[str] = build_tag_specs_argv(TAG_SPECS, base_args=["--print"])
