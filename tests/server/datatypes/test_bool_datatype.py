# Copyright 2026 Merck KGaA, Darmstadt, Germany and/or its affiliates.
# All rights reserved

# tests/server/datatypes/test_bool_datatype.py
from __future__ import annotations

import sys
import types
import unittest
from typing import Any
from unittest.mock import MagicMock

from src.ethernetip_emulator.server.actions import AttributeActions
from src.ethernetip_emulator.server import datatypes


def _install_cpppo_stubs() -> None:
    if "cpppo" in sys.modules and not isinstance(sys.modules["cpppo"], MagicMock):
        return

    class _BaseAttribute:
        def __init__(self, name: str, type_cls: Any, **kwargs: Any) -> None:
            self.name = name
            self.type_cls = type_cls
            self.kwargs = kwargs
            self._store: dict = {}

        def __setitem__(self, key, value) -> None:
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
    sys.modules.update(
        {
            "cpppo": cpppo_mod,
            "cpppo.server": server_mod,
            "cpppo.server.enip": enip_mod,
            "cpppo.server.enip.device": enip_device_mod,
        }
    )


_install_cpppo_stubs()


class _NotBool:
    def __bool__(self):
        raise TypeError("no bool conversion")


class TestBoolRegistration(unittest.TestCase):
    cls = datatypes.Bool
    registered_name = "bool"
    valid_inputs = [True, False, 1, 0]
    invalid_inputs = [_NotBool(), "", "yes"]

    def setUp(self):
        self.type_validator = self.cls.type_validator

    def test_has_type_validator(self):
        self.assertTrue(callable(getattr(self.cls, "type_validator", None)))

    def test_has_on_set_hook(self):
        self.assertTrue(callable(getattr(self.cls, "on_set_hook", None)))

    def test_has_on_change(self):
        self.assertTrue(callable(getattr(self.cls, "on_change", None)))

    def test_has_set_val(self):
        self.assertTrue(callable(getattr(self.cls, "set_val", None)))

    def test_has_get_val(self):
        self.assertTrue(callable(getattr(self.cls, "get_val", None)))

    def test_registered_on_actions(self):
        from src.ethernetip_emulator.server.device import actions

        self.assertIn(self.registered_name, actions._datatypes)

    def test_registered_instance_is_correct_type(self):
        from src.ethernetip_emulator.server.device import actions

        self.assertIsInstance(actions._datatypes.get(self.registered_name), self.cls)

    def test_instantiates_with_parent_actions(self):
        parent = MagicMock(spec=AttributeActions)
        self.assertIsNotNone(self.cls(parent))

    def test_type_validator_accepts_valid_inputs(self):
        for value in self.valid_inputs:
            with self.subTest(value=value):
                self.assertEqual(self.type_validator(value), value)

    def test_type_validator_rejects_invalid_inputs(self):
        for value in self.invalid_inputs:
            with self.subTest(value=value):
                with self.assertRaises(TypeError):
                    self.type_validator(value)

    def test_type_validator_coerces_via_typespec(self):
        from src.ethernetip_emulator.server.device import actions
        from src.ethernetip_emulator.server.actions import TypeSpec

        ts = actions.type.BOOL(1)
        self.assertIsInstance(ts, TypeSpec)
        self.assertEqual(ts.default, self.type_validator(1))


class TestBoolTag(unittest.TestCase):

    def setUp(self):
        from src.ethernetip_emulator.server.device import actions

        class _Attr:
            def __init__(self, name: str, values: list) -> None:
                self.name = name
                self._values = list(values)

            def __getitem__(self, key):
                return self._values[key]

            def __setitem__(self, key, value) -> None:
                self._values[key] = value

        attr = _Attr("test_bool", [1])
        self._fake_attr = attr

        class FakeAttrClass:
            registry = {"test_bool": attr}

        actions.bind(FakeAttrClass)

    def tearDown(self):
        from src.ethernetip_emulator.server.device import actions

        actions._attr_class_ref = None

    def test_tag_initial_value(self):
        from src.ethernetip_emulator.server.device import actions

        self.assertEqual(actions.bool.get_val("test_bool"), 1)

    def test_tag_set_value(self):
        from src.ethernetip_emulator.server.device import actions

        actions.bool.set_val("test_bool", 0)

        self.assertEqual(actions.bool.get_val("test_bool"), 0)


if __name__ == "__main__":
    unittest.main()
