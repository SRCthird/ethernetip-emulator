# Copyright 2026 Merck KGaA, Darmstadt, Germany and/or its affiliates.
# All rights reserved

# test/server/test_device.py
import unittest
from unittest.mock import patch

import threading
import time
import cpppo
import os
import signal
from cpppo.server.enip.main import main as enip_main
from cpppo.server.enip import device as enip_device
import cpppo.server.enip.parser as parser


from ethernetip_emulator.server.actions import TypeSpec
from ethernetip_emulator.server.device import AttributeDevice
from ethernetip_emulator.server.tag_specs import tag_registry
from ethernetip_emulator.server.device import actions

from tests.server import next_port


def _start_server(port: int) -> tuple:
    server_control = cpppo.apidict(timeout=1.0)
    AttributeDevice.set_server_control(server_control)

    def background_task():
        with AttributeDevice._actions.bind(AttributeDevice):
            enip_main(
                argv=tag_registry.build_argv(
                    base_args=["--print", "--address", f":{port}"]
                ),
                attribute_class=AttributeDevice,
                server={"control": server_control},
            )

    thread = threading.Thread(target=background_task, daemon=True)
    thread.start()
    time.sleep(0.5)
    return server_control, thread


def _stop_server(server_control, thread) -> None:
    server_control["done"] = True
    thread.join(timeout=5.0)
    tag_registry.invalidate()
    tag_registry._raw.clear()
    AttributeDevice.reset_defaults()


class TestAttributeDevice(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        @tag_registry.register
        def _():
            return [
                ("tag_int", actions.type.int(42)),
                ("tag_float", actions.type.real(3.14)),
                ("tag_string", actions.type.sstring("String")),
                ("tag_bool", actions.type.bool(False)),
            ]

        cls.server_control, cls.thread = _start_server(next_port())

    @classmethod
    def tearDownClass(cls) -> None:
        _stop_server(cls.server_control, cls.thread)

    def setUp(self) -> None:
        AttributeDevice._ensure_defaults()

    def test_ensure_defaults_populates_dict(self):
        self.assertIsNotNone(AttributeDevice._defaults)
        self.assertIn("tag_int", AttributeDevice._defaults)  # type: ignore
        self.assertIn("tag_float", AttributeDevice._defaults)  # type: ignore
        self.assertIn("tag_string", AttributeDevice._defaults)  # type: ignore
        self.assertIn("tag_bool", AttributeDevice._defaults)  # type: ignore

    def test_ensure_defaults_excludes_none_values(self):
        self.assertNotIn("tag_none", AttributeDevice._defaults)  # type: ignore

    def test_ensure_defaults_idempotent(self):
        first = dict(AttributeDevice._defaults)  # type: ignore
        AttributeDevice._ensure_defaults()
        self.assertEqual(first, AttributeDevice._defaults)  # type: ignore

    def test_defaults_correct_int_value(self):
        self.assertEqual(AttributeDevice._defaults.get("tag_int"), 42)  # type: ignore

    def test_defaults_correct_float_value(self):
        self.assertAlmostEqual(
            AttributeDevice._defaults.get("tag_float"), 3.14, places=5  # type: ignore
        )

    def test_defaults_correct_bool_value(self):
        self.assertEqual(AttributeDevice._defaults.get("tag_bool"), False)  # type: ignore

    def test_defaults_correct_string_value(self):
        self.assertEqual(AttributeDevice._defaults.get("tag_string"), "String")  # type: ignore

    def test_reset_defaults_clears_defaults(self):
        AttributeDevice._ensure_defaults()
        self.assertIsNotNone(AttributeDevice._defaults)
        AttributeDevice.reset_defaults()
        self.assertIsNone(AttributeDevice._defaults)

    def test_reset_defaults_clears_registry(self):
        AttributeDevice.reset_defaults()
        self.assertEqual(len(AttributeDevice.registry), 0)

    def test_typespec_real(self):
        ts = TypeSpec("real", 1.0)
        self.assertEqual(ts.type_name, "REAL")

    def test_typespec_int(self):
        ts = TypeSpec("int", 0)
        self.assertEqual(ts.type_name, "INT")

    def test_typespec_preserves_default(self):
        ts = TypeSpec("real", 9.9)
        self.assertAlmostEqual(ts.default, 9.9, places=5)


class TestAttributeDefaults(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.server_control, cls.thread = _start_server(next_port())

    @classmethod
    def tearDownClass(cls) -> None:
        _stop_server(cls.server_control, cls.thread)

    def test_ensure_defaults_called_implicitly_on_first_init(self):
        AttributeDevice.reset_defaults()
        tag_registry.invalidate()
        tag_registry._raw.clear()

        self.assertIsNone(AttributeDevice._defaults)

        @tag_registry.register
        def _():
            return [("tag_int", actions.type.int(42))]

        AttributeDevice._ensure_defaults()
        self.assertIsNotNone(AttributeDevice._defaults)

    def test_ensure_defaults_after_register(self):
        AttributeDevice.reset_defaults()
        tag_registry.invalidate()
        tag_registry._raw.clear()

        @tag_registry.register
        def _():
            return [("tag_extra", actions.type.int(7))]

        AttributeDevice._ensure_defaults()
        self.assertIn("tag_extra", AttributeDevice._defaults)  # type: ignore

    def test_defaults_only_non_none(self):
        AttributeDevice.reset_defaults()
        tag_registry.invalidate()
        tag_registry._raw.clear()

        @tag_registry.register
        def _():
            return [("tag_int", actions.type.int(42))]

        AttributeDevice._ensure_defaults()
        for val in AttributeDevice._defaults.values():  # type: ignore
            self.assertIsNotNone(val)

    def test_registry_empty_after_reset(self):
        AttributeDevice.reset_defaults()
        self.assertFalse(AttributeDevice.registry)


class TestShutdown(unittest.TestCase):

    def setUp(self):
        AttributeDevice.reset_defaults()
        tag_registry.invalidate()
        tag_registry._raw.clear()
        AttributeDevice._server_control = None

    def tearDown(self):
        AttributeDevice.reset_defaults()
        tag_registry.invalidate()
        tag_registry._raw.clear()
        AttributeDevice._server_control = None

    def test_shutdown_with_control_sets_done(self):
        ctrl = {}
        AttributeDevice._server_control = ctrl  # type: ignore
        AttributeDevice.shutdown()
        self.assertTrue(ctrl["done"])

    def test_shutdown_resets_defaults(self):
        ctrl = {}
        AttributeDevice._server_control = ctrl  # type: ignore

        @tag_registry.register
        def _():
            return [("tag_int", actions.type.int(1))]

        AttributeDevice._ensure_defaults()
        self.assertIsNotNone(AttributeDevice._defaults)

        AttributeDevice.shutdown()
        self.assertIsNone(AttributeDevice._defaults)

    def test_shutdown_without_control_sends_sigint(self):

        AttributeDevice._server_control = None

        with patch("os.kill") as mock_kill:
            AttributeDevice.shutdown()
            mock_kill.assert_called_once_with(os.getpid(), signal.SIGINT)


class TestApplyDefault(unittest.TestCase):
    def _make_device(self, name, type_cls, **kwargs):
        return AttributeDevice(name, type_cls, **kwargs)

    def setUp(self):
        AttributeDevice.reset_defaults()
        tag_registry.invalidate()
        tag_registry._raw.clear()

    def tearDown(self):
        AttributeDevice.reset_defaults()
        tag_registry.invalidate()
        tag_registry._raw.clear()

    def test_apply_default_skips_when_defaults_none(self):
        AttributeDevice._defaults = None
        kwargs = {"default": [0]}
        instance = AttributeDevice.__new__(AttributeDevice)
        instance._defaults = None
        instance._apply_default("any_tag", kwargs)
        self.assertEqual(kwargs, {"default": [0]})

    def test_apply_default_skips_unknown_name(self):
        AttributeDevice._defaults = {"tag_int": 42}
        kwargs = {"default": [0]}
        instance = AttributeDevice.__new__(AttributeDevice)
        instance._defaults = AttributeDevice._defaults
        instance._apply_default("unknown_tag", kwargs)
        self.assertEqual(kwargs, {"default": [0]})

    def test_apply_default_list_value_merges_into_list_configured_default(self):
        AttributeDevice._defaults = {"tag_arr": [10, 20]}
        kwargs = {"default": [0, 0, 0]}
        instance = AttributeDevice.__new__(AttributeDevice)
        instance._defaults = AttributeDevice._defaults
        instance._apply_default("tag_arr", kwargs)
        self.assertEqual(kwargs["default"], [10, 20, 0])

    def test_apply_default_list_value_replaces_non_list_configured_default(self):
        AttributeDevice._defaults = {"tag_arr": [7, 8, 9]}
        kwargs = {}
        instance = AttributeDevice.__new__(AttributeDevice)
        instance._defaults = AttributeDevice._defaults
        instance._apply_default("tag_arr", kwargs)
        self.assertEqual(kwargs["default"], [7, 8, 9])

    def test_apply_default_scalar_value_overwrites_first_slot_of_list(self):
        AttributeDevice._defaults = {"tag_int": 99}
        kwargs = {"default": [0, 0, 0]}
        instance = AttributeDevice.__new__(AttributeDevice)
        instance._defaults = AttributeDevice._defaults
        instance._apply_default("tag_int", kwargs)
        self.assertEqual(kwargs["default"], [99, 0, 0])

    def test_apply_default_scalar_value_replaces_empty_list(self):
        AttributeDevice._defaults = {"tag_int": 5}
        kwargs = {"default": []}
        instance = AttributeDevice.__new__(AttributeDevice)
        instance._defaults = AttributeDevice._defaults
        instance._apply_default("tag_int", kwargs)
        self.assertEqual(kwargs["default"], 5)

    def test_setitem_calls_on_set(self):
        on_set_calls = []

        @tag_registry.register
        def _():
            return [("tag_watch", actions.type.int(0))]

        AttributeDevice._ensure_defaults()

        original_on_set = AttributeDevice._actions.on_set
        try:
            AttributeDevice._actions.on_set = (
                lambda attr, key, val: on_set_calls.append((key, val))
            )  # type: ignore
            on_set_calls.clear()

            attr = AttributeDevice.__new__(AttributeDevice)
            attr._defaults = AttributeDevice._defaults
            attr._actions = AttributeDevice._actions
            attr._registry = AttributeDevice.registry
            enip_device.Attribute.__init__(attr, "tag_watch", parser.UDINT)
            attr[0] = 123
            self.assertTrue(any(val == 123 for _, val in on_set_calls))
        finally:
            AttributeDevice._actions.on_set = original_on_set

    def test_registry_empty_after_reset(self):
        AttributeDevice.reset_defaults()
        self.assertFalse(AttributeDevice.registry)


if __name__ == "__main__":
    unittest.main()
