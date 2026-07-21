# Copyright 2026 Merck KGaA, Darmstadt, Germany and/or its affiliates.
# All rights reserved

# test/server/test_tag_specs.py
import threading
import unittest
from unittest.mock import MagicMock

from src.ethernetip_emulator.server.tag_specs import TagRegistry
from tests.server import next_port


def _make_spec(type_name: str, default=None):
    spec = MagicMock()
    spec.type_name = type_name
    spec.default = default
    return spec


class TestNormalise(unittest.TestCase):
    def test_valid_entry_returns_tuple(self):
        spec = _make_spec("INT", 0)
        result = TagRegistry._normalise(("my_tag", spec))
        self.assertEqual(result, ("my_tag", "INT", 0))

    def test_valid_entry_none_default(self):
        spec = _make_spec("REAL", None)
        result = TagRegistry._normalise(("t", spec))
        self.assertEqual(result, ("t", "REAL", None))

    def test_wrong_tuple_length_raises_value_error(self):
        spec = _make_spec("INT")
        with self.assertRaises(ValueError):
            TagRegistry._normalise(("a", spec, "extra"))

    def test_single_element_raises_value_error(self):
        with self.assertRaises(ValueError):
            TagRegistry._normalise(("only_name",))

    def test_non_typespec_second_element_raises_type_error(self):
        with self.assertRaises(TypeError):
            TagRegistry._normalise(("tag", "not_a_typespec"))

    def test_none_second_element_raises_type_error(self):
        with self.assertRaises(TypeError):
            TagRegistry._normalise(("tag", None))


class TestRegister(unittest.TestCase):
    def setUp(self):
        self.reg = TagRegistry()

    def test_plain_decorator_adds_tags(self):
        @self.reg.register
        def _():
            return [("t1", _make_spec("INT", 1)), ("t2", _make_spec("REAL", 2.0))]

        built = self.reg.build()
        names = [n for n, _, _ in built]
        self.assertIn("t1", names)
        self.assertIn("t2", names)

    def test_plain_decorator_returns_fn(self):
        def my_fn():
            return [("t", _make_spec("INT", 0))]

        result = self.reg.register(my_fn)
        self.assertIs(result, my_fn)

    def test_prefix_decorator_prepends_prefix(self):
        @self.reg.register("ns")
        def _():
            return [("tag", _make_spec("INT", 5))]

        built = self.reg.build()
        names = [n for n, _, _ in built]
        self.assertIn("ns.tag", names)
        self.assertNotIn("tag", names)

    def test_prefix_decorator_returns_fn(self):
        def my_fn():
            return [("t", _make_spec("INT", 0))]

        result = self.reg.register("pfx")(my_fn)
        self.assertIs(result, my_fn)

    def test_register_invalidates_cache(self):
        @self.reg.register
        def _():
            return [("first", _make_spec("INT", 0))]

        self.reg.build()
        self.assertIsNotNone(self.reg._built)

        @self.reg.register
        def __():
            return [("second", _make_spec("REAL", 1.0))]

        self.assertIsNone(self.reg._built)

    def test_multiple_registers_accumulate(self):
        @self.reg.register
        def _():
            return [("a", _make_spec("INT", 0))]

        @self.reg.register
        def __():
            return [("b", _make_spec("INT", 1))]

        names = [n for n, _, _ in self.reg.build()]
        self.assertIn("a", names)
        self.assertIn("b", names)


class TestExpander(unittest.TestCase):
    def setUp(self):
        self.reg = TagRegistry()

    def test_expander_registered_under_uppercase_key(self):
        @self.reg.expander("compound")
        def _expand(name, default):
            return []

        self.assertIn("COMPOUND", self.reg._expanders)

    def test_expander_returns_fn(self):
        def my_expand(name, default):
            return []

        result = self.reg.expander("T")(my_expand)
        self.assertIs(result, my_expand)

    def test_expander_invalidates_cache(self):
        @self.reg.register
        def _():
            return [("t", _make_spec("INT", 0))]

        self.reg.build()
        self.assertIsNotNone(self.reg._built)

        @self.reg.expander("INT")
        def _expand(name, default):
            return [("t", _make_spec("INT", 0))]

        self.assertIsNone(self.reg._built)

    def test_expander_expands_type(self):
        @self.reg.expander("COMPOUND")
        def _expand(name, default):
            return [
                (f"{name}.x", _make_spec("INT", 0)),
                (f"{name}.y", _make_spec("REAL", 0.0)),
            ]

        @self.reg.register
        def _():
            return [("pos", _make_spec("COMPOUND", None))]

        names = [n for n, _, _ in self.reg.build()]
        self.assertIn("pos.x", names)
        self.assertIn("pos.y", names)
        self.assertNotIn("pos", names)

    def test_expand_one_no_expander_returns_self(self):
        result = self.reg._expand_one("t", "INT", 0, "INT")
        self.assertEqual(result, [("t", "INT", 0, "INT")])

    def test_expand_one_cycle_raises_runtime_error(self):
        @self.reg.expander("CYCLIC")
        def _expand(name, default):
            return [(name, _make_spec("CYCLIC", None))]

        with self.assertRaises(RuntimeError) as ctx:
            self.reg._expand_one("t", "CYCLIC", None, "CYCLIC")
        self.assertIn("cycle detected", str(ctx.exception))

    def test_expander_nested_expansion(self):
        @self.reg.expander("OUTER")
        def _outer(name, default):
            return [(f"{name}.inner", _make_spec("INNER", None))]

        @self.reg.expander("INNER")
        def _inner(name, default):
            return [(f"{name}.val", _make_spec("INT", 0))]

        @self.reg.register
        def _():
            return [("root", _make_spec("OUTER", None))]

        names = [n for n, _, _ in self.reg.build()]
        self.assertIn("root.inner.val", names)


class TestBuild(unittest.TestCase):
    def setUp(self):
        self.reg = TagRegistry()

    def test_build_empty_registry(self):
        self.assertEqual(self.reg.build(), [])

    def test_build_returns_list_of_3_tuples(self):
        @self.reg.register
        def _():
            return [("t", _make_spec("INT", 7))]

        result = self.reg.build()
        self.assertEqual(len(result), 1)
        name, type_spec, default = result[0]
        self.assertEqual(name, "t")
        self.assertEqual(type_spec, "INT")
        self.assertEqual(default, 7)

    def test_build_caches_result(self):
        @self.reg.register
        def _():
            return [("t", _make_spec("INT", 0))]

        self.reg.build()
        first = self.reg._built
        self.reg.build()
        self.assertIs(self.reg._built, first)

    def test_build_returns_copy(self):
        @self.reg.register
        def _():
            return [("t", _make_spec("INT", 0))]

        result = self.reg.build()
        result.clear()
        self.assertEqual(len(self.reg.build()), 1)

    def test_duplicate_tag_name_raises_value_error(self):
        @self.reg.register
        def _():
            return [("dup", _make_spec("INT", 0))]

        @self.reg.register
        def __():
            return [("dup", _make_spec("REAL", 1.0))]

        with self.assertRaises(ValueError) as ctx:
            self.reg.build()
        self.assertIn("duplicate", str(ctx.exception).lower())

    def test_build_type_map_keys_match_build(self):
        @self.reg.register
        def _():
            return [
                ("a", _make_spec("INT", 0)),
                ("b", _make_spec("REAL", 0.0)),
            ]

        type_map = self.reg.build_type_map()
        built_names = {n for n, _, _ in self.reg.build()}
        self.assertEqual(set(type_map.keys()), built_names)

    def test_build_type_map_returns_copy(self):
        @self.reg.register
        def _():
            return [("t", _make_spec("INT", 0))]

        tm = self.reg.build_type_map()
        tm["injected"] = "FAKE"
        self.assertNotIn("injected", self.reg.build_type_map())


class TestInvalidate(unittest.TestCase):

    def setUp(self):
        self.reg = TagRegistry()

    def test_invalidate_clears_built(self):
        @self.reg.register
        def _():
            return [("t", _make_spec("INT", 0))]

        self.reg.build()
        self.assertIsNotNone(self.reg._built)
        self.reg.invalidate()
        self.assertIsNone(self.reg._built)

    def test_invalidate_clears_type_map(self):
        @self.reg.register
        def _():
            return [("t", _make_spec("INT", 0))]

        self.reg.build_type_map()
        self.assertIsNotNone(self.reg._type_map)
        self.reg.invalidate()
        self.assertIsNone(self.reg._type_map)

    def test_invalidate_type_map_is_alias(self):
        self.assertIs(
            self.reg.invalidate.__func__, self.reg.invalidate_type_map.__func__
        )

    def test_rebuild_after_invalidate(self):
        @self.reg.register
        def _():
            return [("t", _make_spec("INT", 0))]

        self.reg.build()
        self.reg.invalidate()
        result = self.reg.build()
        self.assertEqual(len(result), 1)


class TestBuildArgv(unittest.TestCase):

    def setUp(self):
        self.reg = TagRegistry()

    def test_build_argv_format(self):
        @self.reg.register
        def _():
            return [("my_tag", _make_spec("INT", 0))]

        argv = self.reg.build_argv()
        self.assertIn("my_tag=INT", argv)

    def test_build_argv_with_base_args(self):
        @self.reg.register
        def _():
            return [("t", _make_spec("REAL", 0.0))]

        port = next_port()

        argv = self.reg.build_argv(base_args=["--print", "--address", f":{port}"])
        self.assertEqual(argv[0], "--print")
        self.assertEqual(argv[1], "--address")
        self.assertEqual(argv[2], f":{port}")
        self.assertIn("t=REAL", argv)

    def test_build_argv_empty_registry(self):
        argv = self.reg.build_argv(base_args=["--print"])
        self.assertEqual(argv, ["--print"])

    def test_argv_property_includes_print(self):
        @self.reg.register
        def _():
            return [("t", _make_spec("INT", 0))]

        self.assertIn("--print", self.reg.argv)

    def test_specs_property_matches_build(self):
        @self.reg.register
        def _():
            return [("t", _make_spec("INT", 0))]

        self.assertEqual(self.reg.specs, self.reg.build())


class TestThreadSafety(unittest.TestCase):

    def test_concurrent_register_does_not_corrupt_raw(self):
        reg = TagRegistry()
        n_threads = 10
        tags_per_thread = 20
        barrier = threading.Barrier(n_threads)

        def worker(idx):
            barrier.wait()

            @reg.register
            def _():
                return [
                    (f"t_{idx}_{i}", _make_spec("INT", i))
                    for i in range(tags_per_thread)
                ]

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(n_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(reg._raw), n_threads * tags_per_thread)

    def test_concurrent_build_is_consistent(self):
        reg = TagRegistry()

        @reg.register
        def _():
            return [(f"t{i}", _make_spec("INT", i)) for i in range(50)]

        results = []
        barrier = threading.Barrier(10)

        def worker():
            barrier.wait()
            results.append(reg.build())

        threads = [threading.Thread(target=worker) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertTrue(all(r == results[0] for r in results))


if __name__ == "__main__":
    unittest.main()
