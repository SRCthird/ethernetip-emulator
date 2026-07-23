# Copyright 2026 Merck KGaA, Darmstadt, Germany and/or its affiliates.
# All rights reserved

# test/server/datatypes/test_datatype_timer.py
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


class TestDatatypeTimerRegistry(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.server_control, cls.thread = _start_server(next_port())

    @classmethod
    def tearDownClass(cls) -> None:
        _stop_server(cls.server_control, cls.thread)

    def test_type_validator_rejects_float(self):
        with self.assertRaises((ValueError, TypeError)):
            tag_registry.register(lambda: [("TMR", actions.type.TIMER(1.5))])

    def test_type_validator_rejects_string(self):
        with self.assertRaises((ValueError, TypeError)):
            tag_registry.register(lambda: [("TMR", actions.type.TIMER("500"))])

    def test_type_validator_rejects_bool(self):
        with self.assertRaises((ValueError, TypeError)):
            tag_registry.register(lambda: [("TMR", actions.type.TIMER(True))])

    def test_type_validator_accepts_int(self):
        tag_registry.register(lambda: [("TMR_V", actions.type.TIMER(500))])
        tag_registry.invalidate()
        tag_registry._raw.clear()

    def test_type_validator_accepts_zero(self):
        tag_registry.register(lambda: [("TMR_Z", actions.type.TIMER(0))])
        tag_registry.invalidate()
        tag_registry._raw.clear()

    def test_expander_creates_all_sub_tags(self):
        tag_registry.register(lambda: [("TMR_E", actions.type.TIMER(100))])
        built_names = {n for n, _, _ in tag_registry.build()}
        for suffix in ("PRE", "ACC", "EN", "TT", "DN"):
            with self.subTest(suffix=suffix):
                self.assertIn(f"TMR_E.{suffix}", built_names)
        tag_registry.invalidate()
        tag_registry._raw.clear()

    def test_expander_sets_preset_from_default(self):
        tag_registry.register(lambda: [("TMR_P", actions.type.TIMER(250))])
        built = {n: d for n, _, d in tag_registry.build()}
        self.assertEqual(built["TMR_P.PRE"], 250)
        tag_registry.invalidate()
        tag_registry._raw.clear()


class TestDatatypeTimerActions(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        tag_registry.register(lambda: [("TMR", actions.type.TIMER(200))])
        cls.server_control, cls.thread = _start_server(next_port())

    @classmethod
    def tearDownClass(cls) -> None:
        _stop_server(cls.server_control, cls.thread)

    def setUp(self) -> None:
        AttributeDevice._ensure_defaults()
        actions._lookup("TMR.ACC")[slice(0, 1)] = [0]  # type: ignore
        actions._lookup("TMR.EN")[slice(0, 1)] = [False]  # type: ignore
        actions._lookup("TMR.TT")[slice(0, 1)] = [False]  # type: ignore
        actions._lookup("TMR.DN")[slice(0, 1)] = [False]  # type: ignore
        actions._lookup("TMR.PRE")[slice(0, 1)] = [2000]  # type: ignore
        time.sleep(0.15)

    def test_get_preset_default(self):
        self.assertEqual(actions.timer.get_preset("TMR"), 2000)

    def test_set_preset(self):
        actions.timer.set_preset("TMR", 500)
        self.assertEqual(actions.timer.get_preset("TMR"), 500)

    def test_get_accumulator_starts_at_zero(self):
        self.assertEqual(actions.timer.get_accumulator("TMR"), 0)

    def test_set_accumulator(self):
        actions.timer.set_accumulator("TMR", 99)
        self.assertEqual(actions.timer.get_accumulator("TMR"), 99)

    def test_en_starts_false(self):
        self.assertFalse(actions.bool.get_val("TMR.EN"))

    def test_tt_starts_false(self):
        self.assertFalse(actions.bool.get_val("TMR.TT"))

    def test_dn_starts_false(self):
        self.assertFalse(actions.bool.get_val("TMR.DN"))

    def test_tt_set_while_timing(self):
        actions.timer.set_preset("TMR", 1000)
        actions.bool.set_val("TMR.EN", True)
        time.sleep(0.4)
        self.assertTrue(actions.bool.get_val("TMR.TT"))
        actions.bool.set_val("TMR.EN", False)

    def test_acc_increases_while_timing(self):
        actions.timer.set_preset("TMR", 1000)
        actions.bool.set_val("TMR.EN", True)
        time.sleep(0.4)
        acc = actions.timer.get_accumulator("TMR")
        actions.bool.set_val("TMR.EN", False)
        self.assertGreater(acc, 0)

    def test_dn_set_after_preset_elapsed(self):
        actions.timer.set_preset("TMR", 100)
        actions.bool.set_val("TMR.EN", True)
        time.sleep(0.4)
        dn = actions.bool.get_val("TMR.DN")
        actions.bool.set_val("TMR.EN", False)
        self.assertTrue(dn)

    def test_tt_cleared_after_done(self):
        actions.timer.set_preset("TMR", 100)
        actions.bool.set_val("TMR.EN", True)
        time.sleep(0.4)
        tt = actions.bool.get_val("TMR.TT")
        actions.bool.set_val("TMR.EN", False)
        self.assertFalse(tt)

    def test_acc_capped_at_preset(self):
        actions.timer.set_preset("TMR", 100)
        actions.bool.set_val("TMR.EN", True)
        time.sleep(0.5)
        acc = actions.timer.get_accumulator("TMR")
        actions.bool.set_val("TMR.EN", False)
        self.assertLessEqual(acc, 100)

    def test_disable_resets_acc_and_clears_bits(self):
        actions.timer.set_preset("TMR", 500)
        actions.bool.set_val("TMR.EN", True)
        time.sleep(0.2)
        actions.bool.set_val("TMR.EN", False)
        time.sleep(0.15)
        self.assertEqual(actions.timer.get_accumulator("TMR"), 0)
        self.assertFalse(actions.bool.get_val("TMR.TT"))
        self.assertFalse(actions.bool.get_val("TMR.DN"))

    def test_reset_clears_acc(self):
        actions.timer.set_accumulator("TMR", 50)
        actions.timer.reset("TMR")
        self.assertEqual(actions.timer.get_accumulator("TMR"), 0)

    def test_reset_clears_en(self):
        actions.bool.set_val("TMR.EN", True)
        actions.timer.reset("TMR")
        self.assertFalse(actions.bool.get_val("TMR.EN"))

    def test_reset_clears_tt(self):
        actions.bool.set_val("TMR.TT", True)
        actions.timer.reset("TMR")
        self.assertFalse(actions.bool.get_val("TMR.TT"))

    def test_reset_clears_dn(self):
        actions.bool.set_val("TMR.DN", True)
        actions.timer.reset("TMR")
        self.assertFalse(actions.bool.get_val("TMR.DN"))

    def test_is_timing_false_initially(self):
        self.assertFalse(bool(actions.timer.is_timing("TMR")))

    def test_is_done_false_initially(self):
        self.assertFalse(bool(actions.timer.is_done("TMR")))

    def test_is_enabled_false_initially(self):
        self.assertFalse(bool(actions.timer.is_enabled("TMR")))

    def test_is_timing_true_while_timing(self):
        actions.timer.set_preset("TMR", 500)
        actions.bool.set_val("TMR.EN", True)
        time.sleep(0.15)
        result = bool(actions.timer.is_timing("TMR"))
        actions.bool.set_val("TMR.EN", False)
        self.assertTrue(result)

    def test_is_done_true_after_preset(self):
        actions.timer.set_preset("TMR", 100)
        actions.bool.set_val("TMR.EN", True)
        time.sleep(0.4)
        result = bool(actions.timer.is_done("TMR"))
        actions.bool.set_val("TMR.EN", False)
        self.assertTrue(result)

    def test_is_done_callback_fires_on_rising_edge(self):
        fired = []
        signal = actions.timer.is_done("TMR")

        @signal
        def _(attr, key, value):
            fired.append(value[0])

        actions.timer.set_preset("TMR", 100)
        actions.bool.set_val("TMR.EN", True)
        time.sleep(0.4)
        actions.bool.set_val("TMR.EN", False)
        self.assertTrue(len(fired) > 0)
        self.assertTrue(fired[0])

    def test_is_done_callback_skips_false(self):
        fired = []
        signal = actions.timer.is_done("TMR")

        @signal
        def _(attr, key, value):
            fired.append(value[0])

        actions.bool.set_val("TMR.DN", False)
        self.assertEqual(fired, [])

    def test_is_timing_callback_fires(self):
        fired = []
        signal = actions.timer.is_timing("TMR")

        @signal
        def _(attr, key, value):
            fired.append(value[0])

        actions.timer.set_preset("TMR", 500)
        actions.bool.set_val("TMR.EN", True)
        time.sleep(0.2)
        actions.bool.set_val("TMR.EN", False)
        self.assertTrue(len(fired) > 0)
        self.assertTrue(fired[0])

    def test_is_enabled_callback_fires(self):
        fired = []
        signal = actions.timer.is_enabled("TMR")

        @signal
        def _(attr, key, value):
            fired.append(value[0])

        actions.bool.set_val("TMR.EN", True)
        time.sleep(0.05)
        actions.bool.set_val("TMR.EN", False)
        self.assertTrue(fired[0])

    def test_is_done_no_rising_edge_guard(self):
        fired = []
        signal = actions.timer.is_done("TMR")

        def _(attr, key, value):
            fired.append(value[0])

        signal(_, rising_edge=False)
        actions.bool.set_val("TMR.DN", False)
        self.assertFalse(fired[-1])


class TestDatatypeTimerRunWorker(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        tag_registry.register(lambda: [("TWR", actions.type.TIMER(200))])
        cls.server_control, cls.thread = _start_server(next_port())

    @classmethod
    def tearDownClass(cls) -> None:
        _stop_server(cls.server_control, cls.thread)

    def setUp(self) -> None:
        AttributeDevice._ensure_defaults()
        actions.timer.reset("TWR")
        actions.timer.set_preset("TWR", 2000)
        time.sleep(0.15)

    def test_start_defers_launch_when_not_entered(self):
        self.assertFalse(actions.timer.parent._entered)

        pending_before = len(actions.timer.parent._pending)
        actions.timer.start(
            "TWR",
            period=0.05,
            preset_ms=None,
            initial_delay=0.0,
            enable=None,
        )
        pending_after = len(actions.timer.parent._pending)

        self.assertEqual(pending_after, pending_before + 1)

        self.assertTrue(callable(actions.timer.parent._pending[-1]))

        actions.timer.parent._pending.pop()

    def test_run_worker_enable_none_runs_unconditionally(self):
        stop = threading.Event()

        original_stop = actions.timer.parent._stop
        actions.timer.parent._stop = stop
        try:
            actions.timer.set_preset("TWR", 2000)
            t = threading.Thread(
                target=actions.timer.run_worker,
                kwargs=dict(
                    tag_prefix="TWR",
                    period=0.05,
                    preset_ms=None,
                    initial_delay=0.0,
                    enable=None,
                ),
                daemon=True,
            )
            t.start()
            time.sleep(0.3)
            acc = actions.timer.get_accumulator("TWR")
            tt = actions.bool.get_val("TWR.TT")
            stop.set()
            t.join(timeout=2.0)
        finally:
            actions.timer.parent._stop = original_stop

        self.assertGreater(acc, 0, "ACC must have advanced with enable=None")
        self.assertTrue(tt, "TT must be True while timing with enable=None")

    def test_run_worker_respects_initial_delay(self):
        stop = threading.Event()
        original_stop = actions.timer.parent._stop
        actions.timer.parent._stop = stop
        try:
            t = threading.Thread(
                target=actions.timer.run_worker,
                kwargs=dict(
                    tag_prefix="TWR",
                    period=0.05,
                    preset_ms=None,
                    initial_delay=0.3,
                    enable=None,
                ),
                daemon=True,
            )
            t.start()
            time.sleep(0.1)
            acc_during_delay = actions.timer.get_accumulator("TWR")
            stop.set()
            t.join(timeout=2.0)
        finally:
            actions.timer.parent._stop = original_stop

        self.assertEqual(acc_during_delay, 0)

    def test_run_worker_callable_enable_gates_timing(self):
        gate = threading.Event()
        actions.timer.set_preset("TWR", 2000)

        with actions:
            actions.timer.start(
                "TWR",
                period=0.05,
                preset_ms=2000,
                initial_delay=0.0,
                enable=lambda: gate.is_set(),
            )
            time.sleep(0.3)
            acc_gated = actions.timer.get_accumulator("TWR")
            gate.set()
            time.sleep(0.3)
            acc_open = actions.timer.get_accumulator("TWR")

        self.assertEqual(acc_gated, 0)
        self.assertGreater(acc_open, 0)


if __name__ == "__main__":
    unittest.main()
