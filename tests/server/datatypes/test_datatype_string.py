# Copyright 2026 Merck KGaA, Darmstadt, Germany and/or its affiliates.
# All rights reserved

# test/server/datatypes/test_datatype_string.py
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


class TestDatatypeSStringRegistry(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.server_control, cls.thread = _start_server(next_port())

    @classmethod
    def tearDownClass(cls) -> None:
        _stop_server(cls.server_control, cls.thread)

    def test_type_validator_invalid_string(self):
        with self.assertRaises(ValueError):
            tag_registry.register(lambda: [("tag_string", actions.type.STRING(42))])


class TestDatatypeSStringActions(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        @tag_registry.register
        def _():
            return [
                ("tag_string", actions.type.STRING("")),
            ]

        cls.server_control, cls.thread = _start_server(next_port())

    @classmethod
    def tearDownClass(cls) -> None:
        _stop_server(cls.server_control, cls.thread)

    def setUp(self) -> None:
        AttributeDevice._ensure_defaults()
        actions._lookup("tag_string.DATA")[slice(0, 1)] = [""]  # type: ignore
        actions._lookup("tag_string.LEN")[slice(0, 1)] = [0]  # type: ignore

    def test_get_val(self):
        self.assertEqual(actions.string.get_val("tag_string"), "")

    def test_get_val_is_none(self):
        v = actions.string.get_val("no_tag")
        self.assertIsNone(v)

    def test_set_val(self):
        actions.string.set_val("tag_string", "VALUE!")
        self.assertEqual(actions.string.get_val("tag_string"), "VALUE!")

    def test_set_val_is_none(self):
        v = actions.string.set_val("no_tag", "VALUE!")
        self.assertIsNone(v)

    def test_get_len(self):
        v = "VALUE!"
        actions.string.set_val("tag_string", v)
        l = actions.string.get_len("tag_string")
        self.assertEqual(l, len(v))

    def test_get_len_is_zero(self):
        v = actions.string.get_len("no_tag")
        self.assertEqual(v, 0)

    def test_on_change(self):
        changed = []

        @actions.string.on_change("tag_string")
        def _(attr, key, value):
            changed.append(value[0])

        actions.string.set_val("tag_string", "VALUE!")
        self.assertEqual(changed[-1], "VALUE!")
