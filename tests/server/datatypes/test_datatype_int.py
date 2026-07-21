# Copyright 2026 Merck KGaA, Darmstadt, Germany and/or its affiliates.
# All rights reserved

# test/server/datatypes/test_datatype_int.py
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


class TestDatatypeDintRegistry(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.server_control, cls.thread = _start_server(next_port())

    @classmethod
    def tearDownClass(cls) -> None:
        _stop_server(cls.server_control, cls.thread)

    def test_type_validator_above_max(self):
        with self.assertRaises(ValueError):
            tag_registry.register(
                lambda: [("tag_int", actions.type.INT(actions.int.MAX + 1))]
            )

    def test_type_validator_below_min(self):
        with self.assertRaises(ValueError):
            tag_registry.register(
                lambda: [("tag_int", actions.type.INT(actions.int.MIN - 1))]
            )

    def test_type_validator_non_numeric(self):
        with self.assertRaises((ValueError, TypeError)):
            tag_registry.register(
                lambda: [("tag_int", actions.type.int("not_a_number"))]
            )

    def test_type_validator_at_max(self):
        tag_registry.register(
            lambda: [("tag_int_max", actions.type.INT(actions.int.MAX))]
        )
        tag_registry.invalidate()
        tag_registry._raw.clear()

    def test_type_validator_at_min(self):
        tag_registry.register(
            lambda: [("tag_int_min", actions.type.INT(actions.int.MIN))]
        )
        tag_registry.invalidate()
        tag_registry._raw.clear()

    def test_type_validator_coerces_float(self):
        tag_registry.register(lambda: [("tag_int_float", actions.type.INT(1.0))])
        tag_registry.invalidate()
        tag_registry._raw.clear()


class TestDatatypeDintActions(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        tag_registry.register(
            lambda: [
                ("tag_int", actions.type.INT(0)),
                ("tag_int_array", actions.type.INTARRAY((1, 2, 3, 4))),
            ]
        )

        cls.server_control, cls.thread = _start_server(next_port())

    @classmethod
    def tearDownClass(cls) -> None:
        _stop_server(cls.server_control, cls.thread)

    def setUp(self) -> None:
        AttributeDevice._ensure_defaults()

    def test_get_val(self):
        self.assertEqual(actions.int.get_val("tag_int"), 0)

    def test_get_val_is_array(self):
        v = actions.int.get_val("tag_int_array", slice(0, 4))
        self.assertIsInstance(v, list)

    def test_get_val_is_none(self):
        self.assertIsNone(actions.int.get_val("no_tag"))

    def test_set_val(self):
        actions.int.set_val("tag_int", 42)
        self.assertEqual(actions.int.get_val("tag_int"), 42)

    def test_set_val_negative(self):
        actions.int.set_val("tag_int", -1)
        self.assertEqual(actions.int.get_val("tag_int"), -1)

    def test_set_val_max(self):
        actions.int.set_val("tag_int", actions.int.MAX)
        self.assertEqual(actions.int.get_val("tag_int"), actions.int.MAX)

    def test_set_val_min(self):
        actions.int.set_val("tag_int", actions.int.MIN)
        self.assertEqual(actions.int.get_val("tag_int"), actions.int.MIN)

    def test_set_val_is_none(self):
        self.assertIsNone(actions.int.set_val("no_tag", 1))

    def test_on_change(self):
        changed = []

        @actions.int.on_change("tag_int")
        def _(attr, key, value):
            changed.append(value[0])

        actions.int.set_val("tag_int", 99)
        self.assertEqual(changed[-1], 99)

    def test_on_change_negative(self):
        changed = []

        @actions.int.on_change("tag_int")
        def _(attr, key, value):
            changed.append(value[0])

        actions.int.set_val("tag_int", -500)
        self.assertEqual(changed[-1], -500)
