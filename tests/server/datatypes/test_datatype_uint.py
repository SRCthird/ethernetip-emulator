# Copyright 2026 Merck KGaA, Darmstadt, Germany and/or its affiliates.
# All rights reserved

# test/server/datatypes/test_datatype_uint.py
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


class TestDatatypeUIntRegistry(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.server_control, cls.thread = _start_server(next_port())

    @classmethod
    def tearDownClass(cls) -> None:
        _stop_server(cls.server_control, cls.thread)

    def test_type_validator_above_max(self):
        with self.assertRaises(ValueError):
            tag_registry.register(
                lambda: [("tag_uint", actions.type.UINT(actions.uint.MAX + 1))]
            )

    def test_type_validator_below_min(self):
        with self.assertRaises(ValueError):
            tag_registry.register(
                lambda: [("tag_uint", actions.type.UINT(actions.uint.MIN - 1))]
            )

    def test_type_validator_non_numeric(self):
        with self.assertRaises((ValueError, TypeError)):
            tag_registry.register(
                lambda: [("tag_uint", actions.type.UINT("not_a_number"))]
            )

    def test_type_validator_at_max(self):
        tag_registry.register(
            lambda: [("tag_uint_max", actions.type.UINT(actions.uint.MAX))]
        )
        tag_registry.invalidate()
        tag_registry._raw.clear()

    def test_type_validator_at_min(self):
        tag_registry.register(
            lambda: [("tag_uint_min", actions.type.UINT(actions.uint.MIN))]
        )
        tag_registry.invalidate()
        tag_registry._raw.clear()

    def test_type_validator_coerces_float(self):
        tag_registry.register(lambda: [("tag_uint_float", actions.type.UINT(1.0))])
        tag_registry.invalidate()
        tag_registry._raw.clear()

    def test_array_type_validator_is_not_tuple(self):
        with self.assertRaises((ValueError, TypeError)):
            tag_registry.register(
                lambda: [("tag_uint_array", actions.type.UINTARRAY("not_a_tuple"))]
            )

    def test_array_type_validator_empty_tuple(self):
        with self.assertRaises((ValueError, TypeError)):
            tag_registry.register(
                lambda: [("tag_uint_array", actions.type.UINTARRAY([]))]
            )

    def test_array_type_validator_not_a_number(self):
        with self.assertRaises((ValueError, TypeError)):
            tag_registry.register(
                lambda: [
                    (
                        "tag_uint_array",
                        actions.type.UINTARRAY(
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
                        "tag_uint",
                        actions.type.UINTARRAY(
                            [
                                actions.uint.MAX + 1,
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
                        "tag_uint",
                        actions.type.UINTARRAY(
                            [
                                actions.uint.MIN - 1,
                            ]
                        ),
                    )
                ]
            )


class TestDatatypeUIntActions(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        tag_registry.register(
            lambda: [
                ("tag_uint", actions.type.UINT(0)),
                ("tag_uint_array", actions.type.UINTARRAY([0, 0, 0, 0])),
            ]
        )

        cls.server_control, cls.thread = _start_server(next_port())

    @classmethod
    def tearDownClass(cls) -> None:
        _stop_server(cls.server_control, cls.thread)

    def setUp(self) -> None:
        AttributeDevice._ensure_defaults()
        actions._lookup("tag_uint")[slice(0, 1)] = [0]  # type: ignore
        actions._lookup("tag_uint_array")[slice(0, 4)] = [0, 0, 0, 0]  # type: ignore

    def test_get_val(self):
        self.assertEqual(actions.uint.get_val("tag_uint"), 0)

    def test_get_val_is_array(self):
        v = actions.uint.get_val("tag_uint_array", slice(0, 4))
        self.assertIsInstance(v, list)

    def test_get_val_is_none(self):
        self.assertIsNone(actions.uint.get_val("no_tag"))

    def test_set_val(self):
        actions.uint.set_val("tag_uint", 42)
        self.assertEqual(actions.uint.get_val("tag_uint"), 42)

    def test_set_val_negative(self):
        with self.assertRaises(ValueError):
            actions.uint.set_val("tag_uint", -1)

    def test_set_val_max(self):
        actions.uint.set_val("tag_uint", actions.uint.MAX)
        self.assertEqual(actions.uint.get_val("tag_uint"), actions.uint.MAX)

    def test_set_val_min(self):
        actions.uint.set_val("tag_uint", actions.uint.MIN)
        self.assertEqual(actions.uint.get_val("tag_uint"), actions.uint.MIN)

    def test_set_val_is_none(self):
        self.assertIsNone(actions.uint.set_val("no_tag", 1))

    def test_on_change(self):
        changed = []

        @actions.uint.on_change("tag_uint")
        def _(attr, key, value):
            changed.append(value[0])

        actions.uint.set_val("tag_uint", 99)
        self.assertEqual(changed[-1], 99)

    def test_array_get_val(self):
        self.assertEqual(actions.uintarray.get_val("tag_uint_array"), [0, 0, 0, 0])

    def test_array_slice_get_val(self):
        self.assertEqual(actions.uintarray.get_val("tag_uint_array", slice(0, 1)), [0])
        self.assertEqual(
            actions.uintarray.get_val("tag_uint_array", slice(0, 2)), [0, 0]
        )
        self.assertEqual(
            actions.uintarray.get_val("tag_uint_array", slice(0, 3)),
            [0, 0, 0],
        )
        self.assertEqual(
            actions.uintarray.get_val("tag_uint_array", slice(0, 4)),
            [0, 0, 0, 0],
        )

    def test_array_get_val_is_empty(self):
        v = actions.uintarray.get_val("no_tag")
        self.assertEqual(v, [])

    def test_array_set_val(self):
        v = [1, 2, 3, 4]
        actions.uintarray.set_val("tag_uint_array", v)
        self.assertEqual(actions.uintarray.get_val("tag_uint_array"), v)

    def test_array_set_val_slice(self):
        v = 99
        actions.uintarray.set_val("tag_uint_array", [v], slice(0, 1))
        actions.uintarray.set_val("tag_uint_array", [v], slice(1, 2))
        actions.uintarray.set_val("tag_uint_array", [v], slice(2, 3))
        actions.uintarray.set_val("tag_uint_array", [v], slice(3, 4))
        rv = actions.uintarray.get_val("tag_uint_array")
        for i, val in enumerate(rv):
            with self.subTest(number=i):
                self.assertEqual(val, v)

    def test_array_set_val_is_none(self):
        v = actions.uintarray.set_val("no_tag", [10])
        self.assertIsNone(v)

    def test_array_on_change(self):
        changed = []
        v = 99

        @actions.uintarray.on_change("tag_uint_array", key=slice(0, 1))
        def _(attr, key, value):
            changed.append(value[0])

        actions.uintarray.set_val("tag_uint_array", [v], slice(0, 1))
        self.assertEqual(changed[-1], v)

    def test_array_on_change_no_slice(self):
        changed = []
        v = [5, 10, 15, 20]

        @actions.uintarray.on_change("tag_uint_array")
        def _(attr, key, value):
            changed.append(value)

        actions.uintarray.set_val("tag_uint_array", v, slice(0, 4))
        self.assertEqual(changed[-1], v)

    def test_array_append(self):
        actions.uintarray.append("tag_uint_array", 10)
        self.assertEqual(actions.uintarray.get_val("tag_uint_array"), [10, 0, 0, 0])

    def test_array_append_is_full(self):
        actions.uintarray.set_val("tag_uint_array", [10, 20, 30, 40])
        v = actions.uintarray.append("tag_uint_array", 5)
        self.assertEqual(v, 0)

    def test_array_prepend(self):
        actions.uintarray.prepend("tag_uint_array", 67)
        self.assertEqual(actions.uintarray.get_val("tag_uint_array"), [0, 0, 0, 67])

    def test_array_prepend_is_full(self):
        actions.uintarray.set_val("tag_uint_array", [10, 20, 30, 40])
        v = actions.uintarray.prepend("tag_uint_array", 5)
        self.assertEqual(v, 0)

    def test_array_pop(self):
        actions.uintarray.set_val("tag_uint_array", [10, 20, 30, 40])
        v = actions.uintarray.pop("tag_uint_array")
        self.assertEqual(v, 40)
        self.assertEqual(actions.uintarray.get_val("tag_uint_array"), [10, 20, 30, 0])

    def test_array_pop_is_empty(self):
        v = actions.uintarray.pop("tag_uint_array")
        self.assertIsNone(v)

    def test_array_insert(self):
        actions.uintarray.insert("tag_uint_array", 2, 99)
        self.assertEqual(actions.uintarray.get_val("tag_uint_array"), [0, 0, 99, 0])

    def test_array_insert_is_full(self):
        actions.uintarray.set_val("tag_uint_array", [10, 20, 30, 40])
        v = actions.uintarray.insert("tag_uint_array", 2, 99)
        self.assertEqual(v, 0)

    def test_array_remove(self):
        actions.uintarray.set_val("tag_uint_array", [10, 20, 30, 40])
        v = actions.uintarray.remove("tag_uint_array", 2)
        self.assertEqual(v, 30)
        self.assertEqual(actions.uintarray.get_val("tag_uint_array"), [10, 20, 40, 0])

    def test_array_remove_is_empty(self):
        v = actions.uintarray.remove("tag_uint_array", 2)
        self.assertIsNone(v)

    def test_array_count(self):
        actions.uintarray.set_val("tag_uint_array", [10, 0, 30, 0])
        self.assertEqual(actions.uintarray.count("tag_uint_array"), 2)

    def test_array_is_full(self):
        actions.uintarray.set_val("tag_uint_array", [10, 20, 30, 40])
        self.assertEqual(actions.uintarray.is_full("tag_uint_array"), True)

    def test_array_is_not_full(self):
        self.assertEqual(actions.uintarray.is_full("tag_uint_array"), False)

    def test_array_is_empty(self):
        self.assertEqual(actions.uintarray.is_empty("tag_uint_array"), True)

    def test_array_is_not_empty(self):
        actions.uintarray.set_val("tag_uint_array", [10, 20, 30, 40])
        self.assertEqual(actions.uintarray.is_empty("tag_uint_array"), False)

    def test_array_find(self):
        actions.uintarray.set_val("tag_uint_array", [10, 20, 30, 40])
        v = actions.uintarray.find("tag_uint_array", 20)
        self.assertEqual(v, 1)

    def test_array_not_found(self):
        actions.uintarray.set_val("tag_uint_array", [10, 20, 30, 40])
        v = actions.uintarray.find("tag_uint_array", 67)
        self.assertIsNone(v)

    def test_array_clear(self):
        actions.uintarray.set_val("tag_uint_array", [10, 20, 30, 40])
        actions.uintarray.clear("tag_uint_array")
        self.assertEqual(actions.uintarray.is_empty("tag_uint_array"), True)
