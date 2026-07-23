# Copyright 2026 Merck KGaA, Darmstadt, Germany and/or its affiliates.
# All rights reserved

# test/server/datatypes/test_datatype_increment.py
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


class TestDatatypeIncrementRegistry(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.server_control, cls.thread = _start_server(next_port())

    @classmethod
    def tearDownClass(cls) -> None:
        _stop_server(cls.server_control, cls.thread)

    def test_type_validator_always_raises(self):
        with self.assertRaises((ValueError, TypeError)):
            tag_registry.register(
                lambda: [("tag_increment", actions.type.INCREMENT(0))]
            )


class TestDatatypeIncrementActions(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        tag_registry.register(lambda: [("tag_inc", actions.type.INT(0))])
        cls.server_control, cls.thread = _start_server(next_port())

    @classmethod
    def tearDownClass(cls) -> None:
        _stop_server(cls.server_control, cls.thread)

    def setUp(self) -> None:
        AttributeDevice._ensure_defaults()
        actions._lookup("tag_inc")[slice(0, 1)] = [0]  # type: ignore

    def test_increment_adds_one(self):
        actions.increment.increment("tag_inc")
        self.assertEqual(actions.int.get_val("tag_inc"), 1)

    def test_increment_custom_amount(self):
        actions.increment.increment("tag_inc", increment=5)
        self.assertEqual(actions.int.get_val("tag_inc"), 5)

    def test_increment_accumulates(self):
        actions.increment.increment("tag_inc")
        actions.increment.increment("tag_inc")
        actions.increment.increment("tag_inc")
        self.assertEqual(actions.int.get_val("tag_inc"), 3)

    def test_increment_missing_tag_does_not_raise(self):
        actions.increment.increment("no_tag")

    def test_decrement_subtracts_one(self):
        actions.int.set_val("tag_inc", 5)
        actions.increment.decrement("tag_inc")
        self.assertEqual(actions.int.get_val("tag_inc"), 4)

    def test_decrement_custom_amount(self):
        actions.int.set_val("tag_inc", 10)
        actions.increment.decrement("tag_inc", 4)
        self.assertEqual(actions.int.get_val("tag_inc"), 6)

    def test_decrement_into_negative(self):
        actions.increment.decrement("tag_inc")
        self.assertEqual(actions.int.get_val("tag_inc"), -1)

    def test_decrement_missing_tag_does_not_raise(self):
        actions.increment.decrement("no_tag")

    def test_reset_to_zero(self):
        actions.int.set_val("tag_inc", 99)
        actions.increment.reset("tag_inc")
        self.assertEqual(actions.int.get_val("tag_inc"), 0)

    def test_reset_custom_default(self):
        actions.int.set_val("tag_inc", 99)
        actions.increment.reset("tag_inc", default=42)
        self.assertEqual(actions.int.get_val("tag_inc"), 42)

    def test_reset_missing_tag_does_not_raise(self):
        actions.increment.reset("no_tag")

    def test_start_increments_over_time(self):
        actions.int.set_val("tag_inc", 0)
        with actions:
            actions.increment.start("tag_inc", period=0.05, initial_delay=0.0)
            time.sleep(0.2)
        val = actions.int.get_val("tag_inc")
        self.assertGreater(val, 0)

    def test_start_with_custom_increment(self):
        actions.int.set_val("tag_inc", 0)
        with actions:
            actions.increment.start(
                "tag_inc", period=0.05, increment=10, initial_delay=0.0
            )
            time.sleep(0.2)
        val = actions.int.get_val("tag_inc")
        self.assertGreater(val, 0)
        self.assertEqual(val % 10, 0)

    def test_start_with_wrap(self):
        actions.int.set_val("tag_inc", 0)
        with actions:
            actions.increment.start(
                "tag_inc", period=0.05, increment=1, wrap=5, initial_delay=0.0
            )
            time.sleep(0.35)
        val = actions.int.get_val("tag_inc")
        self.assertGreaterEqual(val, 0)
        self.assertLess(val, 5)

    def test_start_with_explicit_start_value(self):
        actions.int.set_val("tag_inc", 0)
        with actions:
            actions.increment.start(
                "tag_inc", period=0.05, start=100, increment=1, initial_delay=0.0
            )
            time.sleep(0.15)
        val = actions.int.get_val("tag_inc")
        self.assertGreater(val, 100)

    def test_start_stops_on_context_exit(self):
        actions.int.set_val("tag_inc", 0)
        with actions:
            actions.increment.start("tag_inc", period=0.05, initial_delay=0.0)
            time.sleep(0.15)
        val_at_stop = actions.int.get_val("tag_inc")
        time.sleep(0.2)
        val_after = actions.int.get_val("tag_inc")
        self.assertEqual(val_at_stop, val_after)

    def test_run_worker_respects_initial_delay(self):
        actions.int.set_val("tag_inc", 0)
        stop = threading.Event()
        actions._stop = stop

        t = threading.Thread(
            target=actions.increment.run_worker,
            kwargs=dict(
                tag_name="tag_inc",
                period=0.05,
                key=slice(0, 1),
                start=0,
                increment=1,
                wrap=None,
                initial_delay=0.3,
            ),
            daemon=True,
        )
        t.start()
        time.sleep(0.1)
        val_during_delay = actions.int.get_val("tag_inc")
        stop.set()
        t.join(timeout=2.0)
        self.assertEqual(val_during_delay, 0)

    def test_run_worker_skips_when_attr_none(self):
        actions.int.set_val("tag_inc", 0)
        stop = threading.Event()
        actions._stop = stop

        t = threading.Thread(
            target=actions.increment.run_worker,
            kwargs=dict(
                tag_name="no_tag",
                period=0.05,
                key=slice(0, 1),
                start=0,
                increment=1,
                wrap=None,
                initial_delay=0.0,
            ),
            daemon=True,
        )
        t.start()
        time.sleep(0.2)
        stop.set()
        t.join(timeout=2.0)
        self.assertEqual(actions.int.get_val("tag_inc"), 0)


if __name__ == "__main__":
    unittest.main()
