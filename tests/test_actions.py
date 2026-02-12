# Copyright 2026 Merck KGaA, Darmstadt, Germany and/or its affiliates.
# All rights reserved
import unittest
from unittest.mock import patch

from src.server.actions import AttributeActions


class TestAttributeActions(unittest.TestCase):
    def _kill_action_after(self, stop_after_sleeps: int):
        sleeps = {"n": 0}

        actions: AttributeActions

        def sleep_fn(_: float) -> None:
            sleeps["n"] += 1
            if sleeps["n"] >= stop_after_sleeps:
                actions.stop()

        logs: list[str] = []

        def logger(msg: str) -> None:
            logs.append(msg)

        actions = AttributeActions(sleep_fn=sleep_fn, logger=logger)
        return actions, logs

    def test_worker_setitem_exception_hits_pass_branch(self):
        actions: AttributeActions
        sleep_calls = {"n": 0}

        def sleep_fn(_: float) -> None:
            sleep_calls["n"] += 1
            if sleep_calls["n"] >= 1:
                actions.stop()

        actions = AttributeActions(sleep_fn=sleep_fn)

        class AttrWithFailingSetItem:
            def __getitem__(self, key):
                return 0

            def __setitem__(self, key, value):
                raise RuntimeError("fail to set")

        class AttrClass:
            registry = {"T": AttrWithFailingSetItem()}

        actions.bind(AttrClass)

        actions.run_increment_worker(
            tag_name="T",
            period=0.1,
            key=0,
            start=0,
            increment=1,
            wrap=None,
            initial_delay=0.0,
        )

        self.assertTrue(actions._stop.is_set())

    def test_I_TEXT_falls_back_to_setting_value_attr(self):
        actions = AttributeActions()

        class Other:
            def __init__(self):
                self.value = None

            def __setitem__(self, key, value):
                raise TypeError("simulate setitem failure")

        class ITextAttr:
            name = "I_TEXT"
            registry = {"O_TEXT": Other()}

        i_text = ITextAttr()

        actions.on_set(i_text, 0, 999)

        self.assertEqual(ITextAttr.registry["O_TEXT"].value, 999)

    def test_on_set_noop_for_unknown_attr_name(self):
        actions = AttributeActions()

        class A:
            name = "SOMETHING_ELSE"

        actions.on_set(A(), 0, 123)

    def test_stop_sets_event(self):
        actions = AttributeActions()
        self.assertFalse(actions._stop.is_set())
        actions.stop()
        self.assertTrue(actions._stop.is_set())

    def test_start_increment_runs_worker_via_fake_thread(self):
        ran = {"value": False}

        def sleep_fn(_: float) -> None:
            actions.stop()

        logs = []

        def logger(msg: str) -> None:
            logs.append(msg)

        class Attr:
            def __init__(self):
                self.store = {0: 0}

            def __getitem__(self, k):
                return self.store[k]

            def __setitem__(self, k, v):
                self.store[k] = v

        class AttrClass:
            registry = {"TAG": Attr()}

        class FakeThread:
            def __init__(self, **kwargs):
                self._target = kwargs["target"]

            def start(self):
                ran["value"] = True
                self._target()

        def thread_factory(**kwargs):
            return FakeThread(**kwargs)

        actions = AttributeActions(
            sleep_fn=sleep_fn, thread_factory=thread_factory, logger=logger
        )
        actions.bind(AttrClass)

        actions.start_increment(
            "TAG", period=0.1, key=0, start=0, increment=1, wrap=None, initial_delay=0.0
        )

        self.assertTrue(ran["value"])
        self.assertEqual(AttrClass.registry["TAG"][0], 1)

    def test_start_increment_creates_and_starts_thread_and_tracks_it(self):
        started = {"value": False}

        class FakeThread:
            def __init__(self, **kwargs):
                self.kwargs = kwargs
                self.daemon = kwargs.get("daemon")
                self.name = kwargs.get("name")
                self.target = kwargs.get("target")

            def start(self):
                started["value"] = True

        def thread_factory(**kwargs):
            return FakeThread(**kwargs)

        actions = AttributeActions(thread_factory=thread_factory)
        actions.start_increment("TAG1", period=1.0)

        self.assertTrue(started["value"])
        self.assertEqual(len(actions._threads), 1)
        self.assertEqual(actions._threads[0].name, "TAG1-increment")
        self.assertTrue(actions._threads[0].daemon)

    def test_default_thread_factory_path_is_executed(self):
        actions = AttributeActions()

        class FakeThread:
            def __init__(self, **kwargs):
                self.kwargs = kwargs

            def start(self):
                pass

        with patch("src.server.actions.threading.Thread", FakeThread):
            actions.start_increment("TAGX")

    def test_default_thread_factory_is_used_when_none_provided(self):
        actions = AttributeActions()
        self.assertIsNotNone(actions)

    def test_run_increment_worker_increments_once_and_exits(self):
        calls = {"n": 0}

        actions = AttributeActions()

        def sleep_fn(_: float) -> None:
            calls["n"] += 1
            if calls["n"] >= 2:
                actions.stop()

        logs: list[str] = []

        def logger(msg: str) -> None:
            logs.append(msg)

        actions = AttributeActions(sleep_fn=sleep_fn, logger=logger)

        class FakeAttr:
            def __init__(self) -> None:
                self.store = {"key": 0}

            def __getitem__(self, k):
                return self.store[k]

            def __setitem__(self, k, v):
                self.store[k] = v

        class FakeAttrClass:
            registry = {"test_tag": FakeAttr()}

        actions.bind(FakeAttrClass)

        actions.run_increment_worker(
            tag_name="test_tag",
            period=0.1,
            key="key",
            start=0,
            increment=1,
            wrap=None,
            initial_delay=0.1,
        )

        self.assertEqual(FakeAttrClass.registry["test_tag"]["key"], 1)
        self.assertEqual(logs, [])

    def test_worker_logs_when_attr_class_is_none(self):
        actions, logs = self._kill_action_after(stop_after_sleeps=2)

        actions.run_increment_worker(
            tag_name="X",
            period=0.1,
            key=0,
            start=0,
            increment=1,
            wrap=None,
            initial_delay=0.0,
        )

        self.assertTrue(any("attr_class is None" in m for m in logs))

    def test_worker_logs_when_tag_missing(self):
        actions, logs = self._kill_action_after(stop_after_sleeps=2)

        class AttrClass:
            registry = {}

        actions.bind(AttrClass)

        actions.run_increment_worker(
            tag_name="MISSING",
            period=0.1,
            key=0,
            start=0,
            increment=1,
            wrap=None,
            initial_delay=0.0,
        )

        self.assertTrue(any("attr is None" in m for m in logs))

    def test_worker_start_none_reads_current_via_getitem(self):
        actions, _ = self._kill_action_after(stop_after_sleeps=1)

        class FakeAttr:
            def __init__(self):
                self.store = {0: 10}

            def __getitem__(self, k):
                return self.store[k]

            def __setitem__(self, k, v):
                self.store[k] = v

        class AttrClass:
            registry = {"T": FakeAttr()}

        actions.bind(AttrClass)

        actions.run_increment_worker(
            tag_name="T",
            period=0.1,
            key=0,
            start=None,
            increment=2,
            wrap=None,
            initial_delay=0.0,
        )

        self.assertEqual(AttrClass.registry["T"][0], 12)

    def test_worker_wraps_value(self):
        actions, _ = self._kill_action_after(stop_after_sleeps=1)

        class FakeAttr:
            def __init__(self):
                self.store = {0: 0}

            def __getitem__(self, k):
                return self.store[k]

            def __setitem__(self, k, v):
                self.store[k] = v

        class AttrClass:
            registry = {"T": FakeAttr()}

        actions.bind(AttrClass)

        actions.run_increment_worker(
            tag_name="T",
            period=0.1,
            key=0,
            start=9,
            increment=3,
            wrap=10,
            initial_delay=0.0,
        )

        self.assertEqual(AttrClass.registry["T"][0], 2)

    def test_worker_falls_back_to_value_attribute_when_setitem_missing(self):
        actions, _ = self._kill_action_after(stop_after_sleeps=1)

        class ValueOnlyAttr:
            def __init__(self):
                self.value = 5

        class AttrClass:
            registry = {"T": ValueOnlyAttr()}

        actions.bind(AttrClass)

        actions.run_increment_worker(
            tag_name="T",
            period=0.1,
            key=0,
            start=None,  # read current from .value
            increment=1,
            wrap=None,
            initial_delay=0.0,
        )

        self.assertEqual(AttrClass.registry["T"].value, 6)

    def test_on_set_dispatches_I_TEXT_and_mirrors_to_O_TEXT(self):
        actions, _ = self._kill_action_after(stop_after_sleeps=1)

        class FakeAttr:
            def __init__(self, name):
                self.name = name
                self.store = {}

            def __setitem__(self, k, v):
                self.store[k] = v

        class AttrType:
            registry = {
                "O_TEXT": FakeAttr("O_TEXT"),
            }

        i_text = FakeAttr("I_TEXT")
        i_text.__class__ = AttrType

        actions.on_set(i_text, 0, 123)

        self.assertEqual(AttrType.registry["O_TEXT"].store[0], 123)
