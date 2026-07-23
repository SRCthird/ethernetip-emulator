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


class TestDatatypeIntRegistry(unittest.TestCase):

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
                lambda: [("tag_int", actions.type.INT("not_a_number"))]
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

    def test_array_type_validator_is_not_tuple(self):
        with self.assertRaises((ValueError, TypeError)):
            tag_registry.register(
                lambda: [("tag_int_array", actions.type.INTARRAY("not_a_tuple"))]
            )

    def test_array_type_validator_empty_tuple(self):
        with self.assertRaises((ValueError, TypeError)):
            tag_registry.register(
                lambda: [("tag_int_array", actions.type.INTARRAY([]))]
            )

    def test_array_type_validator_not_a_number(self):
        with self.assertRaises((ValueError, TypeError)):
            tag_registry.register(
                lambda: [
                    (
                        "tag_int_array",
                        actions.type.INTARRAY(
                            [
                                "not_a_number",
                            ]
                        ),
                    )
                ]
            )

    def test_array_type_validator_above_max(self):
        with self.assertRaises(ValueError):
            tag_registry.register(
                lambda: [
                    (
                        "tag_int",
                        actions.type.INTARRAY(
                            [
                                actions.int.MAX + 1,
                            ]
                        ),
                    )
                ]
            )

    def test_array_type_validator_below_min(self):
        with self.assertRaises(ValueError):
            tag_registry.register(
                lambda: [
                    (
                        "tag_int",
                        actions.type.INTARRAY(
                            [
                                actions.int.MIN - 1,
                            ]
                        ),
                    )
                ]
            )


class TestDatatypeIntActions(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        tag_registry.register(
            lambda: [
                ("tag_int", actions.type.INT(0)),
                ("tag_int_array", actions.type.INTARRAY([0, 0, 0, 0])),
            ]
        )

        cls.server_control, cls.thread = _start_server(next_port())

    @classmethod
    def tearDownClass(cls) -> None:
        _stop_server(cls.server_control, cls.thread)

    def setUp(self) -> None:
        AttributeDevice._ensure_defaults()
        actions._lookup("tag_int")[slice(0, 1)] = [0]  # type: ignore
        actions._lookup("tag_int_array")[slice(0, 4)] = [0, 0, 0, 0]  # type: ignore

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

    def test_array_get_val(self):
        self.assertEqual(actions.intarray.get_val("tag_int_array"), [0, 0, 0, 0])

    def test_array_slice_get_val(self):
        self.assertEqual(actions.intarray.get_val("tag_int_array", slice(0, 1)), [0])
        self.assertEqual(actions.intarray.get_val("tag_int_array", slice(0, 2)), [0, 0])
        self.assertEqual(
            actions.intarray.get_val("tag_int_array", slice(0, 3)),
            [0, 0, 0],
        )
        self.assertEqual(
            actions.intarray.get_val("tag_int_array", slice(0, 4)),
            [0, 0, 0, 0],
        )

    def test_array_get_val_is_empty(self):
        v = actions.intarray.get_val("no_tag")
        self.assertEqual(v, [])

    def test_array_set_val(self):
        v = [1, 2, 3, 4]
        actions.intarray.set_val("tag_int_array", v)
        self.assertEqual(actions.intarray.get_val("tag_int_array"), v)

    def test_array_set_val_slice(self):
        v = 99
        actions.intarray.set_val("tag_int_array", [v], slice(0, 1))
        actions.intarray.set_val("tag_int_array", [v], slice(1, 2))
        actions.intarray.set_val("tag_int_array", [v], slice(2, 3))
        actions.intarray.set_val("tag_int_array", [v], slice(3, 4))
        rv = actions.intarray.get_val("tag_int_array")
        for i, val in enumerate(rv):
            with self.subTest(number=i):
                self.assertEqual(val, v)

    def test_array_set_val_is_none(self):
        v = actions.intarray.set_val("no_tag", [10])
        self.assertIsNone(v)

    def test_array_on_change(self):
        changed = []
        v = 99

        @actions.intarray.on_change("tag_int_array", key=slice(0, 1))
        def _(attr, key, value):
            changed.append(value[0])

        actions.intarray.set_val("tag_int_array", [v], slice(0, 1))
        self.assertEqual(changed[-1], v)

    def test_array_on_change_no_slice(self):
        changed = []
        v = [5, 10, 15, 20]

        @actions.intarray.on_change("tag_int_array")
        def _(attr, key, value):
            changed.append(value)

        actions.intarray.set_val("tag_int_array", v, slice(0, 4))
        self.assertEqual(changed[-1], v)

    def test_array_append(self):
        actions.intarray.append("tag_int_array", 10)
        self.assertEqual(actions.intarray.get_val("tag_int_array"), [10, 0, 0, 0])

    def test_array_append_is_full(self):
        actions.intarray.set_val("tag_int_array", [10, 20, 30, 40])
        v = actions.intarray.append("tag_int_array", 5)
        self.assertEqual(v, 0)

    def test_array_prepend(self):
        actions.intarray.prepend("tag_int_array", 67)
        self.assertEqual(actions.intarray.get_val("tag_int_array"), [0, 0, 0, 67])

    def test_array_prepend_is_full(self):
        actions.intarray.set_val("tag_int_array", [10, 20, 30, 40])
        v = actions.intarray.prepend("tag_int_array", 5)
        self.assertEqual(v, 0)

    def test_array_pop(self):
        actions.intarray.set_val("tag_int_array", [10, 20, 30, 40])
        v = actions.intarray.pop("tag_int_array")
        self.assertEqual(v, 40)
        self.assertEqual(actions.intarray.get_val("tag_int_array"), [10, 20, 30, 0])

    def test_array_pop_is_empty(self):
        v = actions.intarray.pop("tag_int_array")
        self.assertIsNone(v)

    def test_array_insert(self):
        actions.intarray.insert("tag_int_array", 2, 99)
        self.assertEqual(actions.intarray.get_val("tag_int_array"), [0, 0, 99, 0])

    def test_array_insert_is_full(self):
        actions.intarray.set_val("tag_int_array", [10, 20, 30, 40])
        v = actions.intarray.insert("tag_int_array", 2, 99)
        self.assertEqual(v, 0)

    def test_array_remove(self):
        actions.intarray.set_val("tag_int_array", [10, 20, 30, 40])
        v = actions.intarray.remove("tag_int_array", 2)
        self.assertEqual(v, 30)
        self.assertEqual(actions.intarray.get_val("tag_int_array"), [10, 20, 40, 0])

    def test_array_remove_is_empty(self):
        v = actions.intarray.remove("tag_int_array", 2)
        self.assertIsNone(v)

    def test_array_count(self):
        actions.intarray.set_val("tag_int_array", [10, 0, 30, 0])
        self.assertEqual(actions.intarray.count("tag_int_array"), 2)

    def test_array_is_full(self):
        actions.intarray.set_val("tag_int_array", [10, 20, 30, 40])
        self.assertEqual(actions.intarray.is_full("tag_int_array"), True)

    def test_array_is_not_full(self):
        self.assertEqual(actions.intarray.is_full("tag_int_array"), False)

    def test_array_is_empty(self):
        self.assertEqual(actions.intarray.is_empty("tag_int_array"), True)

    def test_array_is_not_empty(self):
        actions.intarray.set_val("tag_int_array", [10, 20, 30, 40])
        self.assertEqual(actions.intarray.is_empty("tag_int_array"), False)

    def test_array_find(self):
        actions.intarray.set_val("tag_int_array", [10, 20, 30, 40])
        v = actions.intarray.find("tag_int_array", 20)
        self.assertEqual(v, 1)

    def test_array_not_found(self):
        actions.intarray.set_val("tag_int_array", [10, 20, 30, 40])
        v = actions.intarray.find("tag_int_array", 67)
        self.assertIsNone(v)

    def test_array_clear(self):
        actions.intarray.set_val("tag_int_array", [10, 20, 30, 40])
        actions.intarray.clear("tag_int_array")
        self.assertEqual(actions.intarray.is_empty("tag_int_array"), True)
