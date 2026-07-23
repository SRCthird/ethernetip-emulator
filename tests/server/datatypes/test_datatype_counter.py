# Copyright 2026 Merck KGaA, Darmstadt, Germany and/or its affiliates.
# All rights reserved

# test/server/datatypes/test_datatype_counter.py
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


# ---------------------------------------------------------------------------
# TestDatatypeCounterRegistry
# ---------------------------------------------------------------------------


class TestDatatypeCounterRegistry(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.server_control, cls.thread = _start_server(next_port())

    @classmethod
    def tearDownClass(cls) -> None:
        _stop_server(cls.server_control, cls.thread)

    def test_type_validator_rejects_bool(self):
        with self.assertRaises((ValueError, TypeError)):
            tag_registry.register(lambda: [("ctr", actions.type.COUNTER(True))])

    def test_type_validator_rejects_float(self):
        with self.assertRaises((ValueError, TypeError)):
            tag_registry.register(lambda: [("ctr", actions.type.COUNTER(1.5))])

    def test_type_validator_rejects_string(self):
        with self.assertRaises((ValueError, TypeError)):
            tag_registry.register(lambda: [("ctr", actions.type.COUNTER("10"))])

    def test_type_validator_accepts_int(self):
        tag_registry.register(lambda: [("ctr_valid", actions.type.COUNTER(5))])
        tag_registry.invalidate()
        tag_registry._raw.clear()

    def test_type_validator_accepts_zero(self):
        tag_registry.register(lambda: [("ctr_zero", actions.type.COUNTER(0))])
        tag_registry.invalidate()
        tag_registry._raw.clear()

    def test_expander_creates_all_sub_tags(self):
        tag_registry.register(lambda: [("CTR", actions.type.COUNTER(10))])
        built_names = {n for n, _, _ in tag_registry.build()}
        for suffix in ("PRE", "ACC", "CU", "CD", "DN", "OV", "UN", "RES"):
            with self.subTest(suffix=suffix):
                self.assertIn(f"CTR.{suffix}", built_names)
        tag_registry.invalidate()
        tag_registry._raw.clear()

    def test_expander_sets_preset_from_default(self):
        tag_registry.register(lambda: [("CTR2", actions.type.COUNTER(99))])
        built = {n: d for n, _, d in tag_registry.build()}
        self.assertEqual(built["CTR2.PRE"], 99)
        tag_registry.invalidate()
        tag_registry._raw.clear()


# ---------------------------------------------------------------------------
# TestDatatypeCounterActions
# ---------------------------------------------------------------------------


class TestDatatypeCounterActions(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        tag_registry.register(lambda: [("CTR", actions.type.COUNTER(3))])
        cls.server_control, cls.thread = _start_server(next_port())

    @classmethod
    def tearDownClass(cls) -> None:
        _stop_server(cls.server_control, cls.thread)

    def setUp(self) -> None:
        AttributeDevice._ensure_defaults()
        actions.counter.reset("CTR")

    # --- getters / setters --------------------------------------------------

    def test_get_preset_value(self):
        self.assertEqual(actions.counter.get_preset_value("CTR"), 3)

    def test_set_preset_value(self):
        actions.counter.set_preset_value("CTR", 10)
        self.assertEqual(actions.counter.get_preset_value("CTR"), 10)

    def test_get_accumulated_value_starts_at_zero(self):
        self.assertEqual(actions.counter.get_accumulated_value("CTR"), 0)

    def test_get_count_up_bit_starts_false(self):
        self.assertFalse(actions.counter.get_count_up_bit("CTR"))

    def test_get_count_down_bit_starts_false(self):
        self.assertFalse(actions.counter.get_count_down_bit("CTR"))

    def test_get_done_bit_starts_false(self):
        self.assertFalse(actions.counter.get_done_bit("CTR"))

    def test_get_overflow_bit_starts_false(self):
        self.assertFalse(actions.counter.get_overflow_bit("CTR"))

    def test_get_underflow_bit_starts_false(self):
        self.assertFalse(actions.counter.get_underflow_bit("CTR"))

    def test_get_reset_bit_starts_false(self):
        self.assertFalse(actions.counter.get_reset_bit("CTR"))

    # --- increment ----------------------------------------------------------

    def test_increment_increases_acc(self):
        actions.counter.increment("CTR")
        self.assertEqual(actions.counter.get_accumulated_value("CTR"), 1)

    def test_increment_accumulates(self):
        actions.counter.increment("CTR")
        actions.counter.increment("CTR")
        self.assertEqual(actions.counter.get_accumulated_value("CTR"), 2)

    def test_increment_sets_done_at_preset(self):
        actions.counter.increment("CTR")
        actions.counter.increment("CTR")
        actions.counter.increment("CTR")
        self.assertTrue(actions.counter.get_done_bit("CTR"))

    def test_increment_clears_overflow_bit(self):
        actions.counter._set_overflow_bit("CTR", True)
        actions.counter.increment("CTR")
        self.assertFalse(actions.counter.get_overflow_bit("CTR"))

    def test_increment_at_dint_max_sets_overflow_and_resets_acc(self):
        actions.counter._set_accumulated_value("CTR", actions.dint.MAX)
        actions.counter.increment("CTR")
        self.assertTrue(actions.counter.get_overflow_bit("CTR"))
        self.assertEqual(actions.counter.get_accumulated_value("CTR"), 0)

    def test_decrement_decreases_acc(self):
        actions.counter._set_accumulated_value("CTR", 3)
        actions.counter.decrement("CTR")
        self.assertEqual(actions.counter.get_accumulated_value("CTR"), 2)

    def test_decrement_clears_done_below_preset(self):
        actions.counter._set_accumulated_value("CTR", 3)
        actions.counter._set_done_bit("CTR", True)
        actions.counter.decrement("CTR")
        self.assertFalse(actions.counter.get_done_bit("CTR"))

    def test_decrement_clears_underflow_bit(self):
        actions.counter._set_accumulated_value("CTR", 1)
        actions.counter._set_underflow_bit("CTR", True)
        actions.counter.decrement("CTR")
        self.assertFalse(actions.counter.get_underflow_bit("CTR"))

    def test_decrement_at_dint_min_sets_underflow_and_resets_acc(self):
        actions.counter._set_accumulated_value("CTR", actions.dint.MIN)
        actions.counter.decrement("CTR")
        self.assertTrue(actions.counter.get_underflow_bit("CTR"))
        self.assertEqual(actions.counter.get_accumulated_value("CTR"), 0)

    def test_reset_clears_acc(self):
        actions.counter._set_accumulated_value("CTR", 5)
        actions.counter.reset("CTR")
        self.assertEqual(actions.counter.get_accumulated_value("CTR"), 0)

    def test_reset_clears_done_bit(self):
        actions.counter._set_done_bit("CTR", True)
        actions.counter.reset("CTR")
        self.assertFalse(actions.counter.get_done_bit("CTR"))

    def test_reset_clears_overflow_bit(self):
        actions.counter._set_overflow_bit("CTR", True)
        actions.counter.reset("CTR")
        self.assertFalse(actions.counter.get_overflow_bit("CTR"))

    def test_reset_clears_underflow_bit(self):
        actions.counter._set_underflow_bit("CTR", True)
        actions.counter.reset("CTR")
        self.assertFalse(actions.counter.get_underflow_bit("CTR"))

    def test_reset_clears_reset_bit(self):
        actions.counter._set_reset_bit("CTR", True)
        actions.counter.reset("CTR")
        self.assertFalse(actions.counter.get_reset_bit("CTR"))

    def test_on_set_hook_triggers_reset_on_res_tag(self):
        """Writing True to CTR.RES must reset the counter via on_set_hook."""
        actions.counter._set_accumulated_value("CTR", 5)
        actions.counter._set_done_bit("CTR", True)
        actions.bool.set_val("CTR.RES", True)
        self.assertEqual(actions.counter.get_accumulated_value("CTR"), 0)
        self.assertFalse(actions.counter.get_done_bit("CTR"))

    def test_is_done_returns_false_initially(self):
        signal = actions.counter.is_done("CTR")
        self.assertFalse(bool(signal))

    def test_is_done_returns_true_when_done(self):
        actions.counter._set_done_bit("CTR", True)
        signal = actions.counter.is_done("CTR")
        self.assertTrue(bool(signal))

    def test_is_done_callback_fires_on_rising_edge(self):
        fired = []
        signal = actions.counter.is_done("CTR")

        @signal
        def _(attr, key, value):
            fired.append(value[0])

        actions.counter._set_done_bit("CTR", True)
        self.assertTrue(fired[-1])

    def test_is_done_callback_skips_on_false(self):
        fired = []
        signal = actions.counter.is_done("CTR")

        @signal
        def _(attr, key, value):
            fired.append(value[0])

        actions.counter._set_done_bit("CTR", False)
        self.assertEqual(fired, [])

    def test_is_done_callback_no_rising_edge_guard(self):
        fired = []
        signal = actions.counter.is_done("CTR")

        @signal(rising_edge=False)
        def _(attr, key, value):
            fired.append(value[0])

        actions.counter._set_done_bit("CTR", False)
        self.assertFalse(fired[-1])

    def test_is_reset_returns_false_initially(self):
        signal = actions.counter.is_reset("CTR")
        self.assertFalse(bool(signal))

    def test_is_reset_callback_fires(self):
        fired = []
        signal = actions.counter.is_reset("CTR")

        @signal
        def _(attr, key, value):
            fired.append(value[0])

        actions.counter._set_reset_bit("CTR", True)
        self.assertTrue(fired[-1])

    # --- start / run_worker -------------------------------------------------

    def test_start_increments_over_time(self):
        with actions:
            actions.counter.start("CTR", period=0.05, preset=0, initial_delay=0.0)
            time.sleep(0.3)
        self.assertGreater(actions.counter.get_accumulated_value("CTR"), 0)

    def test_start_sets_count_up_bit(self):
        with actions:
            actions.counter.start("CTR", period=0.05, preset=0, initial_delay=0.0)
            time.sleep(0.1)
            self.assertTrue(actions.counter.get_count_up_bit("CTR"))

    def test_start_clears_count_up_bit_on_stop(self):
        with actions:
            actions.counter.start("CTR", period=0.05, preset=0, initial_delay=0.0)
            time.sleep(0.1)
        self.assertFalse(actions.counter.get_count_up_bit("CTR"))

    def test_start_sets_done_and_resets_acc_at_preset(self):
        done_fired = []
        signal = actions.counter.is_done("CTR")

        @signal
        def _(attr, key, value):
            done_fired.append(value[0])

        with actions:
            actions.counter.start("CTR", period=0.05, preset=3, initial_delay=0.0)
            time.sleep(0.5)
        self.assertTrue(len(done_fired) > 0)

    def test_start_with_preset_kwarg_overrides_tag(self):
        with actions:
            actions.counter.start("CTR", period=0.05, preset=5, initial_delay=0.0)
            time.sleep(0.1)
        self.assertEqual(actions.counter.get_preset_value("CTR"), 5)

    def test_start_enable_callable_gates_counting(self):
        gate = threading.Event()

        with actions:
            actions.counter.start(
                "CTR",
                period=0.05,
                preset=0,
                initial_delay=0.0,
                enable=lambda: gate.is_set(),
            )
            time.sleep(0.2)
            val_gated = actions.counter.get_accumulated_value("CTR")
            gate.set()
            time.sleep(0.2)
        val_open = actions.counter.get_accumulated_value("CTR")
        self.assertEqual(val_gated, 0)
        self.assertGreater(val_open, 0)

    def test_start_enable_tag_gates_counting(self):
        with actions:
            actions.counter.start(
                "CTR",
                period=0.05,
                preset=0,
                initial_delay=0.0,
                enable="CTR.CD",
            )
            time.sleep(0.2)
            val_gated = actions.counter.get_accumulated_value("CTR")
            actions.bool.set_val("CTR.CD", True)
            time.sleep(0.2)
        val_open = actions.counter.get_accumulated_value("CTR")
        self.assertEqual(val_gated, 0)
        self.assertGreater(val_open, 0)

    def test_run_worker_respects_initial_delay(self):
        stop = threading.Event()
        actions._stop = stop

        t = threading.Thread(
            target=actions.counter.run_worker,
            kwargs=dict(
                tag_prefix="CTR",
                period=0.05,
                preset=0,
                initial_delay=0.3,
                enable=None,
            ),
            daemon=True,
        )
        t.start()
        time.sleep(0.1)
        val_during_delay = actions.counter.get_accumulated_value("CTR")
        stop.set()
        t.join(timeout=2.0)
        self.assertEqual(val_during_delay, 0)

    def test_run_worker_overflow(self):
        actions.counter._set_accumulated_value("CTR", actions.dint.MAX)

        ov_snapshot = []
        acc_snapshot = []

        original_sleep = actions.counter.parent._sleep

        def capture_and_stop(period):
            # Capture state at the moment of sleep — OV is True, ACC is 0
            ov_snapshot.append(actions.counter.get_overflow_bit("CTR"))
            acc_snapshot.append(actions.counter.get_accumulated_value("CTR"))
            actions.counter.parent._stop.set()

        actions.counter.parent._sleep = capture_and_stop
        actions.counter.parent._stop.clear()
        try:
            actions.counter.run_worker(
                tag_prefix="CTR",
                period=0.0,
                preset=0,
                initial_delay=0.0,
                enable=None,
            )
        finally:
            actions.counter.parent._sleep = original_sleep
            actions.counter.parent._stop.clear()

        # OV was True and ACC was 0 at the moment of the overflow sleep
        self.assertTrue(ov_snapshot[0])
        self.assertEqual(acc_snapshot[0], 0)


if __name__ == "__main__":
    unittest.main()
