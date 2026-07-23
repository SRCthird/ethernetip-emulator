# Copyright 2026 Merck KGaA, Darmstadt, Germany and/or its affiliates.
# All rights reserved

# test/server/datatypes/test_datatype_sstring.py
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


class TestDatatypeSStringRegistry(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.server_control, cls.thread = _start_server(next_port())

    @classmethod
    def tearDownClass(cls) -> None:
        _stop_server(cls.server_control, cls.thread)

    def test_type_validator_invalid_sstring(self):
        with self.subTest(number=1):
            with self.assertRaises(ValueError):
                tag_registry.register(
                    lambda: [("tag_sstring", actions.type.SSTRING(42))]
                )
        with self.subTest(number=2):
            with self.assertRaises(ValueError):
                tag_registry.register(
                    lambda: [("tag_sstring_array", actions.type.SSTRINGARRAY([42, 42]))]
                )

    def test_type_validator_invalid_non_list(self):
        with self.assertRaises(ValueError):
            tag_registry.register(
                lambda: [("tag_sstring_array", actions.type.SSTRINGARRAY("VALUE?"))]
            )

    def test_type_validator_invalid_empty_tuple(self):
        with self.assertRaises(ValueError):
            tag_registry.register(
                lambda: [("tag_sstring_array", actions.type.SSTRINGARRAY([]))]
            )


class TestDatatypeSStringActions(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        @tag_registry.register
        def _():
            return [
                ("tag_sstring", actions.type.SSTRING("")),
                (
                    "tag_sstring_array",
                    actions.type.SSTRINGARRAY(["", "", "", ""]),
                ),
            ]

        cls.server_control, cls.thread = _start_server(next_port())

    @classmethod
    def tearDownClass(cls) -> None:
        _stop_server(cls.server_control, cls.thread)

    def setUp(self) -> None:
        AttributeDevice._ensure_defaults()
        actions._lookup("tag_sstring")[slice(0, 1)] = [""]  # type: ignore
        actions._lookup("tag_sstring_array")[slice(0, 4)] = ["", "", "", ""]  # type: ignore

    def test_get_val(self):
        self.assertEqual(actions.sstring.get_val("tag_sstring"), "")

    def test_get_val_is_array(self):
        v = actions.sstring.get_val("tag_sstring_array", slice(0, 4))
        self.assertIsInstance(v, list)

    def test_get_val_is_none(self):
        v = actions.sstring.get_val("no_tag")
        self.assertIsNone(v)

    def test_set_val(self):
        actions.sstring.set_val("tag_sstring", "VALUE!")
        self.assertEqual(actions.sstring.get_val("tag_sstring"), "VALUE!")

    def test_set_val_is_none(self):
        v = actions.sstring.set_val("no_tag", "VALUE!")
        self.assertIsNone(v)

    def test_on_change(self):
        changed = []

        @actions.sstring.on_change("tag_sstring")
        def _(attr, key, value):
            changed.append(value[0])

        actions.sstring.set_val("tag_sstring", "VALUE!")
        self.assertEqual(changed[-1], "VALUE!")

    def test_array_get_val(self):
        self.assertEqual(
            actions.sstringarray.get_val("tag_sstring_array"),
            ["", "", "", ""],
        )

    def test_array_slice_get_val(self):
        self.assertEqual(
            actions.sstringarray.get_val("tag_sstring_array", slice(0, 1)), [""]
        )
        self.assertEqual(
            actions.sstringarray.get_val("tag_sstring_array", slice(0, 2)),
            ["", ""],
        )
        self.assertEqual(
            actions.sstringarray.get_val("tag_sstring_array", slice(0, 3)),
            ["", "", ""],
        )
        self.assertEqual(
            actions.sstringarray.get_val("tag_sstring_array", slice(0, 4)),
            ["", "", "", ""],
        )

    def test_array_get_val_is_empty(self):
        v = actions.sstringarray.get_val("no_tag")
        self.assertEqual(v, [])

    def test_array_set_val(self):
        v = ["VALUE1", "", "VALUE2", ""]
        actions.sstringarray.set_val("tag_sstring_array", v)
        self.assertEqual(actions.sstringarray.get_val("tag_sstring_array"), v)

    def test_array_set_val_slice(self):
        v = "VALUE!"
        actions.sstringarray.set_val("tag_sstring_array", [v], slice(0, 1))
        actions.sstringarray.set_val("tag_sstring_array", [v], slice(1, 2))
        actions.sstringarray.set_val("tag_sstring_array", [v], slice(2, 3))
        actions.sstringarray.set_val("tag_sstring_array", [v], slice(3, 4))
        rv = actions.sstringarray.get_val("tag_sstring_array")
        for i, val in enumerate(rv):
            with self.subTest(number=i):
                self.assertEqual(val, v)

    def test_array_set_val_is_none(self):
        v = actions.sstringarray.set_val("no_tag", ["VALUE!"])
        self.assertIsNone(v)

    def test_array_on_change(self):
        changed = []
        v = "VALUE!"

        @actions.sstringarray.on_change("tag_sstring_array", key=slice(0, 1))
        def _(attr, key, value):
            changed.append(value[0])

        actions.sstringarray.set_val("tag_sstring_array", [v], slice(0, 1))
        self.assertEqual(changed[-1], v)

    def test_array_on_change_no_slice(self):
        changed = []
        v = ["VALUE1", "", "VALUE2", ""]

        @actions.sstringarray.on_change("tag_sstring_array")
        def _(attr, key, value):
            changed.append(value)

        actions.sstringarray.set_val("tag_sstring_array", v, slice(0, 4))
        self.assertEqual(changed[-1], v)

    def test_array_append(self):
        actions.sstringarray.append("tag_sstring_array", "VALUE1")
        self.assertEqual(
            actions.sstringarray.get_val("tag_sstring_array"),
            ["VALUE1", "", "", ""],
        )

    def test_array_append_is_full(self):
        actions.sstringarray.set_val(
            "tag_sstring_array", ["VALUE1", "VALUE2", "VALUE3", "VALUE4"]
        )
        v = actions.sstringarray.append("tag_sstring_array", "VALUE5")
        self.assertFalse(v)

    def test_array_prepend(self):
        actions.sstringarray.prepend("tag_sstring_array", "VALUE4")
        self.assertEqual(
            actions.sstringarray.get_val("tag_sstring_array"),
            ["", "", "", "VALUE4"],
        )

    def test_array_prepend_is_full(self):
        actions.sstringarray.set_val(
            "tag_sstring_array", ["VALUE1", "VALUE2", "VALUE3", "VALUE4"]
        )
        v = actions.sstringarray.prepend("tag_sstring_array", "VALUE5")
        self.assertFalse(v)

    def test_array_pop(self):
        actions.sstringarray.set_val(
            "tag_sstring_array", ["VALUE1", "VALUE2", "VALUE3", "VALUE4"]
        )
        v = actions.sstringarray.pop("tag_sstring_array")
        self.assertEqual(v, "VALUE4")
        self.assertEqual(
            actions.sstringarray.get_val("tag_sstring_array"),
            ["VALUE1", "VALUE2", "VALUE3", ""],
        )

    def test_array_pop_is_empty(self):
        v = actions.sstringarray.pop("tag_sstring_array")
        self.assertIsNone(v)

    def test_array_insert(self):
        actions.sstringarray.insert("tag_sstring_array", 2, "VALUE3")
        self.assertEqual(
            actions.sstringarray.get_val("tag_sstring_array"),
            ["", "", "VALUE3", ""],
        )

    def test_array_insert_is_full(self):
        actions.sstringarray.set_val(
            "tag_sstring_array", ["VALUE1", "VALUE2", "VALUE3", "VALUE4"]
        )
        v = actions.sstringarray.insert("tag_sstring_array", 2, "VALUE2.5")
        self.assertFalse(v)

    def test_array_remove(self):
        actions.sstringarray.set_val(
            "tag_sstring_array", ["VALUE1", "VALUE2", "VALUE3", "VALUE4"]
        )
        actions.sstringarray.remove("tag_sstring_array", 2)
        self.assertEqual(
            actions.sstringarray.get_val("tag_sstring_array"),
            ["VALUE1", "VALUE2", "VALUE4", ""],
        )

    def test_array_remove_is_empty(self):
        v = actions.sstringarray.remove("tag_sstring_array", 2)
        self.assertIsNone(v)

    def test_array_count(self):
        actions.sstringarray.set_val("tag_sstring_array", ["", "VALUE2", "", "VALUE4"])
        self.assertEqual(actions.sstringarray.count("tag_sstring_array"), 2)

    def test_array_is_full(self):
        actions.sstringarray.set_val(
            "tag_sstring_array", ["VALUE1", "VALUE2", "VALUE3", "VALUE4"]
        )
        self.assertTrue(actions.sstringarray.is_full("tag_sstring_array"))

    def test_array_is_not_full(self):
        self.assertFalse(actions.sstringarray.is_full("tag_sstring_array"))

    def test_array_is_empty(self):
        self.assertTrue(actions.sstringarray.is_empty("tag_sstring_array"))

    def test_array_is_not_empty(self):
        actions.sstringarray.set_val(
            "tag_sstring_array", ["VALUE1", "VALUE2", "VALUE3", "VALUE4"]
        )
        self.assertFalse(actions.sstringarray.is_empty("tag_sstring_array"))

    def test_array_clear(self):
        actions.sstringarray.set_val("tag_sstring_array", ["VALUE1", "", "VALUE3", ""])
        actions.sstringarray.clear("tag_sstring_array")
        self.assertTrue(actions.sstringarray.is_empty("tag_sstring_array"))

    def test_array_find(self):
        actions.sstringarray.set_val(
            "tag_sstring_array", ["VALUE1", "VALUE2", "VALUE3", "VALUE4"]
        )
        v = actions.sstringarray.find("tag_sstring_array", "VALUE2")
        self.assertEqual(v, 1)

    def test_array_not_found(self):
        actions.sstringarray.set_val(
            "tag_sstring_array", ["VALUE1", "VALUE2", "VALUE3", "VALUE4"]
        )
        v = actions.sstringarray.find("tag_sstring_array", "VALUE5")
        self.assertIsNone(v)
