# Copyright 2026 Merck KGaA, Darmstadt, Germany and/or its affiliates.
# All rights reserved

# tests/server/datatypes/test_counter.py
from __future__ import annotations

import sys
import types
import unittest
from unittest.mock import MagicMock, call, patch
from typing import Any, Dict


def _install_cpppo_stubs() -> None:
    if "cpppo" in sys.modules and not isinstance(sys.modules["cpppo"], MagicMock):
        return

    class _BaseAttribute:
        def __init__(self, name: str, type_cls: Any, **kwargs: Any) -> None:
            self.name = name
            self.type_cls = type_cls
            self.kwargs = kwargs
            self._store: Dict = {}

        def __setitem__(self, key, value):
            self._store[key] = value

        def __getitem__(self, key):
            return self._store[key]

    enip_device_mod = types.ModuleType("cpppo.server.enip.device")
    enip_device_mod.Attribute = _BaseAttribute  # type: ignore
    enip_mod = types.ModuleType("cpppo.server.enip")
    enip_mod.device = enip_device_mod  # type: ignore
    server_mod = types.ModuleType("cpppo.server")
    server_mod.enip = enip_mod  # type: ignore
    cpppo_mod = types.ModuleType("cpppo")
    cpppo_mod.server = server_mod  # type: ignore
    sys.modules["cpppo"] = cpppo_mod
    sys.modules["cpppo.server"] = server_mod
    sys.modules["cpppo.server.enip"] = enip_mod
    sys.modules["cpppo.server.enip.device"] = enip_device_mod


_install_cpppo_stubs()

from src.ethernetip_emulator.server.datatypes.counter import (
    Counter, CounterIsDoingSomething, CounterIsDone, CounterIsReset,
)
from src.ethernetip_emulator.server.tag_specs import tag_registry


def _make_parent(registry: Dict | None = None, stop_after: int = 1):
    parent = MagicMock()
    parent._logger = MagicMock()
    parent._sleep = MagicMock()

    call_count = [0]
    def _is_set():
        call_count[0] += 1
        return call_count[0] > stop_after
    parent._stop.is_set.side_effect = _is_set

    _attrs: Dict[str, Any] = {}
    if registry is not None:
        _attrs.update(registry)

    def _lookup(tag):
        return _attrs.get(tag)
    parent._lookup.side_effect = _lookup

    parent._read_attr.return_value = [0]

    return parent, _attrs


def _make_attr():
    """Return a simple mock attribute."""
    return MagicMock()


def _counter(parent=None):
    if parent is None:
        parent, _ = _make_parent()
    return Counter(parent)  # type: ignore


class TestCounterIsDoingSomething(unittest.TestCase):

    def _make(self, value=False):
        register_fn = MagicMock()
        obj = CounterIsDoingSomething(value, register_fn)
        return obj, register_fn

    def test_bool_true(self):
        obj, _ = self._make(True)
        self.assertTrue(bool(obj))

    def test_bool_false(self):
        obj, _ = self._make(False)
        self.assertFalse(bool(obj))

    def test_call_rising_edge_registers_guarded_fn(self):
        obj, register_fn = self._make()
        cb = MagicMock()
        obj(cb, rising_edge=True)
        register_fn.assert_called_once()

    def test_call_rising_edge_guarded_fn_skips_false_value(self):
        obj, register_fn = self._make()
        cb = MagicMock()
        obj(cb, rising_edge=True)
        guarded = register_fn.call_args[0][0]
        guarded(MagicMock(), slice(0, 1), [0])
        cb.assert_not_called()

    def test_call_rising_edge_guarded_fn_calls_cb_on_true_value(self):
        obj, register_fn = self._make()
        cb = MagicMock()
        obj(cb, rising_edge=True)
        guarded = register_fn.call_args[0][0]
        attr, key = MagicMock(), slice(0, 1)
        guarded(attr, key, [1])
        cb.assert_called_once_with(attr, key, [1])

    def test_call_rising_edge_guarded_name_preserved(self):
        obj, register_fn = self._make()
        def my_callback(a, k, v): pass
        obj(my_callback, rising_edge=True)
        guarded = register_fn.call_args[0][0]
        self.assertEqual(guarded.__name__, "my_callback")

    def test_call_no_rising_edge_registers_fn_directly(self):
        obj, register_fn = self._make()
        cb = MagicMock()
        result = obj(cb, rising_edge=False)
        register_fn.assert_called_once_with(cb)
        self.assertIs(result, cb)

    def test_call_returns_original_fn(self):
        obj, _ = self._make()
        cb = MagicMock()
        result = obj(cb, rising_edge=True)
        self.assertIs(result, cb)


class TestCounterIsDone(unittest.TestCase):
    def test_is_subclass_of_is_doing_something(self):
        self.assertTrue(issubclass(CounterIsDone, CounterIsDoingSomething))


class TestCounterIsReset(unittest.TestCase):
    def test_is_subclass_of_is_doing_something(self):
        self.assertTrue(issubclass(CounterIsReset, CounterIsDoingSomething))


class TestCounterRegistration(unittest.TestCase):

    def test_registered_on_module_level_actions(self):
        from src.ethernetip_emulator.server.device import actions
        self.assertIn("counter", actions._datatypes)

    def test_registered_instance_is_counter(self):
        from src.ethernetip_emulator.server.device import actions
        self.assertIsInstance(actions._datatypes["counter"], Counter)  # type: ignore

    def test_type_validator_valid_int(self):
        self.assertEqual(Counter.type_validator(5), 5)  # type: ignore
        self.assertEqual(Counter.type_validator(0), 0)  # type: ignore
        self.assertEqual(Counter.type_validator(-1), -1)  # type: ignore

    def test_type_validator_rejects_non_int(self):
        for bad in ("abc", 1.5, None, [1]):
            with self.subTest(v=bad):
                with self.assertRaises(TypeError):
                    Counter.type_validator(bad)  # type: ignore

    def test_expander_registered(self):
        self.assertIn("COUNTER", tag_registry._expanders)

    def test_expander_returns_8_tags(self):
        expander = tag_registry._expanders["COUNTER"]
        result = list(expander("CTR", 10))
        self.assertEqual(len(result), 8)

    def test_expander_tag_names(self):
        expander = tag_registry._expanders["COUNTER"]
        names = [entry[0] for entry in expander("CTR", 10)]
        for suffix in (".PRE", ".ACC", ".CU", ".CD", ".DN", ".OV", ".UN", ".RES"):
            self.assertIn(f"CTR{suffix}", names)

    def test_expander_pre_default_equals_preset(self):
        expander = tag_registry._expanders["COUNTER"]
        entries = {name: spec for name, spec in expander("CTR", 42)}
        self.assertEqual(entries["CTR.PRE"].default, 42)

    def test_expander_acc_default_is_zero(self):
        expander = tag_registry._expanders["COUNTER"]
        entries = {name: spec for name, spec in expander("CTR", 10)}
        self.assertEqual(entries["CTR.ACC"].default, 0)


class TestCounterOnSetHook(unittest.TestCase):

    def setUp(self):
        self.parent = MagicMock()
        self.counter = Counter(self.parent)  # type: ignore

    def test_on_set_hook_calls_reset_on_res_tag(self):
        with patch.object(self.counter, "reset") as mock_reset:
            key = slice(0, 1)
            self.counter.on_set_hook("MY_CTR.RES", MagicMock(), key, [1])
            mock_reset.assert_called_once_with("MY_CTR", key=key)

    def test_on_set_hook_ignores_non_res_tags(self):
        with patch.object(self.counter, "reset") as mock_reset:
            self.counter.on_set_hook("MY_CTR.ACC", MagicMock(), slice(0, 1), [1])
            mock_reset.assert_not_called()


class TestCounterIsDoneIsReset(unittest.TestCase):

    def setUp(self):
        self.parent = MagicMock()
        self.parent.on_change = MagicMock()

        from src.ethernetip_emulator.server.datatypes.counter import actions as _actions
        self._bool_dt = _actions._datatypes.get("bool")

    def _patch_get_val(self, val):
        from src.ethernetip_emulator.server.datatypes.counter import actions as _actions
        _actions._datatypes["bool"].get_val = MagicMock(return_value=int(val))

    def test_is_done_returns_counter_is_done(self):
        self._patch_get_val(False)
        counter = Counter(self.parent)  # type: ignore
        result = counter.is_done("CTR")
        self.assertIsInstance(result, CounterIsDone)

    def test_is_done_reflects_current_dn_value_true(self):
        self._patch_get_val(True)
        counter = Counter(self.parent)  # type: ignore
        result = counter.is_done("CTR")
        self.assertTrue(bool(result))

    def test_is_done_reflects_current_dn_value_false(self):
        self._patch_get_val(False)
        counter = Counter(self.parent)  # type: ignore
        result = counter.is_done("CTR")
        self.assertFalse(bool(result))
    def test_is_done_register_fn_calls_on_change(self):
        self._patch_get_val(False)
        counter = Counter(self.parent)  # type: ignore
        result = counter.is_done("CTR")
        cb = MagicMock()
        result(cb, rising_edge=False)
        self.parent.on_change.assert_called_once_with("CTR.DN", cb, defer=False)

    def test_is_reset_returns_counter_is_reset(self):
        self._patch_get_val(False)
        counter = Counter(self.parent)  # type: ignore
        result = counter.is_reset("CTR")
        self.assertIsInstance(result, CounterIsReset)

    def test_is_reset_register_fn_calls_on_change(self):
        self._patch_get_val(False)
        counter = Counter(self.parent)  # type: ignore
        result = counter.is_reset("CTR")
        cb = MagicMock()
        result(cb, rising_edge=False)
        self.parent.on_change.assert_called_once_with("CTR.RES", cb, defer=False)


class TestCounterStart(unittest.TestCase):

    def test_start_calls_start_worker(self):
        parent = MagicMock()
        counter = Counter(parent)  # type: ignore
        counter.start("CTR", period=0.5)
        parent._start_worker.assert_called_once()
        name, fn = parent._start_worker.call_args[0]
        self.assertEqual(name, "CTR-counter")
        self.assertTrue(callable(fn))

    def test_start_returns_parent_start_worker_result(self):
        parent = MagicMock()
        parent._start_worker.return_value = parent
        counter = Counter(parent)  # type: ignore
        result = counter.start("CTR")
        self.assertIs(result, parent)

    def test_start_worker_closure_calls_run_worker_with_correct_args(self):
        parent = MagicMock()
        counter = Counter(parent)  # type: ignore
        with patch.object(counter, "run_worker") as mock_run:
            counter.start(
                "CTR",
                period=0.5,
                key=slice(0, 2),
                preset=10,
                initial_delay=2.0,
                enable="EN_TAG",
            )
            _, worker_fn = parent._start_worker.call_args[0]
            worker_fn()
            mock_run.assert_called_once_with(
                tag_prefix="CTR",
                period=0.5,
                key=slice(0, 2),
                preset=10,
                initial_delay=2.0,
                enable="EN_TAG",
            )


class TestCounterRunWorker(unittest.TestCase):
    KEY = slice(0, 1)

    def _run(self, registry, stop_after=1, **kwargs):
        parent, attrs = _make_parent(registry, stop_after=stop_after)
        counter = Counter(parent)  # type: ignore
        counter.run_worker(
            tag_prefix="CTR",
            period=0.1,
            key=self.KEY,
            preset=None,
            initial_delay=0.0,
            **kwargs,
        )
        return parent, attrs

    def test_initial_sleep_skipped_when_zero(self):
        parent, _ = self._run({})
        initial_sleep_calls = [c for c in parent._sleep.call_args_list if c[0][0] == 0.0]
        self.assertEqual(initial_sleep_calls, [])

    def test_initial_sleep_called_when_positive(self):
        parent, attrs = _make_parent({}, stop_after=0)
        counter = Counter(parent)  # type: ignore
        counter.run_worker(
            tag_prefix="CTR", period=0.1, key=self.KEY,
            preset=None, initial_delay=1.5,
        )
        parent._sleep.assert_any_call(1.5)

    def test_preset_written_to_pre_attr_when_provided(self):
        pre_attr = _make_attr()
        parent, _ = _make_parent({"CTR.PRE": pre_attr}, stop_after=0)
        counter = Counter(parent)  # type: ignore
        counter.run_worker(
            tag_prefix="CTR", period=0.1, key=self.KEY,
            preset=99, initial_delay=0.0,
        )
        parent._write_attr.assert_any_call(pre_attr, self.KEY, [99])

    def test_preset_skipped_when_pre_attr_missing(self):
        parent, _ = _make_parent({}, stop_after=0)
        counter = Counter(parent)  # type: ignore
        counter.run_worker(
            tag_prefix="CTR", period=0.1, key=self.KEY,
            preset=5, initial_delay=0.0,
        )

    def test_cu_set_to_1_on_start(self):
        cu_attr = _make_attr()
        parent, _ = _make_parent({"CTR.CU": cu_attr}, stop_after=0)
        counter = Counter(parent)  # type: ignore
        counter.run_worker(
            tag_prefix="CTR", period=0.1, key=self.KEY,
            preset=None, initial_delay=0.0,
        )
        parent._write_attr.assert_any_call(cu_attr, self.KEY, [1])

    def test_cu_set_to_0_after_stop(self):
        cu_attr = _make_attr()
        parent, _ = _make_parent({"CTR.CU": cu_attr}, stop_after=1)
        counter = Counter(parent)  # type: ignore
        counter.run_worker(
            tag_prefix="CTR", period=0.1, key=self.KEY,
            preset=None, initial_delay=0.0,
        )
        cu_calls = [
            c for c in parent._write_attr.call_args_list
            if c[0][0] is cu_attr
        ]
        self.assertEqual(cu_calls[-1], call(cu_attr, self.KEY, [0]))

    def test_loop_sleeps_per_period_when_attrs_missing(self):
        parent, _ = _make_parent({}, stop_after=2)
        counter = Counter(parent)  # type: ignore
        counter.run_worker(
            tag_prefix="CTR", period=0.1, key=self.KEY,
            preset=None, initial_delay=0.0,
        )
        parent._sleep.assert_any_call(0.1)

    def test_acc_incremented_each_loop(self):
        acc_attr = _make_attr()
        pre_attr = _make_attr()

        parent, attrs = _make_parent(
            {"CTR.ACC": acc_attr, "CTR.PRE": pre_attr},
            stop_after=2,
        )
        parent._read_attr.side_effect = lambda attr, key: [0]

        counter = Counter(parent)  # type: ignore
        counter.run_worker(
            tag_prefix="CTR", period=0.0, key=self.KEY,
            preset=None, initial_delay=0.0,
        )
        acc_writes = [
            c for c in parent._write_attr.call_args_list
            if c[0][0] is acc_attr and c[0][2] == [1]
        ]
        self.assertGreater(len(acc_writes), 0)

    def test_dn_set_when_acc_reaches_pre(self):
        acc_attr = _make_attr()
        pre_attr = _make_attr()
        dn_attr  = _make_attr()

        reads = {acc_attr: [4], pre_attr: [5]}
        def _read(attr, key):
            return reads.get(attr, [0])

        parent, _ = _make_parent(
            {"CTR.ACC": acc_attr, "CTR.PRE": pre_attr, "CTR.DN": dn_attr},
            stop_after=1,
        )
        parent._read_attr.side_effect = _read

        counter = Counter(parent)  # type: ignore
        counter.run_worker(
            tag_prefix="CTR", period=0.0, key=self.KEY,
            preset=None, initial_delay=0.0,
        )
        dn_writes = [
            c for c in parent._write_attr.call_args_list
            if c[0][0] is dn_attr and c[0][2] == [1]
        ]
        self.assertGreater(len(dn_writes), 0)

    def test_ov_set_when_acc_at_max(self):
        from src.ethernetip_emulator.server.datatypes.counter import actions as _actions
        acc_attr = _make_attr()
        pre_attr = _make_attr()
        ov_attr  = _make_attr()

        reads = {acc_attr: [_actions.dint.MAX], pre_attr: [0]}
        def _read(attr, key):
            return reads.get(attr, [0])

        parent, _ = _make_parent(
            {"CTR.ACC": acc_attr, "CTR.PRE": pre_attr, "CTR.OV": ov_attr},
            stop_after=1,
        )
        parent._read_attr.side_effect = _read

        counter = Counter(parent)  # type: ignore
        counter.run_worker(
            tag_prefix="CTR", period=0.0, key=self.KEY,
            preset=None, initial_delay=0.0,
        )
        ov_writes_1 = [
            c for c in parent._write_attr.call_args_list
            if c[0][0] is ov_attr and c[0][2] == [1]
        ]
        self.assertGreater(len(ov_writes_1), 0)

    def test_enable_callable_gates_increment(self):
        acc_attr = _make_attr()
        pre_attr = _make_attr()
        parent, _ = _make_parent(
            {"CTR.ACC": acc_attr, "CTR.PRE": pre_attr},
            stop_after=1,
        )
        parent._read_attr.return_value = [0]
        counter = Counter(parent)  # type: ignore
        counter.run_worker(
            tag_prefix="CTR", period=0.0, key=self.KEY,
            preset=None, initial_delay=0.0,
            enable=lambda: False,
        )
        acc_writes = [
            c for c in parent._write_attr.call_args_list
            if c[0][0] is acc_attr
        ]
        self.assertEqual(acc_writes, [])

    def test_enable_tag_gates_increment_when_false(self):
        acc_attr  = _make_attr()
        pre_attr  = _make_attr()
        gate_attr = _make_attr()

        def _read(attr, key):
            if attr is gate_attr:
                return [0]
            return [0]

        parent, _ = _make_parent(
            {"CTR.ACC": acc_attr, "CTR.PRE": pre_attr, "EN": gate_attr},
            stop_after=1,
        )
        parent._read_attr.side_effect = _read
        counter = Counter(parent)  # type: ignore
        counter.run_worker(
            tag_prefix="CTR", period=0.0, key=self.KEY,
            preset=None, initial_delay=0.0,
            enable="EN",
        )
        acc_writes = [
            c for c in parent._write_attr.call_args_list
            if c[0][0] is acc_attr
        ]
        self.assertEqual(acc_writes, [])


class TestCounterIncrement(unittest.TestCase):

    KEY = slice(0, 1)

    def _make_counter(self, registry):
        parent, attrs = _make_parent(registry, stop_after=0)
        parent._read_attr.side_effect = lambda attr, key: attrs.get(
            next((k for k, v in registry.items() if v is attr), None), [0]  # type: ignore
        ) if isinstance(attrs.get(
            next((k for k, v in registry.items() if v is attr), None)  # type: ignore
        ), list) else [0]
        return Counter(parent), parent  # type: ignore

    def test_logs_when_essential_tags_missing(self):
        parent, _ = _make_parent({})
        counter = Counter(parent)  # type: ignore
        counter.increment("CTR")
        parent._logger.assert_called()

    def test_increments_acc_by_one(self):
        acc_attr = _make_attr()
        pre_attr = _make_attr()
        parent, _ = _make_parent({"CTR.ACC": acc_attr, "CTR.PRE": pre_attr})
        parent._read_attr.return_value = [5]
        counter = Counter(parent)  # type: ignore
        counter.increment("CTR", key=self.KEY)
        parent._write_attr.assert_any_call(acc_attr, self.KEY, [6])

    def test_overflow_sets_ov_and_resets_acc(self):
        from src.ethernetip_emulator.server.datatypes.counter import actions as _actions
        acc_attr = _make_attr()
        pre_attr = _make_attr()
        ov_attr  = _make_attr()

        reads = {id(acc_attr): [_actions.dint.MAX], id(pre_attr): [0]}
        def _read(attr, key):
            return reads.get(id(attr), [0])

        parent, _ = _make_parent({"CTR.ACC": acc_attr, "CTR.PRE": pre_attr, "CTR.OV": ov_attr})
        parent._read_attr.side_effect = _read
        counter = Counter(parent)  # type: ignore
        counter.increment("CTR", key=self.KEY)

        parent._write_attr.assert_any_call(ov_attr, self.KEY, [1])
        parent._write_attr.assert_any_call(acc_attr, self.KEY, [0])

    def test_dn_set_when_acc_meets_pre(self):
        acc_attr = _make_attr()
        pre_attr = _make_attr()
        dn_attr  = _make_attr()

        reads = {id(acc_attr): [4], id(pre_attr): [5]}
        def _read(attr, key):
            return reads.get(id(attr), [0])

        parent, _ = _make_parent(
            {"CTR.ACC": acc_attr, "CTR.PRE": pre_attr, "CTR.DN": dn_attr}
        )
        parent._read_attr.side_effect = _read
        counter = Counter(parent)  # type: ignore
        counter.increment("CTR", key=self.KEY)
        parent._write_attr.assert_any_call(dn_attr, self.KEY, [1])

    def test_ov_cleared_on_normal_increment(self):
        acc_attr = _make_attr()
        pre_attr = _make_attr()
        ov_attr  = _make_attr()

        reads = {id(acc_attr): [0], id(pre_attr): [0]}
        def _read(attr, key):
            return reads.get(id(attr), [0])

        parent, _ = _make_parent(
            {"CTR.ACC": acc_attr, "CTR.PRE": pre_attr, "CTR.OV": ov_attr}
        )
        parent._read_attr.side_effect = _read
        counter = Counter(parent)  # type: ignore
        counter.increment("CTR", key=self.KEY)
        parent._write_attr.assert_any_call(ov_attr, self.KEY, [0])


class TestCounterDecrement(unittest.TestCase):

    KEY = slice(0, 1)

    def test_logs_when_acc_missing(self):
        parent, _ = _make_parent({})
        counter = Counter(parent)  # type: ignore
        counter.decrement("CTR")
        parent._logger.assert_called()

    def test_decrements_acc_by_one(self):
        acc_attr = _make_attr()
        reads = {id(acc_attr): [5]}
        def _read(attr, key):
            return reads.get(id(attr), [0])

        parent, _ = _make_parent({"CTR.ACC": acc_attr})
        parent._read_attr.side_effect = _read
        counter = Counter(parent)  # type: ignore
        counter.decrement("CTR", key=self.KEY)
        parent._write_attr.assert_any_call(acc_attr, self.KEY, [4])

    def test_underflow_sets_un_and_resets_acc(self):
        from src.ethernetip_emulator.server.datatypes.counter import actions as _actions
        acc_attr = _make_attr()
        un_attr  = _make_attr()

        reads = {id(acc_attr): [_actions.dint.MIN]}
        def _read(attr, key):
            return reads.get(id(attr), [0])

        parent, _ = _make_parent({"CTR.ACC": acc_attr, "CTR.UN": un_attr})
        parent._read_attr.side_effect = _read
        counter = Counter(parent)  # type: ignore
        counter.decrement("CTR", key=self.KEY)

        parent._write_attr.assert_any_call(un_attr, self.KEY, [1])
        parent._write_attr.assert_any_call(acc_attr, self.KEY, [0])

    def test_dn_cleared_when_acc_drops_below_pre(self):
        acc_attr = _make_attr()
        pre_attr = _make_attr()
        dn_attr  = _make_attr()

        reads = {id(acc_attr): [5], id(pre_attr): [6]}
        def _read(attr, key):
            return reads.get(id(attr), [0])

        parent, _ = _make_parent(
            {"CTR.ACC": acc_attr, "CTR.PRE": pre_attr, "CTR.DN": dn_attr}
        )
        parent._read_attr.side_effect = _read
        counter = Counter(parent)  # type: ignore
        counter.decrement("CTR", key=self.KEY)
        parent._write_attr.assert_any_call(dn_attr, self.KEY, [0])

    def test_un_cleared_on_normal_decrement(self):
        acc_attr = _make_attr()
        un_attr  = _make_attr()

        reads = {id(acc_attr): [5]}
        def _read(attr, key):
            return reads.get(id(attr), [0])

        parent, _ = _make_parent({"CTR.ACC": acc_attr, "CTR.UN": un_attr})
        parent._read_attr.side_effect = _read
        counter = Counter(parent)  # type: ignore
        counter.decrement("CTR", key=self.KEY)
        parent._write_attr.assert_any_call(un_attr, self.KEY, [0])


class TestCounterReset(unittest.TestCase):

    KEY = slice(0, 1)

    def test_reset_writes_zero_to_all_tags(self):
        attrs = {
            "CTR.ACC": _make_attr(),
            "CTR.DN":  _make_attr(),
            "CTR.OV":  _make_attr(),
            "CTR.UN":  _make_attr(),
            "CTR.RES": _make_attr(),
        }
        parent, _ = _make_parent(attrs)
        counter = Counter(parent)  # type: ignore
        counter.reset("CTR", key=self.KEY)

        for tag, attr in attrs.items():
            with self.subTest(tag=tag):
                parent._write_attr.assert_any_call(attr, self.KEY, [0])

    def test_reset_skips_missing_attrs(self):
        acc_attr = _make_attr()
        parent, _ = _make_parent({"CTR.ACC": acc_attr})
        counter = Counter(parent)  # type: ignore
        counter.reset("CTR", key=self.KEY)
        parent._write_attr.assert_any_call(acc_attr, self.KEY, [0])


if __name__ == "__main__":
    unittest.main()
