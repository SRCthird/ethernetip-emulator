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

    def test_type_validator_invalid_bool(self):
        with self.subTest(number=1):
            with self.assertRaises(ValueError):
                tag_registry.register(lambda: [("tag_bool", actions.type.BOOL(42))])
        with self.subTest(number=2):
            with self.assertRaises(ValueError):
                tag_registry.register(
                    lambda: [("tag_bool_array", actions.type.BOOLARRAY([42, 42]))]
                )

    def test_type_validator_invalid_non_list(self):
        with self.assertRaises(ValueError):
            tag_registry.register(
                lambda: [("tag_bool_array", actions.type.BOOLARRAY(True))]
            )

    def test_type_validator_invalid_empty_tuple(self):
        with self.assertRaises(ValueError):
            tag_registry.register(
                lambda: [("tag_bool_array", actions.type.BOOLARRAY([]))]
            )


class TestDatatypeBoolActions(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        @tag_registry.register
        def _():
            return [
                ("tag_bool", actions.type.BOOL(True)),
                ("tag_bool_array", actions.type.BOOLARRAY([True, True, True, True])),
            ]

        cls.server_control, cls.thread = _start_server(next_port())

    @classmethod
    def tearDownClass(cls) -> None:
        _stop_server(cls.server_control, cls.thread)

    def setUp(self) -> None:
        AttributeDevice._ensure_defaults()
        actions.bool.set_val("tag_bool", False)
        actions.boolarray.set_val("tag_bool_array", [False, False, False, False])

    def test_get_val(self):
        self.assertEqual(actions.bool.get_val("tag_bool"), False)

    def test_get_val_is_array(self):
        v = actions.bool.get_val("tag_bool_array", slice(0, 4))
        self.assertIsInstance(v, list)

    def test_get_val_is_none(self):
        v = actions.bool.get_val("no_tag")
        self.assertIsNone(v)

    def test_set_val(self):
        actions.bool.set_val("tag_bool", True)
        self.assertEqual(actions.bool.get_val("tag_bool"), True)

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

    def test_array_get_val(self):
        self.assertEqual(
            actions.boolarray.get_val("tag_bool_array"), [False, False, False, False]
        )

    def test_array_slice_get_val(self):
        self.assertEqual(
            actions.boolarray.get_val("tag_bool_array", slice(0, 1)), [False]
        )
        self.assertEqual(
            actions.boolarray.get_val("tag_bool_array", slice(0, 2)), [False, False]
        )
        self.assertEqual(
            actions.boolarray.get_val("tag_bool_array", slice(0, 3)),
            [False, False, False],
        )
        self.assertEqual(
            actions.boolarray.get_val("tag_bool_array", slice(0, 4)),
            [False, False, False, False],
        )

    def test_array_get_val_is_empty(self):
        v = actions.boolarray.get_val("no_tag")
        self.assertEqual(v, [])

    def test_array_set_val(self):
        v = [True, False, True, False]
        actions.boolarray.set_val("tag_bool_array", v)
        self.assertEqual(actions.boolarray.get_val("tag_bool_array"), v)

    def test_array_set_val_slice(self):
        v = True
        actions.boolarray.set_val("tag_bool_array", [v], slice(0, 1))
        actions.boolarray.set_val("tag_bool_array", [v], slice(1, 2))
        actions.boolarray.set_val("tag_bool_array", [v], slice(2, 3))
        actions.boolarray.set_val("tag_bool_array", [v], slice(3, 4))
        rv = actions.boolarray.get_val("tag_bool_array")
        for i, val in enumerate(rv):
            with self.subTest(number=i):
                self.assertEqual(val, v)

    def test_array_set_val_is_none(self):
        v = actions.boolarray.set_val("no_tag", [True])
        self.assertIsNone(v)

    def test_array_on_change(self):
        changed = []
        v = True

        @actions.boolarray.on_change("tag_bool_array", key=slice(0, 1))
        def _(attr, key, value):
            changed.append(value[0])

        actions.boolarray.set_val("tag_bool_array", [v], slice(0, 1))
        self.assertEqual(changed[-1], v)

    def test_array_on_change_no_slice(self):
        changed = []
        v = [True, False, True, False]

        @actions.boolarray.on_change("tag_bool_array")
        def _(attr, key, value):
            changed.append(value)

        actions.boolarray.set_val("tag_bool_array", v, slice(0, 4))
        self.assertEqual(changed[-1], v)

    def test_array_get_bit(self):
        self.assertEqual(actions.boolarray.get_bit("tag_bool_array", 0), False)

    def test_array_get_bit_is_none(self):
        self.assertIsNone(actions.boolarray.get_bit("non_bool_array", 0))

    def test_array_set_bit(self):
        self.assertEqual(actions.boolarray.get_bit("tag_bool_array", 0), False)

    def test_array_toggle_bit(self):
        v = actions.boolarray.toggle_bit("tag_bool_array", 0)
        self.assertEqual(v, True)

    def test_array_toggle_bit_is_none(self):
        v = actions.boolarray.toggle_bit("non_bool_array", 0)
        self.assertIsNone(v)

    def test_array_append(self):
        actions.boolarray.append("tag_bool_array", True)
        self.assertEqual(
            actions.boolarray.get_val("tag_bool_array"), [True, False, False, False]
        )

    def test_array_append_is_full(self):
        actions.boolarray.set_val("tag_bool_array", [True, True, True, True])
        v = actions.boolarray.append("tag_bool_array", True)
        self.assertEqual(v, False)

    def test_array_prepend(self):
        actions.boolarray.prepend("tag_bool_array", True)
        self.assertEqual(
            actions.boolarray.get_val("tag_bool_array"), [False, False, False, True]
        )

    def test_array_prepend_is_full(self):
        actions.boolarray.set_val("tag_bool_array", [True, True, True, True])
        v = actions.boolarray.prepend("tag_bool_array", True)
        self.assertEqual(v, False)

    def test_array_pop(self):
        actions.boolarray.set_val("tag_bool_array", [True, True, True, True])
        v = actions.boolarray.pop("tag_bool_array")
        self.assertTrue(v)
        self.assertEqual(
            actions.boolarray.get_val("tag_bool_array"), [True, True, True, False]
        )

    def test_array_pop_is_empty(self):
        v = actions.boolarray.pop("tag_bool_array")
        self.assertIsNone(v)

    def test_array_insert(self):
        actions.boolarray.insert("tag_bool_array", 2, True)
        self.assertEqual(
            actions.boolarray.get_val("tag_bool_array"), [False, False, True, False]
        )

    def test_array_insert_is_full(self):
        actions.boolarray.set_val("tag_bool_array", [True, True, True, True])
        v = actions.boolarray.insert("tag_bool_array", 2, True)
        self.assertEqual(v, False)

    def test_array_remove(self):
        actions.boolarray.set_val("tag_bool_array", [True, True, True, True])
        actions.boolarray.remove("tag_bool_array", 2)
        self.assertEqual(
            actions.boolarray.get_val("tag_bool_array"), [True, True, True, False]
        )

    def test_array_remove_is_empty(self):
        v = actions.boolarray.remove("tag_bool_array", 2)
        self.assertIsNone(v)

    def test_array_count(self):
        actions.boolarray.set_val("tag_bool_array", [False, True, False, True])
        self.assertEqual(actions.boolarray.count("tag_bool_array"), 2)

    def test_array_count_clear(self):
        actions.boolarray.set_val("tag_bool_array", [False, False, False, True])
        self.assertEqual(actions.boolarray.count_clear("tag_bool_array"), 3)

    def test_array_has_any(self):
        actions.boolarray.set_val("tag_bool_array", [False, False, False, True])
        self.assertEqual(actions.boolarray.has_any("tag_bool_array"), True)

    def test_array_doeasnt_have_any(self):
        self.assertEqual(actions.boolarray.has_any("tag_bool_array"), False)

    def test_array_is_full(self):
        actions.boolarray.set_val("tag_bool_array", [True, True, True, True])
        self.assertEqual(actions.boolarray.is_full("tag_bool_array"), True)

    def test_array_is_not_full(self):
        self.assertEqual(actions.boolarray.is_full("tag_bool_array"), False)

    def test_array_is_empty(self):
        self.assertEqual(actions.boolarray.is_empty("tag_bool_array"), True)

    def test_array_is_not_empty(self):
        actions.boolarray.set_val("tag_bool_array", [True, True, True, True])
        self.assertEqual(actions.boolarray.is_empty("tag_bool_array"), False)

    def test_array_clear(self):
        actions.boolarray.set_val("tag_bool_array", [True, False, True, False])
        actions.boolarray.clear("tag_bool_array")
        self.assertEqual(actions.boolarray.is_empty("tag_bool_array"), True)

    def test_array_invert(self):
        actions.boolarray.set_val("tag_bool_array", [True, False, True, False])
        actions.boolarray.invert("tag_bool_array")
        self.assertEqual(
            actions.boolarray.get_val("tag_bool_array"), [False, True, False, True]
        )
