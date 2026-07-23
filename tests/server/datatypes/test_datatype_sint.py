# Copyright 2026 Merck KGaA, Darmstadt, Germany and/or its affiliates.
# All rights reserved

# test/server/datatypes/test_datatype_sint.py
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


class TestDatatypeSintRegistry(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.server_control, cls.thread = _start_server(next_port())

    @classmethod
    def tearDownClass(cls) -> None:
        _stop_server(cls.server_control, cls.thread)

    def test_type_validator_above_max(self):
        with self.assertRaises(ValueError):
            tag_registry.register(
                lambda: [("tag_sint", actions.type.SINT(actions.sint.MAX + 1))]
            )

    def test_type_validator_below_min(self):
        with self.assertRaises(ValueError):
            tag_registry.register(
                lambda: [("tag_sint", actions.type.SINT(actions.sint.MIN - 1))]
            )

    def test_type_validator_non_numeric(self):
        with self.assertRaises((ValueError, TypeError)):
            tag_registry.register(
                lambda: [("tag_sint", actions.type.SINT("not_a_number"))]
            )

    def test_type_validator_at_max(self):
        tag_registry.register(
            lambda: [("tag_sint_max", actions.type.SINT(actions.sint.MAX))]
        )
        tag_registry.invalidate()
        tag_registry._raw.clear()

    def test_type_validator_at_min(self):
        tag_registry.register(
            lambda: [("tag_sint_min", actions.type.SINT(actions.sint.MIN))]
        )
        tag_registry.invalidate()
        tag_registry._raw.clear()

    def test_type_validator_coerces_float(self):
        tag_registry.register(lambda: [("tag_sint_float", actions.type.SINT(1.0))])
        tag_registry.invalidate()
        tag_registry._raw.clear()

    def test_array_type_validator_is_not_tuple(self):
        with self.assertRaises((ValueError, TypeError)):
            tag_registry.register(
                lambda: [("tag_sint_array", actions.type.SINTARRAY("not_a_tuple"))]
            )

    def test_array_type_validator_empty_tuple(self):
        with self.assertRaises((ValueError, TypeError)):
            tag_registry.register(
                lambda: [("tag_sint_array", actions.type.SINTARRAY([]))]
            )

    def test_array_type_validator_not_a_number(self):
        with self.assertRaises((ValueError, TypeError)):
            tag_registry.register(
                lambda: [
                    (
                        "tag_sint_array",
                        actions.type.SINTARRAY(
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
                        "tag_sint",
                        actions.type.SINTARRAY(
                            [
                                actions.sint.MAX + 1,
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
                        "tag_sint",
                        actions.type.SINTARRAY(
                            [
                                actions.sint.MIN - 1,
                            ]
                        ),
                    )
                ]
            )


class TestDatatypeSintActions(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        tag_registry.register(
            lambda: [
                ("tag_sint", actions.type.SINT(0)),
                ("tag_sint_array", actions.type.SINTARRAY([0, 0, 0, 0])),
            ]
        )

        cls.server_control, cls.thread = _start_server(next_port())

    @classmethod
    def tearDownClass(cls) -> None:
        _stop_server(cls.server_control, cls.thread)

    def setUp(self) -> None:
        AttributeDevice._ensure_defaults()
        actions._lookup("tag_sint")[slice(0, 1)] = [0]  # type: ignore
        actions._lookup("tag_sint_array")[slice(0, 4)] = [0, 0, 0, 0]  # type: ignore

    def test_get_val(self):
        self.assertEqual(actions.sint.get_val("tag_sint"), 0)

    def test_get_val_is_array(self):
        v = actions.sint.get_val("tag_sint_array", slice(0, 4))
        self.assertIsInstance(v, list)

    def test_get_val_is_none(self):
        self.assertIsNone(actions.sint.get_val("no_tag"))

    def test_set_val(self):
        actions.sint.set_val("tag_sint", 42)
        self.assertEqual(actions.sint.get_val("tag_sint"), 42)

    def test_set_val_negative(self):
        actions.sint.set_val("tag_sint", -1)
        self.assertEqual(actions.sint.get_val("tag_sint"), -1)

    def test_set_val_max(self):
        actions.sint.set_val("tag_sint", actions.sint.MAX)
        self.assertEqual(actions.sint.get_val("tag_sint"), actions.sint.MAX)

    def test_set_val_min(self):
        actions.sint.set_val("tag_sint", actions.sint.MIN)
        self.assertEqual(actions.sint.get_val("tag_sint"), actions.sint.MIN)

    def test_set_val_is_none(self):
        self.assertIsNone(actions.sint.set_val("no_tag", 1))

    def test_on_change(self):
        changed = []

        @actions.sint.on_change("tag_sint")
        def _(attr, key, value):
            changed.append(value[0])

        actions.sint.set_val("tag_sint", 99)
        self.assertEqual(changed[-1], 99)

    def test_on_change_negative(self):
        changed = []

        @actions.sint.on_change("tag_sint")
        def _(attr, key, value):
            changed.append(value[0])

        actions.sint.set_val("tag_sint", -50)
        self.assertEqual(changed[-1], -50)

    def test_array_get_val(self):
        self.assertEqual(actions.sintarray.get_val("tag_sint_array"), [0, 0, 0, 0])

    def test_array_slice_get_val(self):
        self.assertEqual(actions.sintarray.get_val("tag_sint_array", slice(0, 1)), [0])
        self.assertEqual(
            actions.sintarray.get_val("tag_sint_array", slice(0, 2)), [0, 0]
        )
        self.assertEqual(
            actions.sintarray.get_val("tag_sint_array", slice(0, 3)),
            [0, 0, 0],
        )
        self.assertEqual(
            actions.sintarray.get_val("tag_sint_array", slice(0, 4)),
            [0, 0, 0, 0],
        )

    def test_array_get_val_is_empty(self):
        v = actions.sintarray.get_val("no_tag")
        self.assertEqual(v, [])

    def test_array_set_val(self):
        v = [1, 2, 3, 4]
        actions.sintarray.set_val("tag_sint_array", v)
        self.assertEqual(actions.sintarray.get_val("tag_sint_array"), v)

    def test_array_set_val_slice(self):
        v = 99
        actions.sintarray.set_val("tag_sint_array", [v], slice(0, 1))
        actions.sintarray.set_val("tag_sint_array", [v], slice(1, 2))
        actions.sintarray.set_val("tag_sint_array", [v], slice(2, 3))
        actions.sintarray.set_val("tag_sint_array", [v], slice(3, 4))
        rv = actions.sintarray.get_val("tag_sint_array")
        for i, val in enumerate(rv):
            with self.subTest(number=i):
                self.assertEqual(val, v)

    def test_array_set_val_is_none(self):
        v = actions.sintarray.set_val("no_tag", [10])
        self.assertIsNone(v)

    def test_array_on_change(self):
        changed = []
        v = 99

        @actions.sintarray.on_change("tag_sint_array", key=slice(0, 1))
        def _(attr, key, value):
            changed.append(value[0])

        actions.sintarray.set_val("tag_sint_array", [v], slice(0, 1))
        self.assertEqual(changed[-1], v)

    def test_array_on_change_no_slice(self):
        changed = []
        v = [5, 10, 15, 20]

        @actions.sintarray.on_change("tag_sint_array")
        def _(attr, key, value):
            changed.append(value)

        actions.sintarray.set_val("tag_sint_array", v, slice(0, 4))
        self.assertEqual(changed[-1], v)

    def test_array_append(self):
        actions.sintarray.append("tag_sint_array", 10)
        self.assertEqual(actions.sintarray.get_val("tag_sint_array"), [10, 0, 0, 0])

    def test_array_append_is_full(self):
        actions.sintarray.set_val("tag_sint_array", [10, 20, 30, 40])
        v = actions.sintarray.append("tag_sint_array", 5)
        self.assertEqual(v, 0)

    def test_array_prepend(self):
        actions.sintarray.prepend("tag_sint_array", 67)
        self.assertEqual(actions.sintarray.get_val("tag_sint_array"), [0, 0, 0, 67])

    def test_array_prepend_is_full(self):
        actions.sintarray.set_val("tag_sint_array", [10, 20, 30, 40])
        v = actions.sintarray.prepend("tag_sint_array", 5)
        self.assertEqual(v, 0)

    def test_array_pop(self):
        actions.sintarray.set_val("tag_sint_array", [10, 20, 30, 40])
        v = actions.sintarray.pop("tag_sint_array")
        self.assertEqual(v, 40)
        self.assertEqual(actions.sintarray.get_val("tag_sint_array"), [10, 20, 30, 0])

    def test_array_pop_is_empty(self):
        v = actions.sintarray.pop("tag_sint_array")
        self.assertIsNone(v)

    def test_array_insert(self):
        actions.sintarray.insert("tag_sint_array", 2, 99)
        self.assertEqual(actions.sintarray.get_val("tag_sint_array"), [0, 0, 99, 0])

    def test_array_insert_is_full(self):
        actions.sintarray.set_val("tag_sint_array", [10, 20, 30, 40])
        v = actions.sintarray.insert("tag_sint_array", 2, 99)
        self.assertEqual(v, 0)

    def test_array_remove(self):
        actions.sintarray.set_val("tag_sint_array", [10, 20, 30, 40])
        v = actions.sintarray.remove("tag_sint_array", 2)
        self.assertEqual(v, 30)
        self.assertEqual(actions.sintarray.get_val("tag_sint_array"), [10, 20, 40, 0])

    def test_array_remove_is_empty(self):
        v = actions.sintarray.remove("tag_sint_array", 2)
        self.assertIsNone(v)

    def test_array_count(self):
        actions.sintarray.set_val("tag_sint_array", [10, 0, 30, 0])
        self.assertEqual(actions.sintarray.count("tag_sint_array"), 2)

    def test_array_is_full(self):
        actions.sintarray.set_val("tag_sint_array", [10, 20, 30, 40])
        self.assertEqual(actions.sintarray.is_full("tag_sint_array"), True)

    def test_array_is_not_full(self):
        self.assertEqual(actions.sintarray.is_full("tag_sint_array"), False)

    def test_array_is_empty(self):
        self.assertEqual(actions.sintarray.is_empty("tag_sint_array"), True)

    def test_array_is_not_empty(self):
        actions.sintarray.set_val("tag_sint_array", [10, 20, 30, 40])
        self.assertEqual(actions.sintarray.is_empty("tag_sint_array"), False)

    def test_array_find(self):
        actions.sintarray.set_val("tag_sint_array", [10, 20, 30, 40])
        v = actions.sintarray.find("tag_sint_array", 20)
        self.assertEqual(v, 1)

    def test_array_not_found(self):
        actions.sintarray.set_val("tag_sint_array", [10, 20, 30, 40])
        v = actions.sintarray.find("tag_sint_array", 67)
        self.assertIsNone(v)

    def test_array_clear(self):
        actions.sintarray.set_val("tag_sint_array", [10, 20, 30, 40])
        actions.sintarray.clear("tag_sint_array")
        self.assertEqual(actions.sintarray.is_empty("tag_sint_array"), True)
