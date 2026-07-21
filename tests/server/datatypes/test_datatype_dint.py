# Copyright 2026 Merck KGaA, Darmstadt, Germany and/or its affiliates.
# All rights reserved

# test/server/datatypes/test_datatype_dint.py
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
                lambda: [("tag_dint", actions.type.DINT(actions.dint.MAX + 1))]
            )

    def test_type_validator_below_min(self):
        with self.assertRaises(ValueError):
            tag_registry.register(
                lambda: [("tag_dint", actions.type.DINT(actions.dint.MIN - 1))]
            )

    def test_type_validator_non_numeric(self):
        with self.assertRaises((ValueError, TypeError)):
            tag_registry.register(
                lambda: [("tag_dint", actions.type.DINT("not_a_number"))]
            )

    def test_type_validator_at_max(self):
        tag_registry.register(
            lambda: [("tag_dint_max", actions.type.DINT(actions.dint.MAX))]
        )
        tag_registry.invalidate()
        tag_registry._raw.clear()

    def test_type_validator_at_min(self):
        tag_registry.register(
            lambda: [("tag_dint_min", actions.type.DINT(actions.dint.MIN))]
        )
        tag_registry.invalidate()
        tag_registry._raw.clear()

    def test_type_validator_coerces_float(self):
        tag_registry.register(lambda: [("tag_dint_float", actions.type.DINT(1.0))])
        tag_registry.invalidate()
        tag_registry._raw.clear()


class TestDatatypeDintActions(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        tag_registry.register(
            lambda: [
                ("tag_dint", actions.type.DINT(0)),
                ("tag_dint_array", actions.type.DINTARRAY((1, 2, 3, 4))),
            ]
        )

        cls.server_control, cls.thread = _start_server(next_port())

    @classmethod
    def tearDownClass(cls) -> None:
        _stop_server(cls.server_control, cls.thread)

    def setUp(self) -> None:
        AttributeDevice._ensure_defaults()

    def test_get_val(self):
        self.assertEqual(actions.dint.get_val("tag_dint"), 0)

    def test_get_val_is_array(self):
        v = actions.dint.get_val("tag_dint_array", slice(0, 4))
        self.assertIsInstance(v, list)

    def test_get_val_is_none(self):
        self.assertIsNone(actions.dint.get_val("no_tag"))

    def test_set_val(self):
        actions.dint.set_val("tag_dint", 42)
        self.assertEqual(actions.dint.get_val("tag_dint"), 42)

    def test_set_val_negative(self):
        actions.dint.set_val("tag_dint", -1)
        self.assertEqual(actions.dint.get_val("tag_dint"), -1)

    def test_set_val_max(self):
        actions.dint.set_val("tag_dint", actions.dint.MAX)
        self.assertEqual(actions.dint.get_val("tag_dint"), actions.dint.MAX)

    def test_set_val_min(self):
        actions.dint.set_val("tag_dint", actions.dint.MIN)
        self.assertEqual(actions.dint.get_val("tag_dint"), actions.dint.MIN)

    def test_set_val_is_none(self):
        self.assertIsNone(actions.dint.set_val("no_tag", 1))

    def test_on_change(self):
        changed = []

        @actions.dint.on_change("tag_dint")
        def _(attr, key, value):
            changed.append(value[0])

        actions.dint.set_val("tag_dint", 99)
        self.assertEqual(changed[-1], 99)

    def test_on_change_negative(self):
        changed = []

        @actions.dint.on_change("tag_dint")
        def _(attr, key, value):
            changed.append(value[0])

        actions.dint.set_val("tag_dint", -500)
        self.assertEqual(changed[-1], -500)
