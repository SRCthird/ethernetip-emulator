# Copyright 2026 Merck KGaA, Darmstadt, Germany and/or its affiliates.
# All rights reserved

# test/server/test_actions.py
import threading
import time
import unittest
from typing import Any
from unittest.mock import MagicMock, call

from src.ethernetip_emulator.server.actions import (
    AttributeActions,
    TypeNamespace,
    TypeSpec,
)


def _make_actions(**kwargs) -> AttributeActions:
    kwargs.setdefault("sleep_fn", lambda _: None)
    return AttributeActions(**kwargs)


def _make_attr(name: str, value: Any = None) -> MagicMock:
    attr = MagicMock()
    attr.name = name
    attr.__getitem__ = MagicMock(return_value=[value])
    attr.__setitem__ = MagicMock()
    return attr



class TestTypeSpec(unittest.TestCase):

    def test_stores_type_name_uppercased(self):
        ts = TypeSpec("dint", 0)
        self.assertEqual(ts.type_name, "DINT")

    def test_stores_default(self):
        ts = TypeSpec("BOOL", True)
        self.assertEqual(ts.default, True)

    def test_iter_yields_type_name_and_default(self):
        ts = TypeSpec("DINT", 42)
        name, default = ts
        self.assertEqual(name, "DINT")
        self.assertEqual(default, 42)

    def test_repr(self):
        ts = TypeSpec("DINT", 7)
        self.assertIn("DINT", repr(ts))
        self.assertIn("7", repr(ts))

    def test_equality(self):
        self.assertEqual(TypeSpec("DINT", 1), TypeSpec("dint", 1))
        self.assertNotEqual(TypeSpec("DINT", 1), TypeSpec("DINT", 2))

    def test_not_equal_to_non_typespec(self):
        ts = TypeSpec("DINT", 1)
        self.assertIs(ts.__eq__("other"), NotImplemented)

    def test_hashable(self):
        ts = TypeSpec("DINT", 5)
        self.assertIsInstance(hash(ts), int)

    def test_hash_consistent_with_equality(self):
        a = TypeSpec("DINT", 5)
        b = TypeSpec("dint", 5)
        self.assertEqual(hash(a), hash(b))

    def test_validator_called_when_namespace_provided(self):
        ns = TypeNamespace()
        ns.register_type("INT", lambda v: int(v) * 2)
        ts = TypeSpec("INT", 3, ns)
        self.assertEqual(ts.default, 6)

    def test_validator_rejection_raises_value_error(self):
        ns = TypeNamespace()
        ns.register_type("INT", lambda v: (_ for _ in ()).throw(TypeError("bad")))
        with self.assertRaises(ValueError):
            TypeSpec("INT", "bad", ns)

    def test_unhashable_default_falls_back_to_id_hash(self):
        ts = TypeSpec("LIST", [1, 2, 3])
        self.assertIsInstance(hash(ts), int)


class TestTypeNamespace(unittest.TestCase):

    def test_register_and_access_type(self):
        ns = TypeNamespace()
        ns.register_type("DINT")
        factory = ns.DINT
        self.assertTrue(callable(factory))

    def test_factory_returns_typespec(self):
        ns = TypeNamespace()
        ns.register_type("DINT")
        ts = ns.DINT(99)
        self.assertIsInstance(ts, TypeSpec)
        self.assertEqual(ts.type_name, "DINT")
        self.assertEqual(ts.default, 99)

    def test_factory_name_is_uppercased(self):
        ns = TypeNamespace()
        ns.register_type("dint")
        factory = ns.DINT
        self.assertEqual(factory.__name__, "DINT")

    def test_unknown_type_raises_attribute_error(self):
        ns = TypeNamespace()
        with self.assertRaises(AttributeError):
            _ = ns.UNKNOWN

    def test_register_type_case_insensitive(self):
        ns = TypeNamespace()
        ns.register_type("bool")
        _ = ns.BOOL  # should not raise

    def test_repr_lists_registered_types(self):
        ns = TypeNamespace()
        ns.register_type("DINT")
        ns.register_type("BOOL")
        r = repr(ns)
        self.assertIn("BOOL", r)
        self.assertIn("DINT", r)

    def test_validator_is_called_via_factory(self):
        ns = TypeNamespace()
        ns.register_type("UINT", lambda v: abs(int(v)))
        ts = ns.UINT(-5)
        self.assertEqual(ts.default, 5)


class TestAttributeActionsInit(unittest.TestCase):

    def test_default_construction(self):
        aa = AttributeActions()
        self.assertFalse(aa._entered)
        self.assertFalse(aa._stop.is_set())
        self.assertEqual(aa._threads, [])
        self.assertEqual(aa._pending, [])

    def test_type_namespace_is_registered(self):
        aa = _make_actions()
        self.assertIsInstance(aa.type, TypeNamespace)

    def test_custom_sleep_fn_stored(self):
        sentinel = object()
        aa = AttributeActions(sleep_fn=lambda _: sentinel)
        self.assertTrue(callable(aa._sleep))

    def test_custom_logger_stored(self):
        log = []
        aa = AttributeActions(logger=log.append)
        aa._logger("hello")
        self.assertEqual(log, ["hello"])


class TestRegisterDatatype(unittest.TestCase):

    def setUp(self):
        self.aa = _make_actions()

    def test_register_datatype_by_name(self):
        class Foo:
            def __init__(self, parent):
                self.parent = parent

        self.aa.register_datatype("foo", Foo)
        self.assertIsInstance(self.aa.foo, Foo)

    def test_register_datatype_registers_type(self):
        class Bar:
            def __init__(self, parent):
                pass

            @staticmethod
            def type_validator(v):
                return int(v)

        self.aa.register_datatype("bar", Bar)
        ts = self.aa.type.BAR(5)
        self.assertEqual(ts.default, 5)

    def test_datatype_decorator_uses_class_name(self):
        @self.aa.datatype
        class mydt:
            def __init__(self, parent):
                pass

        self.assertIsInstance(self.aa.mydt, mydt)

    def test_datatype_decorator_with_explicit_name(self):
        @self.aa.datatype("custom")
        class Whatever:
            def __init__(self, parent):
                pass

        self.assertIsInstance(self.aa.custom, Whatever)

    def test_unknown_datatype_raises_attribute_error(self):
        aa = _make_actions()
        with self.assertRaises(AttributeError):
            _ = aa.nonexistent


class TestContextManager(unittest.TestCase):

    def setUp(self):
        self.aa = _make_actions()

    def test_enter_sets_entered(self):
        with self.aa:
            self.assertTrue(self.aa._entered)

    def test_exit_clears_entered(self):
        with self.aa:
            pass
        self.assertFalse(self.aa._entered)

    def test_enter_flushes_pending(self):
        called = []
        self.aa._pending.append(lambda: called.append(1))
        self.aa._pending.append(lambda: called.append(2))
        with self.aa:
            self.assertEqual(called, [1, 2])
            self.assertEqual(self.aa._pending, [])

    def test_exit_stops_worker_threads(self):
        barrier = threading.Barrier(2)

        def slow_worker():
            barrier.wait()
            time.sleep(5)

        with self.aa:
            t = threading.Thread(target=slow_worker, daemon=True)
            t.start()
            self.aa._threads.append(t)
            barrier.wait()
        self.assertEqual(self.aa._threads, [])

    def test_exit_clears_stop_event(self):
        with self.aa:
            pass
        self.assertFalse(self.aa._stop.is_set())

    def test_reenter_after_exit_clears_stop_and_works(self):
        with self.aa:
            pass
        called = []
        with self.aa:
            called.append(True)
        self.assertTrue(called)

    def test_enter_clears_stop_if_already_set(self):
        self.aa._stop.set()
        with self.aa:
            self.assertFalse(self.aa._stop.is_set())

    def test_enter_returns_self(self):
        with self.aa as ctx:
            self.assertIs(ctx, self.aa)

    def test_exit_clears_listeners(self):
        self.aa._listeners["TAG"] = [(lambda a, k, v: None, slice(0, 1))]
        with self.aa:
            pass
        self.assertEqual(self.aa._listeners, {})


class TestBind(unittest.TestCase):

    def test_bind_stores_weak_ref(self):
        aa = _make_actions()

        class Fake:
            pass

        aa.bind(Fake)
        self.assertIs(aa._get_attr_class(), Fake)

    def test_bind_returns_self(self):
        aa = _make_actions()

        class Fake:
            pass

        result = aa.bind(Fake)
        self.assertIs(result, aa)

    def test_get_attr_class_returns_none_when_unbound(self):
        aa = _make_actions()
        self.assertIsNone(aa._get_attr_class())


class TestStartWorker(unittest.TestCase):

    def test_start_worker_runs_function(self):
        done = threading.Event()
        aa = _make_actions()
        aa._start_worker("w1", lambda: done.set())
        self.assertTrue(done.wait(timeout=2.0))

    def test_start_worker_appends_to_threads(self):
        aa = _make_actions()
        aa._start_worker("w2", lambda: time.sleep(0.05))
        self.assertEqual(len(aa._threads), 1)

    def test_custom_thread_factory_is_used(self):
        created = []

        def factory(**kw):
            t = threading.Thread(**kw)
            created.append(t)
            return t

        aa = _make_actions(thread_factory=factory)
        aa._start_worker("w3", lambda: None)
        self.assertEqual(len(created), 1)


class TestOnChange(unittest.TestCase):

    def setUp(self):
        self.aa = _make_actions()

    def test_on_change_registers_callback(self):
        cb = MagicMock()
        self.aa.on_change("TAG1", cb)
        self.assertIn("TAG1", self.aa._listeners)
        self.assertEqual(len(self.aa._listeners["TAG1"]), 1)

    def test_on_change_returns_self(self):
        result = self.aa.on_change("TAG1", MagicMock())
        self.assertIs(result, self.aa)

    def test_on_change_decorator_syntax(self):
        decorator = self.aa.on_change("TAG2")
        self.assertTrue(callable(decorator))

        @decorator
        def my_cb(attr, key, value):
            pass

        self.assertIn("TAG2", self.aa._listeners)

    def test_on_change_decorator_returns_original_fn(self):
        @self.aa.on_change("TAG3")
        def my_cb(attr, key, value):
            pass

        self.assertTrue(callable(my_cb))
        self.assertEqual(my_cb.__name__, "my_cb")

    def test_multiple_callbacks_same_tag(self):
        cb1, cb2 = MagicMock(), MagicMock()
        self.aa.on_change("TAG4", cb1)
        self.aa.on_change("TAG4", cb2)
        self.assertEqual(len(self.aa._listeners["TAG4"]), 2)

    def test_on_change_defer_wraps_callback(self):
        called_threads = []

        def cb(attr, key, value):
            called_threads.append(threading.current_thread())

        self.aa.on_change("DTAG", cb, defer=True)
        attr = _make_attr("DTAG", True)
        self.aa._fire_listeners("DTAG", attr, slice(0, 1), [True])
        time.sleep(0.1)
        self.assertTrue(len(called_threads) > 0)
        self.assertIsNot(called_threads[0], threading.main_thread())


class TestFireListeners(unittest.TestCase):

    def setUp(self):
        self.aa = _make_actions()

    def test_fire_calls_registered_callback(self):
        cb = MagicMock()
        self.aa.on_change("T", cb)
        attr = _make_attr("T", 1)
        self.aa._fire_listeners("T", attr, slice(0, 1), [1])
        cb.assert_called_once()

    def test_fire_skips_mismatched_key_filter(self):
        cb = MagicMock()
        self.aa.on_change("T", cb, key=slice(1, 2))
        attr = _make_attr("T", 1)
        self.aa._fire_listeners("T", attr, slice(0, 1), [1])
        cb.assert_not_called()

    def test_fire_matches_correct_key_filter(self):
        cb = MagicMock()
        self.aa.on_change("T", cb, key=slice(0, 1))
        attr = _make_attr("T", 1)
        self.aa._fire_listeners("T", attr, slice(0, 1), [1])
        cb.assert_called_once()

    def test_fire_logs_on_listener_exception(self):
        log = []
        aa = AttributeActions(logger=log.append)

        def bad_cb(attr, key, value):
            raise RuntimeError("boom")

        aa.on_change("T", bad_cb)
        attr = _make_attr("T", 1)
        aa._fire_listeners("T", attr, slice(0, 1), [1])
        self.assertTrue(any("boom" in msg for msg in log))

    def test_fire_no_listeners_is_safe(self):
        self.aa._fire_listeners("UNKNOWN", MagicMock(), slice(0, 1), [0])

    def test_fire_passes_correct_args_to_callback(self):
        received = []

        def cb(attr, key, value):
            received.append((attr, key, value))

        self.aa.on_change("T", cb)
        attr = _make_attr("T", 99)
        self.aa._fire_listeners("T", attr, slice(0, 1), [99])
        self.assertEqual(len(received), 1)
        self.assertIs(received[0][0], attr)
        self.assertEqual(received[0][2], [99])


class TestRemoveListeners(unittest.TestCase):

    def test_remove_clears_tag_listeners(self):
        aa = _make_actions()
        aa.on_change("T", MagicMock())
        aa.remove_listeners("T")
        self.assertNotIn("T", aa._listeners)

    def test_remove_nonexistent_tag_is_safe(self):
        aa = _make_actions()
        aa.remove_listeners("NOTHING")

    def test_remove_returns_self(self):
        aa = _make_actions()
        result = aa.remove_listeners("X")
        self.assertIs(result, aa)


class TestLookup(unittest.TestCase):

    def test_lookup_returns_attr_when_found(self):
        aa = _make_actions()
        attr = _make_attr("TAG", 1)

        class FakeDevice:
            registry = {"TAG": attr}

        aa.bind(FakeDevice)
        result = aa._lookup("TAG")
        self.assertIs(result, attr)

    def test_lookup_returns_none_when_attr_class_is_none(self):
        log = []
        aa = AttributeActions(logger=log.append)
        result = aa._lookup("TAG")
        self.assertIsNone(result)
        self.assertTrue(any("attr_class is None" in m for m in log))

    def test_lookup_returns_none_when_tag_not_in_registry(self):
        log = []
        aa = AttributeActions(logger=log.append)

        class FakeDevice:
            registry = {}

        aa.bind(FakeDevice)
        result = aa._lookup("MISSING")
        self.assertIsNone(result)
        self.assertTrue(any("attr is None" in m for m in log))

    def test_lookup_uses_registry_attribute(self):
        log = []
        aa = AttributeActions(logger=log.append)

        class FakeDevice:
            pass

        aa.bind(FakeDevice)
        result = aa._lookup("TAG")
        self.assertIsNone(result)
        self.assertTrue(any("attr is None" in m for m in log))


class TestStopAndJoin(unittest.TestCase):

    def test_stop_sets_stop_event(self):
        aa = _make_actions()
        aa.stop()
        self.assertTrue(aa._stop.is_set())

    def test_stop_clears_listeners_when_entered(self):
        aa = _make_actions()
        aa._entered = True
        aa._listeners["T"] = [(MagicMock(), slice(0, 1))]
        aa.stop()
        self.assertEqual(aa._listeners, {})

    def test_stop_does_not_clear_listeners_when_not_entered(self):
        aa = _make_actions()
        aa._listeners["T"] = [(MagicMock(), slice(0, 1))]
        aa.stop()
        self.assertIn("T", aa._listeners)

    def test_join_waits_for_threads(self):
        aa = _make_actions()
        done = threading.Event()

        def worker():
            time.sleep(0.05)
            done.set()

        t = threading.Thread(target=worker, daemon=True)
        t.start()
        aa._threads.append(t)
        aa.join(timeout=2.0)
        self.assertTrue(done.is_set())

    def test_is_running_true_while_thread_alive(self):
        aa = _make_actions()
        ready = threading.Event()
        stop = threading.Event()

        def worker():
            ready.set()
            stop.wait()

        t = threading.Thread(target=worker, daemon=True)
        t.start()
        aa._threads.append(t)
        ready.wait()
        self.assertTrue(aa.is_running())
        stop.set()
        t.join()
        self.assertFalse(aa.is_running())


class TestReadWriteAttr(unittest.TestCase):

    def setUp(self):
        self.aa = _make_actions()

    def test_read_attr_uses_slice(self):
        attr = MagicMock()
        attr.__getitem__ = MagicMock(return_value=[42])
        result = self.aa._read_attr(attr, slice(0, 1))
        self.assertEqual(result, [42])

    def test_read_attr_falls_back_to_value_property(self):
        attr = MagicMock()
        attr.__getitem__ = MagicMock(side_effect=TypeError("no slice"))
        attr.value = [7]
        result = self.aa._read_attr(attr)
        self.assertEqual(result, [7])

    def test_read_attr_returns_none_on_failure(self):
        log = []
        aa = AttributeActions(logger=log.append)
        attr = MagicMock(spec=[])
        result = aa._read_attr(attr)
        self.assertIsNone(result)
        self.assertTrue(len(log) > 0)

    def test_write_attr_uses_setitem(self):
        attr = MagicMock()
        self.aa._write_attr(attr, slice(0, 1), [99])
        attr.__setitem__.assert_called_once_with(slice(0, 1), [99])

    def test_write_attr_falls_back_to_value_property(self):
        attr = MagicMock()
        attr.__setitem__ = MagicMock(side_effect=TypeError("no setitem"))
        self.aa._write_attr(attr, slice(0, 1), [55])
        self.assertEqual(attr.value, [55])

    def test_write_attr_raises_when_no_fallback(self):
        attr = MagicMock(spec=["__setitem__"])
        attr.__setitem__ = MagicMock(side_effect=TypeError("bad"))
        with self.assertRaises(TypeError):
            self.aa._write_attr(attr, slice(0, 1), [1])


class TestOnSet(unittest.TestCase):

    def setUp(self):
        self.aa = _make_actions()

    def _bind_registry(self, tags: dict) -> None:
        cls = type("FakeDevice", (), {"registry": tags})
        self.aa.bind(cls)

    def test_on_set_fires_listener(self):
        cb = MagicMock()
        self.aa.on_change("TAG", cb)
        attr = _make_attr("TAG", 1)
        self._bind_registry({"TAG": attr})

        self.aa._fire_listeners("TAG", attr, slice(0, 1), [1])
        cb.assert_called_once()

    def test_on_set_skips_when_attr_name_is_none(self):
        attr = MagicMock()
        attr.name = None
        self.aa.on_set(attr, slice(0, 1), [0])

    def test_on_set_logs_when_tag_not_in_registry_and_no_listeners(self):
        log = []
        aa = AttributeActions(logger=log.append)
        attr = _make_attr("UNKNOWN_TAG", 0)

        class FakeDevice:
            registry = {}

        aa.bind(FakeDevice)

        from unittest.mock import patch
        from src.ethernetip_emulator.server import tag_specs

        with patch.object(tag_specs.tag_registry, "build_type_map", return_value={}):
            aa.on_set(attr, slice(0, 1), [0])

        self.assertTrue(any("UNKNOWN_TAG" in m for m in log))

    def test_on_set_calls_on_set_hook_on_datatype(self):
        hook_calls = []

        class FakeDT:
            def __init__(self, parent):
                pass

            def on_set_hook(self, tag_name, attr, key, value):
                hook_calls.append(tag_name)

        self.aa.register_datatype("fakedt", FakeDT)
        attr = _make_attr("MYREG", 1)

        class FakeDevice:
            registry = {"MYREG": attr}

        self.aa.bind(FakeDevice)

        from unittest.mock import patch
        from src.ethernetip_emulator.server import tag_specs

        with patch.object(
            tag_specs.tag_registry,
            "build_type_map",
            return_value={"MYREG": "FAKEDT"},
        ):
            self.aa.on_set(attr, slice(0, 1), [1])

        self.assertIn("MYREG", hook_calls)


if __name__ == "__main__":
    unittest.main()
