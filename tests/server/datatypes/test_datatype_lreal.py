# Copyright 2026 Merck KGaA, Darmstadt, Germany and/or its affiliates.
# All rights reserved

# test/server/datatypes/test_datatype_lreal.py
import unittest

import threading
import time
import cpppo
from cpppo.server.enip.main import main as enip_main

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


class TestDatatypeLRealRegistry(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.server_control, cls.thread = _start_server(next_port())

    @classmethod
    def tearDownClass(cls) -> None:
        _stop_server(cls.server_control, cls.thread)

    def test_type_validator_non_numeric(self):
        with self.assertRaises((ValueError, TypeError)):
            tag_registry.register(
                lambda: [("tag_lreal", actions.type.LREAL("not_a_number"))]
            )

    def test_type_validator_coerces_float(self):
        tag_registry.register(lambda: [("tag_lreal_float", actions.type.LREAL(1.0))])
        tag_registry.invalidate()
        tag_registry._raw.clear()

    def test_array_type_validator_is_not_list(self):
        with self.assertRaises((ValueError, TypeError)):
            tag_registry.register(
                lambda: [("tag_lreal_array", actions.type.LREALARRAY("not_a_list"))]
            )

    def test_array_type_validator_empty_list(self):
        with self.assertRaises((ValueError, TypeError)):
            tag_registry.register(
                lambda: [("tag_lreal_array", actions.type.LREALARRAY([]))]
            )

    def test_array_type_validator_not_a_number(self):
        with self.assertRaises((ValueError, TypeError)):
            tag_registry.register(
                lambda: [("tag_lreal_array", actions.type.LREALARRAY(["not_a_number"]))]
            )

    def test_array_type_validator_coerces_float(self):
        tag_registry.register(
            lambda: [("tag_lreal_float", actions.type.LREALARRAY([1.0, 2.0]))]
        )
        tag_registry.invalidate()
        tag_registry._raw.clear()


class TestDatatypeLRealActions(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        tag_registry.register(
            lambda: [
                ("tag_lreal", actions.type.LREAL(0.0)),
                ("tag_lreal_array", actions.type.LREALARRAY([0.0, 0.0, 0.0, 0.0])),
            ]
        )

        cls.server_control, cls.thread = _start_server(next_port())

    @classmethod
    def tearDownClass(cls) -> None:
        _stop_server(cls.server_control, cls.thread)

    def setUp(self) -> None:
        AttributeDevice._ensure_defaults()
        actions._lookup("tag_lreal")[slice(0, 1)] = [0.0]  # type: ignore
        actions._lookup("tag_lreal_array")[slice(0, 4)] = [0.0, 0.0, 0.0, 0.0]  # type: ignore

    def test_get_val(self):
        self.assertEqual(actions.lreal.get_val("tag_lreal"), 0.0)

    def test_get_val_is_array(self):
        v = actions.lreal.get_val("tag_lreal_array", slice(0, 4))
        self.assertIsInstance(v, list)

    def test_get_val_is_none(self):
        self.assertIsNone(actions.lreal.get_val("no_tag"))

    def test_set_val(self):
        actions.lreal.set_val("tag_lreal", 42.42)
        self.assertEqual(actions.lreal.get_val("tag_lreal"), 42.42)

    def test_set_val_negative(self):
        actions.lreal.set_val("tag_lreal", -1.0)
        self.assertEqual(actions.lreal.get_val("tag_lreal"), -1.0)

    def test_set_val_is_none(self):
        self.assertIsNone(actions.lreal.set_val("no_tag", 1))

    def test_on_change(self):
        changed = []

        @actions.lreal.on_change("tag_lreal")
        def _(attr, key, value):
            changed.append(value[0])

        actions.lreal.set_val("tag_lreal", 99.0)
        self.assertEqual(changed[-1], 99.0)

    def test_on_change_negative(self):
        changed = []

        @actions.lreal.on_change("tag_lreal")
        def _(attr, key, value):
            changed.append(value[0])

        actions.lreal.set_val("tag_lreal", -500.99)
        self.assertEqual(changed[-1], -500.99)

    def test_array_get_val(self):
        self.assertEqual(
            actions.lrealarray.get_val("tag_lreal_array"), [0.0, 0.0, 0.0, 0.0]
        )

    def test_array_slice_get_val(self):
        self.assertEqual(
            actions.lrealarray.get_val("tag_lreal_array", slice(0, 1)), [0.0]
        )
        self.assertEqual(
            actions.lrealarray.get_val("tag_lreal_array", slice(0, 2)), [0.0, 0.0]
        )
        self.assertEqual(
            actions.lrealarray.get_val("tag_lreal_array", slice(0, 3)),
            [0.0, 0.0, 0.0],
        )
        self.assertEqual(
            actions.lrealarray.get_val("tag_lreal_array", slice(0, 4)),
            [0.0, 0.0, 0.0, 0.0],
        )

    def test_array_get_val_is_empty(self):
        v = actions.lrealarray.get_val("no_tag")
        self.assertEqual(v, [])

    def test_array_set_val(self):
        v = [1.2, 3.4, 5.6, 6.7]
        actions.lrealarray.set_val("tag_lreal_array", v)
        self.assertEqual(actions.lrealarray.get_val("tag_lreal_array"), v)

    def test_array_set_val_slice(self):
        v = 99.99
        actions.lrealarray.set_val("tag_lreal_array", [v], slice(0, 1))
        actions.lrealarray.set_val("tag_lreal_array", [v], slice(1, 2))
        actions.lrealarray.set_val("tag_lreal_array", [v], slice(2, 3))
        actions.lrealarray.set_val("tag_lreal_array", [v], slice(3, 4))
        rv = actions.lrealarray.get_val("tag_lreal_array")
        for i, val in enumerate(rv):
            with self.subTest(number=i):
                self.assertEqual(val, v)

    def test_array_set_val_is_none(self):
        v = actions.lrealarray.set_val("no_tag", [10.0])
        self.assertIsNone(v)

    def test_array_on_change(self):
        changed = []
        v = 98.76

        @actions.lrealarray.on_change("tag_lreal_array", key=slice(0, 1))
        def _(attr, key, value):
            changed.append(value[0])

        actions.lrealarray.set_val("tag_lreal_array", [v], slice(0, 1))
        self.assertEqual(changed[-1], v)

    def test_array_on_change_no_slice(self):
        changed = []
        v = [5.0, 10.0, 15.0, 20.0]

        @actions.lrealarray.on_change("tag_lreal_array")
        def _(attr, key, value):
            changed.append(value)

        actions.lrealarray.set_val("tag_lreal_array", v, slice(0, 4))
        self.assertEqual(changed[-1], v)

    def test_array_append(self):
        actions.lrealarray.append("tag_lreal_array", 10.10)
        self.assertEqual(
            actions.lrealarray.get_val("tag_lreal_array"), [10.10, 0.0, 0.0, 0.0]
        )

    def test_array_append_is_full(self):
        actions.lrealarray.set_val("tag_lreal_array", [10.0, 20.0, 30.0, 40.0])
        v = actions.lrealarray.append("tag_lreal_array", 5.0)
        self.assertFalse(v)

    def test_array_prepend(self):
        actions.lrealarray.prepend("tag_lreal_array", 67.0)
        self.assertEqual(
            actions.lrealarray.get_val("tag_lreal_array"), [0.0, 0.0, 0.0, 67.0]
        )

    def test_array_prepend_is_full(self):
        actions.lrealarray.set_val("tag_lreal_array", [10.0, 20.0, 30.0, 40.0])
        v = actions.lrealarray.prepend("tag_lreal_array", 5.0)
        self.assertFalse(v)

    def test_array_pop(self):
        actions.lrealarray.set_val("tag_lreal_array", [10.0, 20.0, 30.0, 40.0])
        v = actions.lrealarray.pop("tag_lreal_array")
        self.assertEqual(v, 40)
        self.assertEqual(
            actions.lrealarray.get_val("tag_lreal_array"), [10.0, 20.0, 30.0, 0.0]
        )

    def test_array_pop_is_empty(self):
        v = actions.lrealarray.pop("tag_lreal_array")
        self.assertIsNone(v)

    def test_array_insert(self):
        actions.lrealarray.insert("tag_lreal_array", 2, 99.0)
        self.assertEqual(
            actions.lrealarray.get_val("tag_lreal_array"), [0.0, 0.0, 99.0, 0.0]
        )

    def test_array_insert_is_full(self):
        actions.lrealarray.set_val("tag_lreal_array", [10.0, 20.0, 30.0, 40.0])
        v = actions.lrealarray.insert("tag_lreal_array", 2, 99.0)
        self.assertFalse(v)

    def test_array_remove(self):
        actions.lrealarray.set_val("tag_lreal_array", [10.0, 20.0, 30.0, 40.0])
        v = actions.lrealarray.remove("tag_lreal_array", 2)
        self.assertEqual(v, 30.0)
        self.assertEqual(
            actions.lrealarray.get_val("tag_lreal_array"), [10.0, 20.0, 40.0, 0.0]
        )

    def test_array_remove_is_empty(self):
        v = actions.lrealarray.remove("tag_lreal_array", 2)
        self.assertIsNone(v)

    def test_array_count(self):
        actions.lrealarray.set_val("tag_lreal_array", [10.0, 0.0, 30.0, 0.0])
        self.assertEqual(actions.lrealarray.count("tag_lreal_array"), 2)

    def test_array_is_full(self):
        actions.lrealarray.set_val("tag_lreal_array", [10.0, 20.0, 30.0, 40.0])
        self.assertEqual(actions.lrealarray.is_full("tag_lreal_array"), True)

    def test_array_is_not_full(self):
        self.assertEqual(actions.lrealarray.is_full("tag_lreal_array"), False)

    def test_array_is_empty(self):
        self.assertEqual(actions.lrealarray.is_empty("tag_lreal_array"), True)

    def test_array_is_not_empty(self):
        actions.lrealarray.set_val("tag_lreal_array", [10.0, 20.0, 30.0, 40.0])
        self.assertEqual(actions.lrealarray.is_empty("tag_lreal_array"), False)

    def test_array_find(self):
        actions.lrealarray.set_val("tag_lreal_array", [10.0, 20.0, 30.0, 40.0])
        v = actions.lrealarray.find("tag_lreal_array", 20.0)
        self.assertEqual(v, 1)

    def test_array_not_found(self):
        actions.lrealarray.set_val("tag_lreal_array", [10.0, 20.0, 30.0, 40.0])
        v = actions.lrealarray.find("tag_lreal_array", 67.8)
        self.assertIsNone(v)

    def test_array_clear(self):
        actions.lrealarray.set_val("tag_lreal_array", [10.0, 20.0, 30.0, 40.0])
        actions.lrealarray.clear("tag_lreal_array")
        self.assertEqual(actions.lrealarray.is_empty("tag_lreal_array"), True)
