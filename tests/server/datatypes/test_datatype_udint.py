# Copyright 2026 Merck KGaA, Darmstadt, Germany and/or its affiliates.
# All rights reserved

# test/server/datatypes/test_datatype_udint.py
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


class TestDatatypeUDintRegistry(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.server_control, cls.thread = _start_server(next_port())

    @classmethod
    def tearDownClass(cls) -> None:
        _stop_server(cls.server_control, cls.thread)

    def test_type_validator_above_max(self):
        with self.assertRaises(ValueError):
            tag_registry.register(
                lambda: [("tag_udint", actions.type.UDINT(actions.udint.MAX + 1))]
            )

    def test_type_validator_below_min(self):
        with self.assertRaises(ValueError):
            tag_registry.register(
                lambda: [("tag_udint", actions.type.UDINT(actions.udint.MIN - 1))]
            )

    def test_type_validator_non_numeric(self):
        with self.assertRaises((ValueError, TypeError)):
            tag_registry.register(
                lambda: [("tag_udint", actions.type.UDINT("not_a_number"))]
            )

    def test_type_validator_at_max(self):
        tag_registry.register(
            lambda: [("tag_udint_max", actions.type.UDINT(actions.udint.MAX))]
        )
        tag_registry.invalidate()
        tag_registry._raw.clear()

    def test_type_validator_at_min(self):
        tag_registry.register(
            lambda: [("tag_udint_min", actions.type.UDINT(actions.udint.MIN))]
        )
        tag_registry.invalidate()
        tag_registry._raw.clear()

    def test_type_validator_coerces_float(self):
        tag_registry.register(lambda: [("tag_udint_float", actions.type.UDINT(1.0))])
        tag_registry.invalidate()
        tag_registry._raw.clear()

    def test_array_type_validator_is_not_tuple(self):
        with self.assertRaises((ValueError, TypeError)):
            tag_registry.register(
                lambda: [("tag_udint_array", actions.type.UDINTARRAY("not_a_tuple"))]
            )

    def test_array_type_validator_empty_tuple(self):
        with self.assertRaises((ValueError, TypeError)):
            tag_registry.register(
                lambda: [("tag_udint_array", actions.type.UDINTARRAY([]))]
            )

    def test_array_type_validator_not_a_number(self):
        with self.assertRaises((ValueError, TypeError)):
            tag_registry.register(
                lambda: [
                    (
                        "tag_udint_array",
                        actions.type.UDINTARRAY(
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
                        "tag_udint",
                        actions.type.UDINTARRAY(
                            [
                                actions.udint.MAX + 1,
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
                        "tag_udint",
                        actions.type.UDINTARRAY(
                            [
                                actions.udint.MIN - 1,
                            ]
                        ),
                    )
                ]
            )


class TestDatatypeUDintActions(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        tag_registry.register(
            lambda: [
                ("tag_udint", actions.type.UDINT(0)),
                ("tag_udint_array", actions.type.UDINTARRAY([0, 0, 0, 0])),
            ]
        )

        cls.server_control, cls.thread = _start_server(next_port())

    @classmethod
    def tearDownClass(cls) -> None:
        _stop_server(cls.server_control, cls.thread)

    def setUp(self) -> None:
        AttributeDevice._ensure_defaults()
        actions._lookup("tag_udint")[slice(0, 1)] = [0]  # type: ignore
        actions._lookup("tag_udint_array")[slice(0, 4)] = [0, 0, 0, 0]  # type: ignore

    def test_get_val(self):
        self.assertEqual(actions.udint.get_val("tag_udint"), 0)

    def test_get_val_is_array(self):
        v = actions.udint.get_val("tag_udint_array", slice(0, 4))
        self.assertIsInstance(v, list)

    def test_get_val_is_none(self):
        self.assertIsNone(actions.udint.get_val("no_tag"))

    def test_set_val(self):
        actions.udint.set_val("tag_udint", 42)
        self.assertEqual(actions.udint.get_val("tag_udint"), 42)

    def test_set_val_negative(self):
        with self.assertRaises(ValueError):
            actions.udint.set_val("tag_udint", -1)

    def test_set_val_max(self):
        actions.udint.set_val("tag_udint", actions.udint.MAX)
        self.assertEqual(actions.udint.get_val("tag_udint"), actions.udint.MAX)

    def test_set_val_min(self):
        actions.udint.set_val("tag_udint", actions.udint.MIN)
        self.assertEqual(actions.udint.get_val("tag_udint"), actions.udint.MIN)

    def test_set_val_is_none(self):
        self.assertIsNone(actions.udint.set_val("no_tag", 1))

    def test_on_change(self):
        changed = []

        @actions.udint.on_change("tag_udint")
        def _(attr, key, value):
            changed.append(value[0])

        actions.udint.set_val("tag_udint", 99)
        self.assertEqual(changed[-1], 99)

    def test_array_get_val(self):
        self.assertEqual(actions.udintarray.get_val("tag_udint_array"), [0, 0, 0, 0])

    def test_array_slice_get_val(self):
        self.assertEqual(
            actions.udintarray.get_val("tag_udint_array", slice(0, 1)), [0]
        )
        self.assertEqual(
            actions.udintarray.get_val("tag_udint_array", slice(0, 2)), [0, 0]
        )
        self.assertEqual(
            actions.udintarray.get_val("tag_udint_array", slice(0, 3)),
            [0, 0, 0],
        )
        self.assertEqual(
            actions.udintarray.get_val("tag_udint_array", slice(0, 4)),
            [0, 0, 0, 0],
        )

    def test_array_get_val_is_empty(self):
        v = actions.udintarray.get_val("no_tag")
        self.assertEqual(v, [])

    def test_array_set_val(self):
        v = [1, 2, 3, 4]
        actions.udintarray.set_val("tag_udint_array", v)
        self.assertEqual(actions.udintarray.get_val("tag_udint_array"), v)

    def test_array_set_val_slice(self):
        v = 99
        actions.udintarray.set_val("tag_udint_array", [v], slice(0, 1))
        actions.udintarray.set_val("tag_udint_array", [v], slice(1, 2))
        actions.udintarray.set_val("tag_udint_array", [v], slice(2, 3))
        actions.udintarray.set_val("tag_udint_array", [v], slice(3, 4))
        rv = actions.udintarray.get_val("tag_udint_array")
        for i, val in enumerate(rv):
            with self.subTest(number=i):
                self.assertEqual(val, v)

    def test_array_set_val_is_none(self):
        v = actions.udintarray.set_val("no_tag", [10])
        self.assertIsNone(v)

    def test_array_on_change(self):
        changed = []
        v = 99

        @actions.udintarray.on_change("tag_udint_array", key=slice(0, 1))
        def _(attr, key, value):
            changed.append(value[0])

        actions.udintarray.set_val("tag_udint_array", [v], slice(0, 1))
        self.assertEqual(changed[-1], v)

    def test_array_on_change_no_slice(self):
        changed = []
        v = [5, 10, 15, 20]

        @actions.udintarray.on_change("tag_udint_array")
        def _(attr, key, value):
            changed.append(value)

        actions.udintarray.set_val("tag_udint_array", v, slice(0, 4))
        self.assertEqual(changed[-1], v)

    def test_array_append(self):
        actions.udintarray.append("tag_udint_array", 10)
        self.assertEqual(actions.udintarray.get_val("tag_udint_array"), [10, 0, 0, 0])

    def test_array_append_is_full(self):
        actions.udintarray.set_val("tag_udint_array", [10, 20, 30, 40])
        v = actions.udintarray.append("tag_udint_array", 5)
        self.assertEqual(v, 0)

    def test_array_prepend(self):
        actions.udintarray.prepend("tag_udint_array", 67)
        self.assertEqual(actions.udintarray.get_val("tag_udint_array"), [0, 0, 0, 67])

    def test_array_prepend_is_full(self):
        actions.udintarray.set_val("tag_udint_array", [10, 20, 30, 40])
        v = actions.udintarray.prepend("tag_udint_array", 5)
        self.assertEqual(v, 0)

    def test_array_pop(self):
        actions.udintarray.set_val("tag_udint_array", [10, 20, 30, 40])
        v = actions.udintarray.pop("tag_udint_array")
        self.assertEqual(v, 40)
        self.assertEqual(actions.udintarray.get_val("tag_udint_array"), [10, 20, 30, 0])

    def test_array_pop_is_empty(self):
        v = actions.udintarray.pop("tag_udint_array")
        self.assertIsNone(v)

    def test_array_insert(self):
        actions.udintarray.insert("tag_udint_array", 2, 99)
        self.assertEqual(actions.udintarray.get_val("tag_udint_array"), [0, 0, 99, 0])

    def test_array_insert_is_full(self):
        actions.udintarray.set_val("tag_udint_array", [10, 20, 30, 40])
        v = actions.udintarray.insert("tag_udint_array", 2, 99)
        self.assertEqual(v, 0)

    def test_array_remove(self):
        actions.udintarray.set_val("tag_udint_array", [10, 20, 30, 40])
        v = actions.udintarray.remove("tag_udint_array", 2)
        self.assertEqual(v, 30)
        self.assertEqual(actions.udintarray.get_val("tag_udint_array"), [10, 20, 40, 0])

    def test_array_remove_is_empty(self):
        v = actions.udintarray.remove("tag_udint_array", 2)
        self.assertIsNone(v)

    def test_array_count(self):
        actions.udintarray.set_val("tag_udint_array", [10, 0, 30, 0])
        self.assertEqual(actions.udintarray.count("tag_udint_array"), 2)

    def test_array_is_full(self):
        actions.udintarray.set_val("tag_udint_array", [10, 20, 30, 40])
        self.assertEqual(actions.udintarray.is_full("tag_udint_array"), True)

    def test_array_is_not_full(self):
        self.assertEqual(actions.udintarray.is_full("tag_udint_array"), False)

    def test_array_is_empty(self):
        self.assertEqual(actions.udintarray.is_empty("tag_udint_array"), True)

    def test_array_is_not_empty(self):
        actions.udintarray.set_val("tag_udint_array", [10, 20, 30, 40])
        self.assertEqual(actions.udintarray.is_empty("tag_udint_array"), False)

    def test_array_find(self):
        actions.udintarray.set_val("tag_udint_array", [10, 20, 30, 40])
        v = actions.udintarray.find("tag_udint_array", 20)
        self.assertEqual(v, 1)

    def test_array_not_found(self):
        actions.udintarray.set_val("tag_udint_array", [10, 20, 30, 40])
        v = actions.udintarray.find("tag_udint_array", 67)
        self.assertIsNone(v)

    def test_array_clear(self):
        actions.udintarray.set_val("tag_udint_array", [10, 20, 30, 40])
        actions.udintarray.clear("tag_udint_array")
        self.assertEqual(actions.udintarray.is_empty("tag_udint_array"), True)
