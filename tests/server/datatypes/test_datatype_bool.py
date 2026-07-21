# Copyright 2026 Merck KGaA, Darmstadt, Germany and/or its affiliates.
# All rights reserved

# test/server/datatypes/test_datatype_bool.py
import unittest

import threading
import time
import cpppo
from cpppo.server.enip.main import main as enip_main

from src.ethernetip_emulator.server.device import AttributeDevice
from src.ethernetip_emulator.server.tag_specs import tag_registry
from src.ethernetip_emulator.server.device import actions
from tests.server import next_port


def _start_server(port: int) -> tuple:
    server_control = cpppo.apidict(timeout=1.0)
    AttributeDevice.set_server_control(server_control)

    def background_task():
        with AttributeDevice._actions.bind(AttributeDevice):
            enip_main(
                argv=tag_registry.build_argv(base_args=["--address", f":{port}"]),
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


class TestDatatypeBoolRegistry(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.server_control, cls.thread = _start_server(next_port())

    @classmethod
    def tearDownClass(cls) -> None:
        _stop_server(cls.server_control, cls.thread)

    def test_type_validator_invalid(self):
        with self.assertRaises(ValueError):
            tag_registry.register(lambda: [("tag_bool", actions.type.BOOL(42))])


class TestDatatypeBoolActions(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        @tag_registry.register
        def _():
            return [
                ("tag_bool", actions.type.BOOL(True)),
                ("tag_array", actions.type.BOOLARRAY((True, True, True, True))),
            ]

        cls.server_control, cls.thread = _start_server(next_port())

    @classmethod
    def tearDownClass(cls) -> None:
        _stop_server(cls.server_control, cls.thread)

    def setUp(self) -> None:
        AttributeDevice._ensure_defaults()

    def test_get_val(self):
        self.assertEqual(actions.bool.get_val("tag_bool"), True)

    def test_get_val_is_array(self):
        v = actions.bool.get_val("tag_array", slice(0, 4))
        self.assertIsInstance(v, list)

    def test_get_val_is_none(self):
        v = actions.bool.get_val("no_tag")
        self.assertIsNone(v)

    def test_set_val(self):
        actions.bool.set_val("tag_bool", False)
        self.assertEqual(actions.bool.get_val("tag_bool"), False)

    def test_set_val_is_none(self):
        v = actions.bool.set_val("no_tag", True)
        self.assertIsNone(v)

    def test_on_change(self):
        changed = []

        @actions.bool.on_change("tag_bool")
        def _(attr, key, value):
            changed.append(value[0])

        actions.bool.set_val("tag_bool", True)
        self.assertEqual(changed[-1], True)
