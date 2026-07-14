# Copyright 2026 Merck KGaA, Darmstadt, Germany and/or its affiliates.
# All rights reserved

# tests/server/datatypes/test_array_datatypes.py
from __future__ import annotations

import sys
import types
import unittest
from unittest.mock import MagicMock
from typing import Any, List, Tuple


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

from src.ethernetip_emulator.server.actions import AttributeActions
from src.ethernetip_emulator.server.datatypes.boolarray import BoolArray
from src.ethernetip_emulator.server.datatypes.dintarray import DintArray
from src.ethernetip_emulator.server.datatypes.intarray import IntArray
from src.ethernetip_emulator.server.datatypes.lintarray import LintArray
from src.ethernetip_emulator.server.datatypes.sintarray import SintArray
from src.ethernetip_emulator.server.datatypes.udintarray import UdintArray
from src.ethernetip_emulator.server.datatypes.uintarray import UintArray
from src.ethernetip_emulator.server.datatypes.ulintarray import UlintArray
from src.ethernetip_emulator.server.datatypes.usintarray import UsintArray
from src.ethernetip_emulator.server.datatypes.realarray import RealArray
from src.ethernetip_emulator.server.datatypes.lrealarray import LrealArray
from src.ethernetip_emulator.server.datatypes.sstringarray import SstringArray
from src.ethernetip_emulator.server.tag_specs import tag_registry


ARRAY_DATATYPE_CASES: List[Tuple] = [
    # BoolArray -----------------------------------------------------------
    (
        BoolArray, "boolarray", "BOOLARRAY",
        [((True, False, True), (True, False, True)),
         ((True,), (True,))],
        [[1, 2],          TypeError,    # not a tuple
         [],              TypeError,    # not a tuple (list)
         (),              ValueError,   # empty tuple
         (True, 1, False), TypeError],  # mixed bool/int
        (True, 0, False),               # 0/1 are not bool → TypeError
        (True, False),
    ),
    # DintArray -----------------------------------------------------------
    (
        DintArray, "dintarray", "DINTARRAY",
        [((0, 1, -1), (0, 1, -1)),
         ((32_767, -32_768), (32_767, -32_768))],
        [[1, 2],     TypeError,   # not a tuple
         (),         ValueError,  # empty
         (1, "x"),   TypeError,   # non-int element
         (1, 2_147_483_648), ValueError],  # out of range
        (1, "bad", 3),
        (0, 1, -1),
    ),
    # IntArray ------------------------------------------------------------
    (
        IntArray, "intarray", "INTARRAY",
        [((0, 1, -1), (0, 1, -1)),
         ((32_767, -32_768), (32_767, -32_768))],
        [[1],    TypeError,
         (),     ValueError,
         (1, "x"), TypeError,
         (1, 32_768), ValueError],
        (1, "bad"),
        (0, 1),
    ),
    # LintArray -----------------------------------------------------------
    (
        LintArray, "lintarray", "LINTARRAY",
        [((0, 1, -1), (0, 1, -1))],
        [[1],    TypeError,
         (),     ValueError,
         (1, "x"), TypeError,
         (1, 9_223_372_036_854_775_808), ValueError],
        (1, "bad"),
        (0, 1),
    ),
    # SintArray -----------------------------------------------------------
    (
        SintArray, "sintarray", "SINTARRAY",
        [((0, 127, -128), (0, 127, -128))],
        [[1],    TypeError,
         (),     ValueError,
         (1, "x"), TypeError,
         (1, 128), ValueError],
        (1, "bad"),
        (0, 1),
    ),
    # UdintArray ----------------------------------------------------------
    (
        UdintArray, "udintarray", "UDINTARRAY",
        [((0, 1, 4_294_967_295), (0, 1, 4_294_967_295))],
        [[1],    TypeError,
         (),     ValueError,
         (1, "x"), TypeError,
         (1, -1), ValueError],
        (1, "bad"),
        (0, 1),
    ),
    # UintArray -----------------------------------------------------------
    (
        UintArray, "uintarray", "UINTARRAY",
        [((0, 65_535), (0, 65_535))],
        [[1],    TypeError,
         (),     ValueError,
         (1, "x"), TypeError,
         (1, -1), ValueError],
        (1, "bad"),
        (0, 1),
    ),
    # UlintArray ----------------------------------------------------------
    (
        UlintArray, "ulintarray", "ULINTARRAY",
        [((0, 1), (0, 1))],
        [[1],    TypeError,
         (),     ValueError,
         (1, "x"), TypeError,
         (1, -1), ValueError],
        (1, "bad"),
        (0, 1),
    ),
    # UsintArray ----------------------------------------------------------
    (
        UsintArray, "usintarray", "USINTARRAY",
        [((0, 255), (0, 255))],
        [[1],    TypeError,
         (),     ValueError,
         (1, "x"), TypeError,
         (1, 256), ValueError],
        (1, "bad"),
        (0, 1),
    ),
    # RealArray -----------------------------------------------------------
    (
        RealArray, "realarray", "REALARRAY",
        [((0.0, 1.5, -1.5), (0.0, 1.5, -1.5))],
        [[1.0],  TypeError,
         (),     ValueError,
         (1.0, "x"), TypeError],
        (1.0, "bad"),
        (0.0, 1.0),
    ),
    # LrealArray ----------------------------------------------------------
    (
        LrealArray, "lrealarray", "LREALARRAY",
        [((0.0, 1e300), (0.0, 1e300))],
        [[1.0],  TypeError,
         (),     ValueError,
         (1.0, "x"), TypeError],
        (1.0, "bad"),
        (0.0, 1.0),
    ),
    # SstringArray --------------------------------------------------------
    (
        SstringArray, "sstringarray", "SSTRINGARRAY",
        [(("hello", "world"), ("hello", "world")),
         (("",), ("",))],
        [[1],    TypeError,
         (),     ValueError,
         ("ok", 123), TypeError],
        ("ok", 123),
        ("hello", "world"),
    ),
]


class ArrayDatatypeMixin:

    cls = None
    registered_name = None
    expander_type = None
    valid_cases = []
    invalid_cases = []
    mixed_type_case = ()
    expander_preset = ()

    def test_registered_on_module_level_actions(self):
        from src.ethernetip_emulator.server.device import actions
        self.assertIn(self.registered_name, actions._datatypes)  # type: ignore

    def test_registered_instance_is_correct_type(self):
        from src.ethernetip_emulator.server.device import actions
        self.assertIsInstance(actions._datatypes[self.registered_name], self.cls)  # type: ignore

    def test_instantiates_with_parent_actions(self):
        parent = MagicMock(spec=AttributeActions)
        self.assertIsNotNone(self.cls(parent))  # type: ignore

    def test_has_type_validator(self):
        self.assertTrue(callable(getattr(self.cls, "type_validator", None)))  # type: ignore

    def test_type_validator_valid_inputs(self):
        for raw, expected in self.valid_cases:
            with self.subTest(input=raw):  # type: ignore
                self.assertEqual(self.cls.type_validator(raw), expected)  # type: ignore

    def test_type_validator_raises_for_non_tuple(self):
        with self.assertRaises(TypeError):  # type: ignore
            self.cls.type_validator([1, 2, 3])  # type: ignore

    def test_type_validator_raises_for_non_tuple_scalar(self):
        with self.assertRaises(TypeError):  # type: ignore
            self.cls.type_validator("not_a_tuple")  # type: ignore

    def test_type_validator_raises_for_empty_tuple(self):
        with self.assertRaises(ValueError):  # type: ignore
            self.cls.type_validator(())  # type: ignore

    def test_type_validator_raises_for_mixed_element_types(self):
        with self.assertRaises(TypeError):  # type: ignore
            self.cls.type_validator(self.mixed_type_case)  # type: ignore

    def test_type_validator_invalid_cases(self):
        it = iter(self.invalid_cases)
        for bad_input, exc_type in zip(it, it):
            with self.subTest(input=bad_input):  # type: ignore
                with self.assertRaises(exc_type):  # type: ignore
                    self.cls.type_validator(bad_input)  # type: ignore

    def test_expander_registered_in_tag_registry(self):
        self.assertIn(self.expander_type, tag_registry._expanders)  # type: ignore

    def test_expander_returns_single_entry(self):
        expander = tag_registry._expanders[self.expander_type]  # type: ignore
        result = list(expander("my_tag", self.expander_preset))
        self.assertEqual(len(result), 1)  # type: ignore

    def test_expander_entry_name_matches_tag(self):
        expander = tag_registry._expanders[self.expander_type]  # type: ignore
        (name, _spec), = expander("my_tag", self.expander_preset)
        self.assertEqual(name, "my_tag")  # type: ignore

    def test_expander_entry_type_spec_encodes_length(self):
        expander = tag_registry._expanders[self.expander_type]  # type: ignore
        (_, spec), = expander("my_tag", self.expander_preset)
        expected_len = len(self.expander_preset)
        self.assertIn(str(expected_len), spec.type_name)  # type: ignore

    def test_expander_entry_default_is_list(self):
        expander = tag_registry._expanders[self.expander_type]  # type: ignore
        (_, spec), = expander("my_tag", self.expander_preset)
        self.assertIsInstance(spec.default, list)  # type: ignore

    def test_expander_entry_default_matches_preset(self):
        expander = tag_registry._expanders[self.expander_type]  # type: ignore
        (_, spec), = expander("my_tag", self.expander_preset)
        self.assertEqual(spec.default, list(self.expander_preset))  # type: ignore


def _make_test_class(
    cls, registered_name, expander_type,
    valid_cases, invalid_cases, mixed_type_case, expander_preset,
):
    return type(
        f"Test{cls.__name__}",
        (ArrayDatatypeMixin, unittest.TestCase),
        {
            "cls": cls,
            "registered_name": registered_name,
            "expander_type": expander_type,
            "valid_cases": valid_cases,
            "invalid_cases": invalid_cases,
            "mixed_type_case": mixed_type_case,
            "expander_preset": expander_preset,
        },
    )


for _args in ARRAY_DATATYPE_CASES:
    _test_cls = _make_test_class(*_args)
    globals()[_test_cls.__name__] = _test_cls


if __name__ == "__main__":
    unittest.main()
