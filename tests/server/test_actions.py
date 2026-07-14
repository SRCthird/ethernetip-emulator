# Copyright 2026 Merck KGaA, Darmstadt, Germany and/or its affiliates.
# All rights reserved

# tests/server/test_actions.py
import sys
import types
import unittest
from unittest.mock import MagicMock, patch
from typing import Any, Dict


def _install_cpppo_stubs():
    if "cpppo" in sys.modules and not isinstance(sys.modules["cpppo"], MagicMock):
        return

    class _BaseAttribute:
        def __init__(self, name: str, type_cls: Any, **kwargs: Any) -> None:
            self.name = name
            self.type_cls = type_cls
            self.kwargs = kwargs
            self._store: Dict[Any, Any] = {}

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

from src.ethernetip_emulator.server.actions import AttributeActions, TypeSpec, TypeNamespace


def _noop_logger(msg: str) -> None:
    pass


def _instant_sleep(_: float) -> None:
    pass


def _make_actions(**kwargs) -> AttributeActions:
    kwargs.setdefault("sleep_fn", _instant_sleep)
    kwargs.setdefault("logger", _noop_logger)
    return AttributeActions(**kwargs)


def _fake_attr(name: str, store: Dict | None = None) -> Any:
    attr = MagicMock()
    attr.name = name
    attr._store = store if store is not None else {}
    attr.__getitem__ = lambda self, k: self._store[k]
    attr.__setitem__ = lambda self, k, v: self._store.__setitem__(k, v)
    return attr


class TestTypeSpec(unittest.TestCase):

    def test_type_name_uppercased(self):
        ts = TypeSpec("real", 1.0)
        self.assertEqual(ts.type_name, "REAL")

    def test_default_stored(self):
        ts = TypeSpec("INT", 42)
        self.assertEqual(ts.default, 42)

    def test_iter_yields_type_name_then_default(self):
        ts = TypeSpec("BOOL", True)
        name, default = ts
        self.assertEqual(name, "BOOL")
        self.assertEqual(default, True)

    def test_repr(self):
        ts = TypeSpec("DINT", 7)
        self.assertIn("DINT", repr(ts))
        self.assertIn("7", repr(ts))

    def test_equality(self):
        self.assertEqual(TypeSpec("INT", 1), TypeSpec("INT", 1))
        self.assertNotEqual(TypeSpec("INT", 1), TypeSpec("INT", 2))
        self.assertNotEqual(TypeSpec("INT", 1), TypeSpec("DINT", 1))

    def test_equality_returns_not_implemented_for_non_typespec(self):
        result = TypeSpec("INT", 1).__eq__("other")
        self.assertIs(result, NotImplemented)

    def test_hash_consistent_with_equality(self):
        ts1 = TypeSpec("INT", 1)
        ts2 = TypeSpec("INT", 1)
        self.assertEqual(hash(ts1), hash(ts2))

    def test_hash_unhashable_default_falls_back(self):
        ts = TypeSpec("DINT", [1, 2, 3])
        self.assertIsInstance(hash(ts), int)

    def test_validator_called_when_namespace_provided(self):
        ns = TypeNamespace()
        validator = MagicMock(return_value=99)
        ns.register_type("INT", validator)
        ts = TypeSpec("INT", 5, namespace=ns)
        validator.assert_called_once_with(5)
        self.assertEqual(ts.default, 99)

    def test_validator_error_raises_value_error(self):
        ns = TypeNamespace()
        ns.register_type("INT", lambda v: (_ for _ in ()).throw(ValueError("bad")))
        with self.assertRaises(ValueError):
            TypeSpec("INT", 5, namespace=ns)

    def test_no_validator_in_namespace_stores_raw_default(self):
        ns = TypeNamespace()
        ns.register_type("INT", None)
        ts = TypeSpec("INT", 5, namespace=ns)
        self.assertEqual(ts.default, 5)

    def test_none_namespace_skips_validation(self):
        ts = TypeSpec("ANYTHING", "raw")
        self.assertEqual(ts.default, "raw")


class TestTypeNamespace(unittest.TestCase):

    def setUp(self):
        self.ns = TypeNamespace()
        self.ns.register_type("INT", int)
        self.ns.register_type("REAL", float)
        self.ns.register_type("RAW", None)

    def test_register_type_uppercases_name(self):
        self.ns.register_type("bool", bool)
        self.assertIn("BOOL", self.ns._types)

    def test_getattr_returns_factory_for_registered_type(self):
        factory = self.ns.INT
        self.assertTrue(callable(factory))

    def test_factory_returns_typespec(self):
        ts = self.ns.INT(10)
        self.assertIsInstance(ts, TypeSpec)
        self.assertEqual(ts.type_name, "INT")
        self.assertEqual(ts.default, 10)

    def test_factory_name_matches_type(self):
        self.assertEqual(self.ns.REAL.__name__, "REAL")

    def test_getattr_unknown_type_raises_attribute_error(self):
        with self.assertRaises(AttributeError):
            _ = self.ns.NONEXISTENT

    def test_repr_contains_registered_types(self):
        r = repr(self.ns)
        self.assertIn("INT", r)
        self.assertIn("REAL", r)


class TestAttributeActionsInit(unittest.TestCase):

    def test_default_construction(self):
        aa = _make_actions()
        self.assertIsNotNone(aa)
        self.assertFalse(aa._entered)
        self.assertFalse(aa._stop.is_set())

    def test_type_namespace_available_as_datatype(self):
        aa = _make_actions()
        self.assertIsInstance(aa.type, TypeNamespace)

    def test_unknown_attribute_raises_attribute_error(self):
        aa = _make_actions()
        with self.assertRaises(AttributeError):
            _ = aa.nonexistent_datatype

    def test_register_datatype_makes_it_accessible(self):
        aa = _make_actions()

        class MyDT:
            def __init__(self, actions): pass

        aa.register_datatype("mydt", MyDT)
        self.assertIsInstance(aa.mydt, MyDT)

    def test_register_datatype_registers_type_in_namespace(self):
        aa = _make_actions()

        class MyDT:
            type_validator = staticmethod(int)
            def __init__(self, actions): pass

        aa.register_datatype("mydt", MyDT)
        self.assertIn("MYDT", aa.type._types)

    def test_register_datatype_returns_self(self):
        aa = _make_actions()

        class MyDT:
            def __init__(self, actions): pass

        result = aa.register_datatype("mydt", MyDT)
        self.assertIs(result, aa)

    def test_datatype_decorator_with_string_name(self):
        aa = _make_actions()

        @aa.datatype("counter")  # type: ignore
        class Counter:
            def __init__(self, actions): pass

        self.assertIsInstance(aa.counter, Counter)

    def test_datatype_decorator_with_class_uses_lowercase_class_name(self):
        aa = _make_actions()

        @aa.datatype
        class Timer:
            def __init__(self, actions): pass

        self.assertIsInstance(aa.timer, Timer)  # type: ignore


class TestAttributeActionsContextManager(unittest.TestCase):

    def test_enter_sets_entered_flag(self):
        aa = _make_actions()
        aa.__enter__()
        self.assertTrue(aa._entered)
        aa.__exit__(None, None, None)

    def test_exit_clears_entered_flag(self):
        aa = _make_actions()
        with aa:
            pass
        self.assertFalse(aa._entered)

    def test_exit_calls_stop(self):
        aa = _make_actions()
        with patch.object(aa, "stop") as mock_stop:
            with aa:
                pass
        mock_stop.assert_called_once()

    def test_enter_flushes_pending_thunks(self):
        aa = _make_actions()
        called = []
        aa._pending.append(lambda: called.append(1))
        aa._pending.append(lambda: called.append(2))
        aa.__enter__()
        self.assertEqual(called, [1, 2])
        self.assertEqual(aa._pending, [])
        aa.__exit__(None, None, None)

    def test_enter_clears_stop_if_already_set(self):
        aa = _make_actions()
        aa._stop.set()
        aa.__enter__()
        self.assertFalse(aa._stop.is_set())
        aa.__exit__(None, None, None)

    def test_exit_joins_threads(self):
        aa = _make_actions()
        mock_thread = MagicMock()
        aa._threads.append(mock_thread)
        with aa:
            pass
        mock_thread.join.assert_called_once()

    def test_exit_clears_threads_list(self):
        aa = _make_actions()
        with aa:
            pass
        self.assertEqual(aa._threads, [])


class TestAttributeActionsLookup(unittest.TestCase):

    def test_bind_stores_weakref(self):
        aa = _make_actions()

        class FakeAttrClass:
            registry = {}

        aa.bind(FakeAttrClass)
        self.assertIs(aa._get_attr_class(), FakeAttrClass)

    def test_get_attr_class_returns_none_when_unbound(self):
        aa = _make_actions()
        self.assertIsNone(aa._get_attr_class())

    def test_lookup_returns_attr_from_registry(self):
        aa = _make_actions()
        mock_attr = MagicMock()

        class FakeAttrClass:
            registry = {"my_tag": mock_attr}

        aa.bind(FakeAttrClass)
        result = aa._lookup("my_tag")
        self.assertIs(result, mock_attr)

    def test_lookup_returns_none_for_missing_tag(self):
        aa = _make_actions()

        class FakeAttrClass:
            registry = {}

        aa.bind(FakeAttrClass)
        self.assertIsNone(aa._lookup("ghost_tag"))

    def test_lookup_returns_none_when_unbound(self):
        aa = _make_actions()
        self.assertIsNone(aa._lookup("any_tag"))


class TestAttributeActionsReadWrite(unittest.TestCase):

    def test_read_attr_returns_value_via_getitem(self):
        aa = _make_actions()
        attr = MagicMock()
        attr.__getitem__ = MagicMock(return_value=[42])
        result = aa._read_attr(attr, slice(0, 1))
        self.assertEqual(result, [42])

    def test_read_attr_falls_back_to_value_property_on_error(self):
        aa = _make_actions()
        attr = MagicMock()
        attr.__getitem__ = MagicMock(side_effect=Exception("boom"))
        attr.value = [99]
        result = aa._read_attr(attr, slice(0, 1))
        self.assertEqual(result, [99])

    def test_read_attr_returns_none_when_both_fail(self):
        log = []
        aa = _make_actions(logger=log.append)

        class BrokenAttr:
            def __getitem__(self, key):
                raise Exception("boom")

        result = aa._read_attr(BrokenAttr(), slice(0, 1))
        self.assertIsNone(result)

    def test_write_attr_uses_setitem(self):
        aa = _make_actions()
        attr = MagicMock()
        aa._write_attr(attr, slice(0, 1), [7])
        attr.__setitem__.assert_called_once_with(slice(0, 1), [7])

    def test_write_attr_falls_back_to_value_property(self):
        aa = _make_actions()

        class FallbackAttr:
            value = None
            def __setitem__(self, key, val):
                raise TypeError("no")

        attr = FallbackAttr()
        aa._write_attr(attr, slice(0, 1), [7])
        self.assertEqual(attr.value, [7])

    def test_write_attr_raises_when_no_fallback(self):
        aa = _make_actions()

        class NoFallbackAttr:
            def __setitem__(self, key, val):
                raise TypeError("no")

        with self.assertRaises(TypeError):
            aa._write_attr(NoFallbackAttr(), slice(0, 1), [7])


class TestAttributeActionsListeners(unittest.TestCase):

    def setUp(self):
        self.aa = _make_actions()

    def test_on_change_registers_callback(self):
        cb = MagicMock()
        self.aa.on_change("my_tag", cb)
        self.assertIn("my_tag", self.aa._listeners)

    def test_on_change_as_decorator(self):
        @self.aa.on_change("my_tag")
        def cb(attr, key, value):
            pass

        self.assertIn("my_tag", self.aa._listeners)

    def test_on_change_returns_self_when_callback_provided(self):
        cb = MagicMock()
        result = self.aa.on_change("my_tag", cb)
        self.assertIs(result, self.aa)

    def test_fire_listeners_calls_matching_callback(self):
        cb = MagicMock()
        key = slice(0, 1)
        self.aa.on_change("my_tag", cb, key=key)
        attr = MagicMock()
        self.aa._fire_listeners("my_tag", attr, key, 42)
        cb.assert_called_once_with(attr, key, 42)

    def test_fire_listeners_skips_wrong_key(self):
        cb = MagicMock()
        self.aa.on_change("my_tag", cb, key=slice(0, 1))
        self.aa._fire_listeners("my_tag", MagicMock(), slice(1, 2), 99)
        cb.assert_not_called()

    def test_fire_listeners_swallows_callback_exception_and_logs(self):
        log = []
        aa = _make_actions(logger=log.append)
        key = slice(0, 1)
        aa.on_change("my_tag", MagicMock(side_effect=RuntimeError("oops")), key=key)
        aa._fire_listeners("my_tag", MagicMock(), key, 1)
        self.assertTrue(any("my_tag" in m for m in log))

    def test_fire_listeners_no_entry_is_noop(self):
        self.aa._fire_listeners("ghost", MagicMock(), slice(0, 1), 0)

    def test_remove_listeners_clears_tag(self):
        self.aa.on_change("my_tag", MagicMock())
        self.aa.remove_listeners("my_tag")
        self.assertNotIn("my_tag", self.aa._listeners)

    def test_remove_listeners_unknown_tag_is_noop(self):
        self.aa.remove_listeners("nonexistent")

    def test_remove_listeners_returns_self(self):
        result = self.aa.remove_listeners("any")
        self.assertIs(result, self.aa)

    def test_on_change_defer_spawns_thread_per_call(self):
        spawned = []

        def fake_factory(**kw):
            t = MagicMock()
            spawned.append(t)
            return t

        aa = _make_actions(thread_factory=fake_factory)
        key = slice(0, 1)
        aa.on_change("my_tag", MagicMock(), key=key, defer=True)
        aa._fire_listeners("my_tag", MagicMock(), key, 1)
        self.assertEqual(len(spawned), 1)
        spawned[0].start.assert_called_once()

    def test_on_change_multiple_callbacks_all_fired(self):
        cb1, cb2 = MagicMock(), MagicMock()
        key = slice(0, 1)
        self.aa.on_change("t", cb1, key=key)
        self.aa.on_change("t", cb2, key=key)
        self.aa._fire_listeners("t", MagicMock(), key, 0)
        cb1.assert_called_once()
        cb2.assert_called_once()


class TestAttributeActionsStartWorker(unittest.TestCase):

    def test_start_worker_calls_thread_factory_with_correct_kwargs(self):
        spawned = []

        def fake_factory(**kw):
            t = MagicMock()
            spawned.append((kw, t))
            return t

        aa = _make_actions(thread_factory=fake_factory)
        fn = MagicMock()
        aa._start_worker("my_worker", fn)

        self.assertEqual(len(spawned), 1)
        kw, _ = spawned[0]
        self.assertIs(kw["target"], fn)
        self.assertEqual(kw["name"], "my_worker")
        self.assertTrue(kw["daemon"])

    def test_start_worker_starts_the_thread(self):
        mock_thread = MagicMock()
        aa = _make_actions(thread_factory=lambda **kw: mock_thread)
        aa._start_worker("w", MagicMock())
        mock_thread.start.assert_called_once()

    def test_start_worker_appends_thread_to_threads_list(self):
        mock_thread = MagicMock()
        aa = _make_actions(thread_factory=lambda **kw: mock_thread)
        aa._start_worker("w", MagicMock())
        self.assertIn(mock_thread, aa._threads)

    def test_start_worker_returns_self(self):
        aa = _make_actions(thread_factory=lambda **kw: MagicMock())
        result = aa._start_worker("w", MagicMock())
        self.assertIs(result, aa)


class TestAttributeActionsLifecycle(unittest.TestCase):

    def test_stop_sets_stop_event(self):
        aa = _make_actions()
        aa.stop()
        self.assertTrue(aa._stop.is_set())

    def test_stop_clears_listeners_when_entered(self):
        aa = _make_actions()
        aa.__enter__()
        aa.on_change("t", MagicMock())
        aa.stop()
        self.assertEqual(aa._listeners, {})
        aa.__exit__(None, None, None)

    def test_stop_does_not_clear_listeners_when_not_entered(self):
        aa = _make_actions()
        aa.on_change("t", MagicMock())
        aa.stop()
        self.assertIn("t", aa._listeners)

    def test_is_running_false_when_no_threads(self):
        aa = _make_actions()
        self.assertFalse(aa.is_running())

    def test_is_running_true_when_thread_alive(self):
        aa = _make_actions()
        t = MagicMock()
        t.is_alive.return_value = True
        aa._threads.append(t)
        self.assertTrue(aa.is_running())

    def test_join_delegates_to_threads(self):
        aa = _make_actions()
        t = MagicMock()
        aa._threads.append(t)
        aa.join(timeout=1.0)
        t.join.assert_called_once_with(timeout=1.0)


class TestAttributeActionsOnSet(unittest.TestCase):

    def _patched_aa(self, type_map=None, **kw):
        aa = _make_actions(**kw)
        self._type_map = type_map if type_map is not None else {}
        fake_tag_specs = MagicMock()
        fake_tag_specs.tag_registry.build_type_map.return_value = self._type_map
        sys.modules["src.ethernetip_emulator.server.tag_specs"] = fake_tag_specs
        return aa

    def tearDown(self):
        sys.modules.pop("src.ethernetip_emulator.server.tag_specs", None)

    def test_on_set_returns_early_when_attr_has_no_name(self):
        aa = self._patched_aa()
        attr = MagicMock(spec=[])
        aa.on_set(attr, slice(0, 1), 1)

    def test_on_set_fires_listeners(self):
        cb = MagicMock()
        key = slice(0, 1)
        aa = self._patched_aa(type_map={"my_tag": "int"})
        aa.on_change("my_tag", cb, key=key)
        attr = _fake_attr("my_tag")
        aa.on_set(attr, key, 5)
        cb.assert_called_once_with(attr, key, 5)

    def test_on_set_calls_datatype_hook_when_present(self):
        hook = MagicMock()

        class MyDT:
            def __init__(self, actions): pass
            on_set_hook = staticmethod(hook)

        aa = self._patched_aa(type_map={"my_tag": "mydt"})
        aa.register_datatype("mydt", MyDT)
        attr = _fake_attr("my_tag")
        aa.on_set(attr, slice(0, 1), 99)
        hook.assert_called_once_with("my_tag", attr, slice(0, 1), 99)

    def test_on_set_skips_hook_when_datatype_not_registered(self):
        aa = self._patched_aa(type_map={"my_tag": "unknown_dt"})
        attr = _fake_attr("my_tag")
        aa.on_set(attr, slice(0, 1), 1)

    def test_on_set_logs_and_skips_fire_when_no_type_and_no_listeners(self):
        log = []
        aa = self._patched_aa(type_map={}, logger=log.append)
        attr = _fake_attr("orphan_tag")
        aa.on_set(attr, slice(0, 1), 1)
        self.assertTrue(any("orphan_tag" in m for m in log))

    def test_on_set_fires_listeners_even_when_no_origin_type(self):
        cb = MagicMock()
        key = slice(0, 1)
        aa = self._patched_aa(type_map={})
        aa.on_change("my_tag", cb, key=key)
        attr = _fake_attr("my_tag")
        aa.on_set(attr, key, 7)
        cb.assert_called_once()

    def test_on_set_does_not_call_hook_when_on_set_hook_absent(self):
        class MyDT:
            def __init__(self, actions): pass

        aa = self._patched_aa(type_map={"my_tag": "mydt"})
        aa.register_datatype("mydt", MyDT)
        attr = _fake_attr("my_tag")
        aa.on_set(attr, slice(0, 1), 1)


if __name__ == "__main__":
    unittest.main()
