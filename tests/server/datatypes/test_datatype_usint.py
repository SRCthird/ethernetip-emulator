# Copyright 2026 Merck KGaA, Darmstadt, Germany and/or its affiliates.
# All rights reserved

# test/server/datatypes/test_datatype_usint.py
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


class TestDatatypeUSintRegistry(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.server_control, cls.thread = _start_server(next_port())

    @classmethod
    def tearDownClass(cls) -> None:
        _stop_server(cls.server_control, cls.thread)

    def test_type_validator_above_max(self):
        with self.assertRaises(ValueError):
            tag_registry.register(
                lambda: [("tag_usint", actions.type.USINT(actions.usint.MAX + 1))]
            )

    def test_type_validator_below_min(self):
        with self.assertRaises(ValueError):
            tag_registry.register(
                lambda: [("tag_usint", actions.type.USINT(actions.usint.MIN - 1))]
            )

    def test_type_validator_non_numeric(self):
        with self.assertRaises((ValueError, TypeError)):
            tag_registry.register(
                lambda: [("tag_usint", actions.type.USINT("not_a_number"))]
            )

    def test_type_validator_at_max(self):
        tag_registry.register(
            lambda: [("tag_usint_max", actions.type.USINT(actions.usint.MAX))]
        )
        tag_registry.invalidate()
        tag_registry._raw.clear()

    def test_type_validator_at_min(self):
        tag_registry.register(
            lambda: [("tag_usint_min", actions.type.USINT(actions.usint.MIN))]
        )
        tag_registry.invalidate()
        tag_registry._raw.clear()

    def test_type_validator_coerces_float(self):
        tag_registry.register(lambda: [("tag_usint_float", actions.type.USINT(1.0))])
        tag_registry.invalidate()
        tag_registry._raw.clear()

    def test_array_type_validator_is_not_tuple(self):
        with self.assertRaises((ValueError, TypeError)):
            tag_registry.register(
                lambda: [("tag_usint_array", actions.type.USINTARRAY("not_a_tuple"))]
            )

    def test_array_type_validator_empty_tuple(self):
        with self.assertRaises((ValueError, TypeError)):
            tag_registry.register(
                lambda: [("tag_usint_array", actions.type.USINTARRAY([]))]
            )

    def test_array_type_validator_not_a_number(self):
        with self.assertRaises((ValueError, TypeError)):
            tag_registry.register(
                lambda: [
                    (
                        "tag_usint_array",
                        actions.type.USINTARRAY(
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
                        "tag_usint",
                        actions.type.USINTARRAY(
                            [
                                actions.usint.MAX + 1,
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
                        "tag_usint",
                        actions.type.USINTARRAY(
                            [
                                actions.usint.MIN - 1,
                            ]
                        ),
                    )
                ]
            )


class TestDatatypeUSintActions(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        tag_registry.register(
            lambda: [
                ("tag_usint", actions.type.USINT(0)),
                ("tag_usint_array", actions.type.USINTARRAY([0, 0, 0, 0])),
            ]
        )

        cls.server_control, cls.thread = _start_server(next_port())

    @classmethod
    def tearDownClass(cls) -> None:
        _stop_server(cls.server_control, cls.thread)

    def setUp(self) -> None:
        AttributeDevice._ensure_defaults()
        actions._lookup("tag_usint")[slice(0, 1)] = [0]  # type: ignore
        actions._lookup("tag_usint_array")[slice(0, 4)] = [0, 0, 0, 0]  # type: ignore

    def test_get_val(self):
        self.assertEqual(actions.usint.get_val("tag_usint"), 0)

    def test_get_val_is_array(self):
        v = actions.usint.get_val("tag_usint_array", slice(0, 4))
        self.assertIsInstance(v, list)

    def test_get_val_is_none(self):
        self.assertIsNone(actions.usint.get_val("no_tag"))

    def test_set_val(self):
        actions.usint.set_val("tag_usint", 42)
        self.assertEqual(actions.usint.get_val("tag_usint"), 42)

    def test_set_val_negative(self):
        with self.assertRaises(ValueError):
            actions.usint.set_val("tag_usint", -1)

    def test_set_val_max(self):
        actions.usint.set_val("tag_usint", actions.usint.MAX)
        self.assertEqual(actions.usint.get_val("tag_usint"), actions.usint.MAX)

    def test_set_val_min(self):
        actions.usint.set_val("tag_usint", actions.usint.MIN)
        self.assertEqual(actions.usint.get_val("tag_usint"), actions.usint.MIN)

    def test_set_val_is_none(self):
        self.assertIsNone(actions.usint.set_val("no_tag", 1))

    def test_on_change(self):
        changed = []

        @actions.usint.on_change("tag_usint")
        def _(attr, key, value):
            changed.append(value[0])

        actions.usint.set_val("tag_usint", 99)
        self.assertEqual(changed[-1], 99)

    def test_array_get_val(self):
        self.assertEqual(actions.usintarray.get_val("tag_usint_array"), [0, 0, 0, 0])

    def test_array_slice_get_val(self):
        self.assertEqual(
            actions.usintarray.get_val("tag_usint_array", slice(0, 1)), [0]
        )
        self.assertEqual(
            actions.usintarray.get_val("tag_usint_array", slice(0, 2)), [0, 0]
        )
        self.assertEqual(
            actions.usintarray.get_val("tag_usint_array", slice(0, 3)),
            [0, 0, 0],
        )
        self.assertEqual(
            actions.usintarray.get_val("tag_usint_array", slice(0, 4)),
            [0, 0, 0, 0],
        )

    def test_array_get_val_is_empty(self):
        v = actions.usintarray.get_val("no_tag")
        self.assertEqual(v, [])

    def test_array_set_val(self):
        v = [1, 2, 3, 4]
        actions.usintarray.set_val("tag_usint_array", v)
        self.assertEqual(actions.usintarray.get_val("tag_usint_array"), v)

    def test_array_set_val_slice(self):
        v = 99
        actions.usintarray.set_val("tag_usint_array", [v], slice(0, 1))
        actions.usintarray.set_val("tag_usint_array", [v], slice(1, 2))
        actions.usintarray.set_val("tag_usint_array", [v], slice(2, 3))
        actions.usintarray.set_val("tag_usint_array", [v], slice(3, 4))
        rv = actions.usintarray.get_val("tag_usint_array")
        for i, val in enumerate(rv):
            with self.subTest(number=i):
                self.assertEqual(val, v)

    def test_array_set_val_is_none(self):
        v = actions.usintarray.set_val("no_tag", [10])
        self.assertIsNone(v)

    def test_array_on_change(self):
        changed = []
        v = 99

        @actions.usintarray.on_change("tag_usint_array", key=slice(0, 1))
        def _(attr, key, value):
            changed.append(value[0])

        actions.usintarray.set_val("tag_usint_array", [v], slice(0, 1))
        self.assertEqual(changed[-1], v)

    def test_array_on_change_no_slice(self):
        changed = []
        v = [5, 10, 15, 20]

        @actions.usintarray.on_change("tag_usint_array")
        def _(attr, key, value):
            changed.append(value)

        actions.usintarray.set_val("tag_usint_array", v, slice(0, 4))
        self.assertEqual(changed[-1], v)

    def test_array_append(self):
        actions.usintarray.append("tag_usint_array", 10)
        self.assertEqual(actions.usintarray.get_val("tag_usint_array"), [10, 0, 0, 0])

    def test_array_append_is_full(self):
        actions.usintarray.set_val("tag_usint_array", [10, 20, 30, 40])
        v = actions.usintarray.append("tag_usint_array", 5)
        self.assertEqual(v, 0)

    def test_array_prepend(self):
        actions.usintarray.prepend("tag_usint_array", 67)
        self.assertEqual(actions.usintarray.get_val("tag_usint_array"), [0, 0, 0, 67])

    def test_array_prepend_is_full(self):
        actions.usintarray.set_val("tag_usint_array", [10, 20, 30, 40])
        v = actions.usintarray.prepend("tag_usint_array", 5)
        self.assertEqual(v, 0)

    def test_array_pop(self):
        actions.usintarray.set_val("tag_usint_array", [10, 20, 30, 40])
        v = actions.usintarray.pop("tag_usint_array")
        self.assertEqual(v, 40)
        self.assertEqual(actions.usintarray.get_val("tag_usint_array"), [10, 20, 30, 0])

    def test_array_pop_is_empty(self):
        v = actions.usintarray.pop("tag_usint_array")
        self.assertIsNone(v)

    def test_array_insert(self):
        actions.usintarray.insert("tag_usint_array", 2, 99)
        self.assertEqual(actions.usintarray.get_val("tag_usint_array"), [0, 0, 99, 0])

    def test_array_insert_is_full(self):
        actions.usintarray.set_val("tag_usint_array", [10, 20, 30, 40])
        v = actions.usintarray.insert("tag_usint_array", 2, 99)
        self.assertEqual(v, 0)

    def test_array_remove(self):
        actions.usintarray.set_val("tag_usint_array", [10, 20, 30, 40])
        v = actions.usintarray.remove("tag_usint_array", 2)
        self.assertEqual(v, 30)
        self.assertEqual(actions.usintarray.get_val("tag_usint_array"), [10, 20, 40, 0])

    def test_array_remove_is_empty(self):
        v = actions.usintarray.remove("tag_usint_array", 2)
        self.assertIsNone(v)

    def test_array_count(self):
        actions.usintarray.set_val("tag_usint_array", [10, 0, 30, 0])
        self.assertEqual(actions.usintarray.count("tag_usint_array"), 2)

    def test_array_is_full(self):
        actions.usintarray.set_val("tag_usint_array", [10, 20, 30, 40])
        self.assertEqual(actions.usintarray.is_full("tag_usint_array"), True)

    def test_array_is_not_full(self):
        self.assertEqual(actions.usintarray.is_full("tag_usint_array"), False)

    def test_array_is_empty(self):
        self.assertEqual(actions.usintarray.is_empty("tag_usint_array"), True)

    def test_array_is_not_empty(self):
        actions.usintarray.set_val("tag_usint_array", [10, 20, 30, 40])
        self.assertEqual(actions.usintarray.is_empty("tag_usint_array"), False)

    def test_array_find(self):
        actions.usintarray.set_val("tag_usint_array", [10, 20, 30, 40])
        v = actions.usintarray.find("tag_usint_array", 20)
        self.assertEqual(v, 1)

    def test_array_not_found(self):
        actions.usintarray.set_val("tag_usint_array", [10, 20, 30, 40])
        v = actions.usintarray.find("tag_usint_array", 67)
        self.assertIsNone(v)

    def test_array_clear(self):
        actions.usintarray.set_val("tag_usint_array", [10, 20, 30, 40])
        actions.usintarray.clear("tag_usint_array")
        self.assertEqual(actions.usintarray.is_empty("tag_usint_array"), True)
