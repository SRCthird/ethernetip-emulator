# Copyright 2026 Merck KGaA, Darmstadt, Germany and/or its affiliates.
# All rights reserved

# src/server/tag_specs.py
from typing import Any, Iterable, List, Sequence, Tuple

# TAG_SPECS is expected to be: List[Tuple[str, str, Any]]
#   name: str
#   type_spec: str (e.g., "INT", "BOOL", "COUNTER", "TIMER")
#   default: Any (or None)


# ---------------------------------------------------------------------------
# Composite-type expanders
# ---------------------------------------------------------------------------

def expand_counter(name: str, preset: int) -> List[Tuple[str, str, Any]]:
    """
    Expand a virtual COUNTER tag into its individual sub-tags.

    Sub-tags mirror the Allen-Bradley / Studio 5000 COUNTER structure:
        .PRE  – Preset value (count target)
        .ACC  – Accumulator (current count)
        .CU   – Count-Up enable
        .CD   – Count-Down enable
        .DN   – Done bit  (ACC >= PRE)
        .OV   – Overflow
        .UN   – Underflow
        .RES  – Reset
    """
    return [
        (f"{name}.PRE", "DINT", preset),
        (f"{name}.ACC", "DINT", 0),
        (f"{name}.CU",  "BOOL", 0),
        (f"{name}.CD",  "BOOL", 0),
        (f"{name}.DN",  "BOOL", 0),
        (f"{name}.OV",  "BOOL", 0),
        (f"{name}.UN",  "BOOL", 0),
        (f"{name}.RES", "BOOL", 0),
    ]


def expand_timer(name: str, preset: int) -> List[Tuple[str, str, Any]]:
    """
    Expand a virtual TIMER tag into its individual sub-tags.

    Sub-tags mirror the Allen-Bradley / Studio 5000 TIMER structure:
        .PRE  – Preset value (milliseconds)
        .ACC  – Accumulator (elapsed ms)
        .EN   – Enable bit
        .TT   – Timer Timing bit
        .DN   – Done bit  (ACC >= PRE)
    """
    return [
        (f"{name}.PRE", "DINT", preset),
        (f"{name}.ACC", "DINT", 0),
        (f"{name}.EN",  "BOOL", 0),
        (f"{name}.TT",  "BOOL", 0),
        (f"{name}.DN",  "BOOL", 0),
    ]


# ---------------------------------------------------------------------------
# Composite-type registry
# ---------------------------------------------------------------------------

_EXPANDERS = {
    "COUNTER": expand_counter,
    "TIMER":   expand_timer,
}


# ---------------------------------------------------------------------------
# Public helper
# ---------------------------------------------------------------------------

def build_tag_specs(
    raw: Iterable[Tuple[str, str, Any]],
) -> List[Tuple[str, str, Any]]:
    """
    Expand composite type specs (COUNTER, TIMER) into their primitive tags.

    All other entries are passed through unchanged.

    Args:
        raw: Iterable of (name, type_spec, default) tuples. When type_spec is
             "COUNTER" or "TIMER", the default value is used as the preset.

    Returns:
        A flat list of (name, type_spec, default) tuples containing only
        primitive types.
    """
    result: List[Tuple[str, str, Any]] = []
    for name, type_spec, default in raw:
        expander = _EXPANDERS.get(type_spec.upper())
        if expander is not None:
            result.extend(expander(name, default))
        else:
            result.append((name, type_spec, default))
    return result


def build_tag_specs_argv(
    tag_specs: Iterable[Tuple[str, str, Any]],
    base_args: Sequence[str] | None = None,
) -> List[str]:
    """
    Build an argv-like list from tag specs.

    Composite types (COUNTER, TIMER) are automatically expanded before
    the argv is assembled.

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

    expanded = build_tag_specs(tag_specs)
    argv: List[str] = list(base_args)
    argv.extend(f"{name}={type_spec}" for (name, type_spec, _) in expanded)
    return argv


# Default tag specifications.
# You can still replace TAG_SPECS in tests, or bypass this constant entirely
# by calling build_tag_specs_argv with your own tag_specs.
TAG_SPECS = build_tag_specs([
    # (tag_name,    type_spec,  default)

    ("I_TEXT", "SSTRING[255]", ""),
    ("O_TEXT", "SSTRING[255]", ""),

    ("O_INCR", "INT", 0),

    # Types of numbers
    ("O_8Bit",        "SINT",  0),
    ("O_16Bit",       "INT",   0),
    ("O_32Bit",       "DINT",  0),
    ("O_32Bit_Float", "REAL",  0.0),

    # Composite types – expand automatically
    ("O_Updates",       "COUNTER",       1000),   # preset = 1000
    ("O_Updates.LAZY",  "INT",           0),      # lazy counter (separate)
    ("O_Timer",         "TIMER",         5000),   # preset = 5000 ms
])

# Convenience module-level argv built from TAG_SPECS.
# For tests, use build_tag_specs_argv directly with test data.
TAG_ARGV: List[str] = build_tag_specs_argv(TAG_SPECS, base_args=["--print"])
