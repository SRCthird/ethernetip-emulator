# Copyright 2026 Merck KGaA, Darmstadt, Germany and/or its affiliates.
# All rights reserved

# tests/server/test_tag_specs.py
import threading
import unittest
from unittest.mock import MagicMock

from src.ethernetip_emulator.server.tag_specs import TagRegistry, tag_registry

def _make_spec(type_name: str, default=None):
    spec = MagicMock()
    spec.type_name = type_name.upper()
    spec.default = default
    return spec


def _entry(name: str, type_name: str, default=None):
    return (name, _make_spec(type_name, default))


class TestNormalise(unittest.TestCase):

    def test_returns_name_type_default_triple(self):
        spec = _make_spec("INT", 42)
        result = TagRegistry._normalise(("my_tag", spec))
        self.assertEqual(result, ("my_tag", "INT", 42))

    def test_uppercases_type_name(self):
        spec = _make_spec("real", 1.0)
        name, type_name, _ = TagRegistry._normalise(("t", spec))
        self.assertEqual(type_name, "REAL")

    def test_raises_value_error_for_wrong_tuple_length(self):
        with self.assertRaises(ValueError):
            TagRegistry._normalise(("a", _make_spec("INT"), "extra"))

    def test_raises_value_error_for_single_element(self):
        with self.assertRaises(ValueError):
            TagRegistry._normalise(("only_name",))

    def test_raises_type_error_when_spec_has_no_type_name(self):
        bad_spec = object()
        with self.assertRaises(TypeError):
            TagRegistry._normalise(("t", bad_spec))

    def test_none_default_preserved(self):
        spec = _make_spec("BOOL", None)
        _, _, default = TagRegistry._normalise(("t", spec))
        self.assertIsNone(default)

    def test_list_default_preserved(self):
        spec = _make_spec("DINT", [1, 2, 3])
        _, _, default = TagRegistry._normalise(("t", spec))
        self.assertEqual(default, [1, 2, 3])


class TestRegister(unittest.TestCase):

    def setUp(self):
        self.reg = TagRegistry()

    def test_register_function_adds_entries(self):
        @self.reg.register
        def _():
            return [_entry("tag_a", "INT", 1)]

        self.assertIn(("tag_a", "INT", 1), self.reg.build())

    def test_register_returns_original_function(self):
        def my_fn():
            return [_entry("x", "INT")]

        result = self.reg.register(my_fn)
        self.assertIs(result, my_fn)

    def test_register_with_prefix_prepends_prefix(self):
        @self.reg.register("ns")
        def _():
            return [_entry("tag_b", "REAL", 2.0)]

        names = [n for n, _, _ in self.reg.build()]
        self.assertIn("ns.tag_b", names)

    def test_register_with_prefix_returns_original_function(self):
        def my_fn():
            return [_entry("x", "INT")]

        result = self.reg.register("pfx")(my_fn)
        self.assertIs(result, my_fn)

    def test_register_multiple_functions_all_included(self):
        @self.reg.register
        def _a():
            return [_entry("a1", "INT"), _entry("a2", "INT")]

        @self.reg.register
        def _b():
            return [_entry("b1", "REAL")]

        names = {n for n, _, _ in self.reg.build()}
        self.assertIn("a1", names)
        self.assertIn("a2", names)
        self.assertIn("b1", names)

    def test_register_invalidates_cache(self):
        @self.reg.register
        def _first():
            return [_entry("t1", "INT")]

        _ = self.reg.build()

        @self.reg.register
        def _second():
            return [_entry("t2", "INT")]

        names = {n for n, _, _ in self.reg.build()}
        self.assertIn("t2", names)

    def test_register_raises_on_bad_entry(self):
        with self.assertRaises((ValueError, TypeError)):
            @self.reg.register
            def _():
                return [("only_name",)]


class TestExpander(unittest.TestCase):

    def setUp(self):
        self.reg = TagRegistry()

    def _simple_expander(self, tag_name, default):
        """Expand COMPLEX → two INT sub-tags."""
        return [
            _entry(f"{tag_name}.x", "INT", 0),
            _entry(f"{tag_name}.y", "INT", 0),
        ]

    def test_expander_decorator_registers_expander(self):
        @self.reg.expander("COMPLEX")
        def _(name, default):
            return self._simple_expander(name, default)

        self.assertIn("COMPLEX", self.reg._expanders)

    def test_expander_decorator_returns_original_function(self):
        def my_exp(name, default):
            return []

        result = self.reg.expander("FOO")(my_exp)
        self.assertIs(result, my_exp)

    def test_expander_uppercases_type_key(self):
        @self.reg.expander("complex")
        def _(name, default):
            return []

        self.assertIn("COMPLEX", self.reg._expanders)

    def test_expander_invalidates_cache(self):
        @self.reg.register
        def _():
            return [_entry("t", "INT")]

        _ = self.reg.build()

        @self.reg.expander("INT")
        def _(name, default):
            return [_entry(f"{name}.v", "DINT")]

        result = self.reg.build()
        names = {n for n, _, _ in result}
        self.assertIn("t.v", names)


class TestExpandOne(unittest.TestCase):

    def setUp(self):
        self.reg = TagRegistry()

    def test_no_expander_returns_single_primitive_entry(self):
        result = self.reg._expand_one("tag", "INT", 5, "INT")
        self.assertEqual(result, [("tag", "INT", 5, "INT")])

    def test_expander_applied_recursively(self):
        @self.reg.expander("PAIR")
        def _(name, default):
            return [_entry(f"{name}.a", "INT"), _entry(f"{name}.b", "INT")]

        result = self.reg._expand_one("t", "PAIR", None, "PAIR")
        names = [r[0] for r in result]
        self.assertIn("t.a", names)
        self.assertIn("t.b", names)

    def test_cycle_detection_raises_runtime_error(self):
        @self.reg.expander("LOOP")
        def _(name, default):
            return [_entry(f"{name}.child", "LOOP")]

        with self.assertRaises(RuntimeError):
            self.reg._expand_one("t", "LOOP", None, "LOOP")

    def test_origin_preserved_in_result(self):
        result = self.reg._expand_one("tag", "INT", 0, "MY_ORIGIN")
        self.assertEqual(result[0][3], "MY_ORIGIN")


class TestBuild(unittest.TestCase):

    def setUp(self):
        self.reg = TagRegistry()

    def _populate(self, *entries):
        @self.reg.register
        def _():
            return list(entries)

    def test_build_returns_list_of_triples(self):
        self._populate(_entry("t", "INT", 7))
        result = self.reg.build()
        self.assertIsInstance(result, list)
        self.assertEqual(result[0], ("t", "INT", 7))

    def test_build_is_cached(self):
        self._populate(_entry("t", "INT"))
        self.reg.build()
        first_built = self.reg._built
        self.reg.build()
        self.assertIs(self.reg._built, first_built)

    def test_build_returns_copy_not_internal_list(self):
        self._populate(_entry("t", "INT"))
        result = self.reg.build()
        result.clear()
        self.assertGreater(len(self.reg.build()), 0)

    def test_build_raises_on_duplicate_tag_name(self):
        self._populate(_entry("dup", "INT"), _entry("dup", "REAL"))
        with self.assertRaises(ValueError):
            self.reg.build()

    def test_build_empty_registry_returns_empty_list(self):
        self.assertEqual(self.reg.build(), [])

    def test_build_expands_types_via_expander(self):
        @self.reg.expander("VEC2")
        def _(name, default):
            return [_entry(f"{name}.x", "INT"), _entry(f"{name}.y", "INT")]

        self._populate(_entry("pos", "VEC2"))
        names = {n for n, _, _ in self.reg.build()}
        self.assertIn("pos.x", names)
        self.assertIn("pos.y", names)
        self.assertNotIn("pos", names)

    def test_build_thread_safety(self):
        for i in range(20):
            spec = _make_spec("INT", i)
            self.reg._raw.append((f"tag_{i}", "INT", i))
        self.reg.invalidate()

        errors = []
        results = []

        def worker():
            try:
                results.append(self.reg.build())
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(errors, [])
        for r in results:
            self.assertEqual(len(r), 20)


class TestBuildTypeMap(unittest.TestCase):

    def setUp(self):
        self.reg = TagRegistry()

    def test_returns_dict_mapping_name_to_origin_type(self):
        @self.reg.register
        def _():
            return [_entry("t", "INT")]

        tm = self.reg.build_type_map()
        self.assertEqual(tm.get("t"), "INT")

    def test_returns_copy_not_internal_dict(self):
        @self.reg.register
        def _():
            return [_entry("t", "INT")]

        tm = self.reg.build_type_map()
        tm["injected"] = "FAKE"
        self.assertNotIn("injected", self.reg.build_type_map())

    def test_expanded_tags_use_origin_type(self):
        @self.reg.expander("VEC2")
        def _(name, default):
            return [_entry(f"{name}.x", "INT"), _entry(f"{name}.y", "INT")]

        @self.reg.register
        def _():
            return [_entry("pos", "VEC2")]

        tm = self.reg.build_type_map()
        self.assertEqual(tm.get("pos.x"), "VEC2")
        self.assertEqual(tm.get("pos.y"), "VEC2")


class TestInvalidate(unittest.TestCase):

    def setUp(self):
        self.reg = TagRegistry()

    def test_invalidate_clears_built(self):
        @self.reg.register
        def _():
            return [_entry("t", "INT")]

        self.reg.build()
        self.assertIsNotNone(self.reg._built)
        self.reg.invalidate()
        self.assertIsNone(self.reg._built)

    def test_invalidate_clears_type_map(self):
        @self.reg.register
        def _():
            return [_entry("t", "INT")]

        self.reg.build_type_map()
        self.assertIsNotNone(self.reg._type_map)
        self.reg.invalidate()
        self.assertIsNone(self.reg._type_map)

    def test_invalidate_type_map_is_alias_for_invalidate(self):
        self.assertIs(self.reg.invalidate_type_map.__func__, self.reg.invalidate.__func__)

    def test_rebuild_after_invalidate_picks_up_new_raw_entries(self):
        @self.reg.register
        def _():
            return [_entry("t1", "INT")]

        self.reg.build()
        self.reg._raw.append(("t2", "INT", 0))
        self.reg.invalidate()

        names = {n for n, _, _ in self.reg.build()}
        self.assertIn("t2", names)


class TestBuildArgv(unittest.TestCase):

    def setUp(self):
        self.reg = TagRegistry()

    def test_returns_list_of_name_eq_type_strings(self):
        @self.reg.register
        def _():
            return [_entry("my_tag", "INT")]

        argv = self.reg.build_argv()
        self.assertIn("my_tag=INT", argv)

    def test_base_args_prepended(self):
        @self.reg.register
        def _():
            return [_entry("t", "INT")]

        argv = self.reg.build_argv(base_args=["--server", "localhost"])
        self.assertEqual(argv[0], "--server")
        self.assertEqual(argv[1], "localhost")
        self.assertIn("t=INT", argv)

    def test_no_base_args_defaults_to_empty(self):
        @self.reg.register
        def _():
            return [_entry("t", "INT")]

        argv = self.reg.build_argv()
        self.assertFalse(any(a.startswith("-") for a in argv))

    def test_empty_registry_returns_only_base_args(self):
        argv = self.reg.build_argv(base_args=["--flag"])
        self.assertEqual(argv, ["--flag"])


class TestProperties(unittest.TestCase):

    def setUp(self):
        self.reg = TagRegistry()

    def test_specs_property_equals_build(self):
        @self.reg.register
        def _():
            return [_entry("t", "INT", 1)]

        self.assertEqual(self.reg.specs, self.reg.build())

    def test_argv_property_prepends_print_flag(self):
        @self.reg.register
        def _():
            return [_entry("t", "INT")]

        self.assertIn("--print", self.reg.argv)
        self.assertIn("t=INT", self.reg.argv)


class TestModuleLevelSingleton(unittest.TestCase):

    def test_is_tag_registry_instance(self):
        self.assertIsInstance(tag_registry, TagRegistry)


if __name__ == "__main__":
    unittest.main()
