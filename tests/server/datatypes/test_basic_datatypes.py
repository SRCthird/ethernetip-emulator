# Copyright 2026 Merck KGaA, Darmstadt, Germany and/or its affiliates.
# All rights reserved

# tests/server/datatypes/test_basic_datatypes.py
"""
Parameterized tests for all Basic-template datatypes.

Adding a new datatype to DATATYPE_CASES is enough to include it in the full
test suite — no extra test class required.
"""

from __future__ import annotations

import sys
import types
import unittest
from unittest.mock import MagicMock
from typing import Any, List, Tuple


# ---------------------------------------------------------------------------
# cpppo stub (must precede any src import)
# ---------------------------------------------------------------------------

def _install_cpppo_stubs() -> None:
    if "cpppo" in sys.modules and not isinstance(sys.modules["cpppo"], MagicMock):
        return

    class _BaseAttribute:
        def __init__(self, name: str, type_cls: Any, **kwargs: Any) -> None:
            self.name = name
            self.type_cls = type_cls
            self.kwargs = kwargs
            self._store: dict = {}

        def __setitem__(self, key, value):
            self._store[key] = value

        def __getitem__(self, key):
            return self._store[key]

    enip_device_mod = types.ModuleType("cpppo.server.enip.device")
    enip_device_mod.Attribute = _BaseAttribute  # type: ignore
    enip_mod = types.ModuleType("cpppo.server.enip")
    enip_mod.device = enip_device_mod  # type: ignore
    server_mod = types.ModuleType("cpppo.server")
    server_mod.enip = enip_mod  # type: ignore
    cpppo_mod = types.ModuleType("cpppo")
    cpppo_mod.server = server_mod  # type: ignore
    sys.modules["cpppo"] = cpppo_mod
    sys.modules["cpppo.server"] = server_mod
    sys.modules["cpppo.server.enip"] = enip_mod
    sys.modules["cpppo.server.enip.device"] = enip_device_mod


_install_cpppo_stubs()

# ---------------------------------------------------------------------------
# Real imports
# ---------------------------------------------------------------------------

from src.ethernetip_emulator.server.actions import AttributeActions       # noqa: E402
from src.ethernetip_emulator.server.datatypes.bool import Bool             # noqa: E402
from src.ethernetip_emulator.server.datatypes.dint import Dint             # noqa: E402
from src.ethernetip_emulator.server.datatypes.int import Int               # noqa: E402
from src.ethernetip_emulator.server.datatypes.lint import Lint             # noqa: E402
from src.ethernetip_emulator.server.datatypes.sint import Sint             # noqa: E402
from src.ethernetip_emulator.server.datatypes.udint import Udint           # noqa: E402
from src.ethernetip_emulator.server.datatypes.uint import Uint             # noqa: E402
from src.ethernetip_emulator.server.datatypes.ulint import Ulint           # noqa: E402
from src.ethernetip_emulator.server.datatypes.usint import Usint           # noqa: E402
from src.ethernetip_emulator.server.datatypes.real import Real             # noqa: E402
from src.ethernetip_emulator.server.datatypes.lreal import LReal           # noqa: E402
from src.ethernetip_emulator.server.datatypes.sstring import Sstring       # noqa: E402


# ---------------------------------------------------------------------------
# Test-case descriptors
#
# Each entry:
#   (
#     cls,                    # datatype class
#     registered_name,        # key in actions._datatypes
#     valid_cases,            # list of (raw_input, expected_output)
#     invalid_cases,          # list of (bad_input, expected_exception_type)
#     boundary_cases,         # list of (raw_input, expected_output)  ← optional
#   )
# ---------------------------------------------------------------------------

class _NoBool:
    """Helper: object whose __bool__ raises TypeError, exercising Bool.type_validator's except branch."""
    def __bool__(self):
        raise TypeError("no bool conversion")


DATATYPE_CASES: List[Tuple] = [
    # Bool ----------------------------------------------------------------
    (
        Bool, "bool",
        [(True, True), (False, False), (1, True), (0, False), ("yes", True)],
        [(_NoBool(), TypeError)],
        [],
    ),
    # Dint ----------------------------------------------------------------
    (
        Dint, "dint",
        [(0, 0), (100, 100), (-1, -1)],
        [("abc", (TypeError, ValueError)), (2_147_483_648, ValueError),
         (-2_147_483_649, ValueError)],
        [(2_147_483_647, 2_147_483_647), (-2_147_483_648, -2_147_483_648)],
    ),
    # Int -----------------------------------------------------------------
    (
        Int, "int",
        [(0, 0), (1000, 1000), (-1, -1)],
        [("abc", (TypeError, ValueError)), (32_768, ValueError),
         (-32_769, ValueError)],
        [(32_767, 32_767), (-32_768, -32_768)],
    ),
    # Lint ----------------------------------------------------------------
    (
        Lint, "lint",
        [(0, 0), (1, 1), (-1, -1)],
        [("abc", (TypeError, ValueError)),
         (9_223_372_036_854_775_808, ValueError),
         (-9_223_372_036_854_775_809, ValueError)],
        [(9_223_372_036_854_775_807, 9_223_372_036_854_775_807),
         (-9_223_372_036_854_775_808, -9_223_372_036_854_775_808)],
    ),
    # Sint ----------------------------------------------------------------
    (
        Sint, "sint",
        [(0, 0), (100, 100), (-1, -1)],
        [("abc", (TypeError, ValueError)), (128, ValueError), (-129, ValueError)],
        [(127, 127), (-128, -128)],
    ),
    # Udint ---------------------------------------------------------------
    (
        Udint, "udint",
        [(0, 0), (100, 100)],
        [("abc", (TypeError, ValueError)), (-1, ValueError),
         (4_294_967_296, ValueError)],
        [(4_294_967_295, 4_294_967_295), (0, 0)],
    ),
    # Uint ----------------------------------------------------------------
    (
        Uint, "uint",
        [(0, 0), (1000, 1000)],
        [("abc", (TypeError, ValueError)), (-1, ValueError), (65_536, ValueError)],
        [(65_535, 65_535), (0, 0)],
    ),
    # Ulint ---------------------------------------------------------------
    (
        Ulint, "ulint",
        [(0, 0), (1, 1)],
        [("abc", (TypeError, ValueError)), (-1, ValueError),
         (18_446_744_073_709_551_616, ValueError)],
        [(18_446_744_073_709_551_615, 18_446_744_073_709_551_615), (0, 0)],
    ),
    # Usint ---------------------------------------------------------------
    (
        Usint, "usint",
        [(0, 0), (200, 200)],
        [("abc", (TypeError, ValueError)), (-1, ValueError), (256, ValueError)],
        [(255, 255), (0, 0)],
    ),
    # Real ----------------------------------------------------------------
    (
        Real, "real",
        [(0.0, 0.0), (3.14, 3.14), (-1.5, -1.5)],
        [("abc", (TypeError, ValueError))],
        [],
    ),
    # LReal ---------------------------------------------------------------
    (
        LReal, "lreal",
        [(0.0, 0.0), (1e300, 1e300), (-1e300, -1e300)],
        [("abc", (TypeError, ValueError))],
        [],
    ),
    # Sstring -------------------------------------------------------------
    (
        Sstring, "sstring",
        [("hello", "hello"), ("", "")],
        [(123, TypeError), (None, TypeError), (3.14, TypeError)],
        [],
    ),
]


# ===========================================================================
# Shared mixin – every subclass gets these tests for free
# ===========================================================================

class BasicDatatypeMixin:
    """
    Mixin that provides a generic test suite for Basic-template datatypes.

    Subclasses must set:
        cls              – the datatype class under test
        registered_name  – expected key in actions._datatypes
        valid_cases      – list of (input, expected_output) for type_validator
        invalid_cases    – list of (bad_input, exception_or_tuple_of_exceptions)
        boundary_cases   – list of (input, expected_output) for type_validator
    """

    cls = None
    registered_name = None
    valid_cases = []
    invalid_cases = []
    boundary_cases = []

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def test_registered_on_module_level_actions(self):
        from src.ethernetip_emulator.server.device import actions
        self.assertIn(
            self.registered_name,
            actions._datatypes,
            f"{self.cls.__name__} not registered as {self.registered_name!r} "
            f"in module-level actions",
        )

    def test_registered_instance_is_correct_type(self):
        from src.ethernetip_emulator.server.device import actions
        instance = actions._datatypes.get(self.registered_name)
        self.assertIsInstance(instance, self.cls)

    # ------------------------------------------------------------------
    # Instantiation
    # ------------------------------------------------------------------

    def test_instantiates_with_parent_actions(self):
        parent = MagicMock(spec=AttributeActions)
        instance = self.cls(parent)
        self.assertIsNotNone(instance)

    # ------------------------------------------------------------------
    # type_validator – has the method
    # ------------------------------------------------------------------

    def test_has_type_validator_staticmethod(self):
        self.assertTrue(
            callable(getattr(self.cls, "type_validator", None)),
            f"{self.cls.__name__}.type_validator is not callable",
        )

    # ------------------------------------------------------------------
    # type_validator – valid inputs
    # ------------------------------------------------------------------

    def test_type_validator_valid_inputs(self):
        for raw, expected in self.valid_cases:
            with self.subTest(input=raw):
                result = self.cls.type_validator(raw)
                self.assertEqual(result, expected)

    # ------------------------------------------------------------------
    # type_validator – invalid inputs
    # ------------------------------------------------------------------

    def test_type_validator_invalid_inputs_raise(self):
        for bad_input, exc_types in self.invalid_cases:
            with self.subTest(input=bad_input):
                with self.assertRaises(exc_types):
                    self.cls.type_validator(bad_input)

    # ------------------------------------------------------------------
    # type_validator – boundary values
    # ------------------------------------------------------------------

    def test_type_validator_boundary_values(self):
        for raw, expected in self.boundary_cases:
            with self.subTest(boundary=raw):
                result = self.cls.type_validator(raw)
                self.assertEqual(result, expected)


# ===========================================================================
# Generate one concrete TestCase per datatype
# ===========================================================================

def _make_test_class(
    cls, registered_name, valid_cases, invalid_cases, boundary_cases
):
    return type(
        f"Test{cls.__name__}",
        (BasicDatatypeMixin, unittest.TestCase),
        {
            "cls": cls,
            "registered_name": registered_name,
            "valid_cases": valid_cases,
            "invalid_cases": invalid_cases,
            "boundary_cases": boundary_cases,
        },
    )


for _args in DATATYPE_CASES:
    _cls = _args[0]
    _test_cls = _make_test_class(*_args)
    # Inject into this module's namespace so unittest discovery finds them
    globals()[_test_cls.__name__] = _test_cls


if __name__ == "__main__":
    unittest.main()
