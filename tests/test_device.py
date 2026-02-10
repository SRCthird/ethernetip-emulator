# Copyright 2022 Merck KGaA, Darmstadt, Germany and/or its affiliates.
# All rights reserved

import unittest
from unittest.mock import MagicMock
from src.server.device import build_argv, build_defaults, AttributeDevice


class TestDevice(unittest.TestCase):
    def test_build_argv_base_args_none(self):
        specs = [("A", "INT", 0)]
        self.assertEqual(build_argv(specs, base_args=None), ["A=INT"])

    def test_apply_default_sets_scalar_default(self):
        dev = AttributeDevice.__new__(AttributeDevice)
        dev._defaults = {"I_TEXT": 123}

        kwargs = {}
        dev._apply_default("I_TEXT", kwargs)

        self.assertEqual(kwargs["default"], 123)

    def test_apply_default_replaces_first_list_element(self):
        dev = AttributeDevice.__new__(AttributeDevice)
        dev._defaults = {"I_TEXT": 123}

        original = [0, 99]
        kwargs = {"default": original}
        dev._apply_default("I_TEXT", kwargs)

        self.assertEqual(kwargs["default"], [123, 99])
        self.assertIsNot(kwargs["default"], original)

    def test_setitem_triggers_action(self):
        actions = MagicMock()

        dev = AttributeDevice(
            name="X",
            type_cls=int,
            defaults={},
            actions=actions,
            registry={},
        )

        dev[0] = 42

        actions.on_set.assert_called_once_with(dev, 0, 42)

    def test_build_argv(self):
        specs = [("A", "INT", None), ("B", "BOOL", 0)]
        self.assertEqual(
            build_argv(specs, base_args=["--print"]), ["--print", "A=INT", "B=BOOL"]
        )

    def test_build_defaults_filters_none(self):
        specs = [("A", "INT", None), ("B", "BOOL", 0)]
        self.assertEqual(build_defaults(specs), {"B": 0})

    def test_apply_default_replaces_first_element_of_list(self):
        dev = AttributeDevice.__new__(AttributeDevice)
        dev._defaults = {"X": 7}
        kwargs = {"default": [0, 99]}
        dev._apply_default("X", kwargs)
        self.assertEqual(kwargs["default"], [7, 99])
