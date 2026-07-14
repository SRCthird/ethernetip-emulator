# Copyright 2026 Merck KGaA, Darmstadt, Germany and/or its affiliates.
# All rights reserved

# tests/server/test_device.py
import sys
import types
import unittest
from unittest.mock import MagicMock, patch
from typing import Any, Dict


def _install_cpppo_stubs():
    """
    Build the minimal cpppo package/module tree that device.py needs:
        cpppo
        cpppo.server
        cpppo.server.enip
        cpppo.server.enip.device          ← needs device.Attribute
    """
    # Only stub if cpppo is not already installed in this environment
    if "cpppo" in sys.modules and not isinstance(sys.modules["cpppo"], MagicMock):
        return  # real cpppo is available – nothing to do

    class _BaseAttribute:
        """Minimal stand-in for cpppo.server.enip.device.Attribute."""

        def __init__(self, name: str, type_cls: Any, **kwargs: Any) -> None:
            self.name = name
            self.type_cls = type_cls
            self.kwargs = kwargs
            self._store: Dict[Any, Any] = {}

        def __setitem__(self, key: Any, value: Any) -> None:
            self._store[key] = value

        def __getitem__(self, key: Any) -> Any:
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

import importlib as _importlib

_device_mod = _importlib.import_module("src.ethernetip_emulator.server.device")
AttributeDevice = _device_mod.AttributeDevice
actions = _device_mod.actions


def _make_registry_entries(extra=None):
    """Default tag registry entries used across tests."""
    base = [
        ("tag_int",   "INT",  42),
        ("tag_float", "REAL", 3.14),
        ("tag_list",  "DINT", [1, 2, 3]),
        ("tag_none",  "BOOL", None),
    ]
    return base + (extra or [])


class _RecordingActions:
    def __init__(self):
        self.calls = []

    def on_set(self, attr, key, value):
        self.calls.append((attr, key, value))


class TestAttributeDevice(unittest.TestCase):

    def setUp(self):
        global AttributeDevice
        device_mod = _importlib.import_module("src.ethernetip_emulator.server.device")
        AttributeDevice = device_mod.AttributeDevice
        AttributeDevice.reset_defaults()
        self._registry_patcher = patch(
            "src.ethernetip_emulator.server.device.tag_registry",
        )
        self.mock_tag_registry = self._registry_patcher.start()
        self.mock_tag_registry.build.return_value = _make_registry_entries()
        self.recording_actions = _RecordingActions()

    def tearDown(self):
        self._registry_patcher.stop()
        AttributeDevice.reset_defaults()

    def test_ensure_defaults_populates_dict(self):
        AttributeDevice._ensure_defaults()
        self.assertIsNotNone(AttributeDevice._defaults)
        self.assertIn("tag_int", AttributeDevice._defaults)
        self.assertIn("tag_float", AttributeDevice._defaults)
        self.assertIn("tag_list", AttributeDevice._defaults)

    def test_ensure_defaults_excludes_none_values(self):
        AttributeDevice._ensure_defaults()
        self.assertNotIn("tag_none", AttributeDevice._defaults)

    def test_ensure_defaults_is_idempotent(self):
        """Second call must not rebuild – tag_registry.build called only once."""
        AttributeDevice._ensure_defaults()
        AttributeDevice._ensure_defaults()
        self.mock_tag_registry.build.assert_called_once()

    def test_ensure_defaults_called_implicitly_on_first_init(self):
        self.assertIsNone(AttributeDevice._defaults)
        AttributeDevice("tag_int", "INT")
        self.assertIsNotNone(AttributeDevice._defaults)

    def test_init_adds_to_class_registry(self):
        attr = AttributeDevice("tag_int", "INT")
        self.assertIn("tag_int", AttributeDevice.registry)
        self.assertIs(AttributeDevice.registry["tag_int"], attr)

    def test_init_uses_custom_registry(self):
        custom: Dict[str, Any] = {}
        attr = AttributeDevice("tag_int", "INT", registry=custom)
        self.assertIn("tag_int", custom)
        self.assertIs(custom["tag_int"], attr)

    def test_init_custom_registry_does_not_pollute_class_registry(self):
        custom: Dict[str, Any] = {}
        AttributeDevice("tag_int", "INT", registry=custom)
        self.assertNotIn("tag_int", AttributeDevice.registry)

    def test_init_multiple_instances_all_registered(self):
        a1 = AttributeDevice("tag_int", "INT")
        a2 = AttributeDevice("tag_float", "REAL")
        self.assertIs(AttributeDevice.registry["tag_int"], a1)
        self.assertIs(AttributeDevice.registry["tag_float"], a2)

    def test_init_last_instance_wins_for_same_name(self):
        AttributeDevice("tag_int", "INT")
        attr2 = AttributeDevice("tag_int", "INT")
        self.assertIs(AttributeDevice.registry["tag_int"], attr2)

    def test_init_custom_defaults_override_class_defaults(self):
        custom_defaults = {"tag_int": 99}
        attr = AttributeDevice("tag_int", "INT", defaults=custom_defaults)
        self.assertEqual(attr.kwargs.get("default"), 99)

    def test_init_custom_actions_stored_on_instance(self):
        attr = AttributeDevice("tag_int", "INT", actions=self.recording_actions)
        self.assertIs(attr._actions, self.recording_actions)

    def test_init_falls_back_to_class_actions_when_none_given(self):
        attr = AttributeDevice("tag_int", "INT")
        self.assertIs(attr._actions, AttributeDevice._actions)

    def test_scalar_default_set_when_no_prior_default(self):
        attr = AttributeDevice("tag_int", "INT")
        self.assertEqual(attr.kwargs.get("default"), 42)

    def test_scalar_default_overwrites_scalar_kwarg_default(self):
        attr = AttributeDevice("tag_int", "INT", default=0)
        self.assertEqual(attr.kwargs.get("default"), 42)

    def test_scalar_default_overwrites_first_element_of_list_kwarg(self):
        attr = AttributeDevice("tag_int", "INT", default=[0, 0, 0])
        self.assertEqual(attr.kwargs["default"], [42, 0, 0])

    def test_scalar_default_replaces_empty_list_kwarg(self):
        attr = AttributeDevice("tag_int", "INT", default=[])
        self.assertEqual(attr.kwargs["default"], 42)

    def test_float_scalar_default_applied(self):
        attr = AttributeDevice("tag_float", "REAL")
        self.assertAlmostEqual(attr.kwargs.get("default"), 3.14, places=5)

    def test_list_default_set_when_no_prior_default(self):
        attr = AttributeDevice("tag_list", "DINT")
        self.assertEqual(attr.kwargs.get("default"), [1, 2, 3])

    def test_list_default_merges_into_longer_list_kwarg(self):
        attr = AttributeDevice("tag_list", "DINT", default=[0, 0, 0, 99])
        self.assertEqual(attr.kwargs["default"], [1, 2, 3, 99])

    def test_list_default_partial_merge_when_kwarg_shorter(self):
        attr = AttributeDevice("tag_list", "DINT", default=[0, 0])
        self.assertEqual(attr.kwargs["default"], [1, 2])

    def test_list_default_replaces_empty_list_kwarg(self):
        attr = AttributeDevice("tag_list", "DINT", default=[])
        self.assertEqual(attr.kwargs["default"], [1, 2, 3])

    def test_list_default_original_not_mutated(self):
        AttributeDevice._ensure_defaults()
        original = list(AttributeDevice._defaults["tag_list"])
        AttributeDevice("tag_list", "DINT", default=[0, 0, 0, 99])
        self.assertEqual(AttributeDevice._defaults["tag_list"], original)

    def test_unknown_tag_receives_no_default(self):
        attr = AttributeDevice("unknown_tag", "INT")
        self.assertNotIn("default", attr.kwargs)

    def test_tag_with_none_registry_value_receives_no_default(self):
        attr = AttributeDevice("tag_none", "BOOL")
        self.assertNotIn("default", attr.kwargs)

    def test_apply_default_is_noop_when_instance_defaults_is_none(self):
        attr = AttributeDevice("tag_int", "INT")
        attr._defaults = None
        kwargs: Dict[str, Any] = {}
        attr._apply_default("tag_int", kwargs)
        self.assertEqual(kwargs, {})

    def test_setitem_persists_value(self):
        attr = AttributeDevice("tag_int", "INT", actions=self.recording_actions)
        attr[0] = 100
        self.assertEqual(attr[0], 100)

    def test_setitem_calls_on_set_with_correct_args(self):
        attr = AttributeDevice("tag_int", "INT", actions=self.recording_actions)
        attr[0] = 55
        self.assertEqual(len(self.recording_actions.calls), 1)
        rec_attr, rec_key, rec_val = self.recording_actions.calls[0]
        self.assertIs(rec_attr, attr)
        self.assertEqual(rec_key, 0)
        self.assertEqual(rec_val, 55)

    def test_setitem_multiple_writes_all_forwarded_to_on_set(self):
        attr = AttributeDevice("tag_int", "INT", actions=self.recording_actions)
        attr[0] = 1
        attr[1] = 2
        attr[0] = 3
        self.assertEqual(len(self.recording_actions.calls), 3)

    def test_setitem_latest_value_wins(self):
        attr = AttributeDevice("tag_int", "INT", actions=self.recording_actions)
        attr[0] = 7
        attr[0] = 42
        self.assertEqual(attr[0], 42)

    def test_reset_defaults_sets_defaults_to_none(self):
        AttributeDevice._ensure_defaults()
        AttributeDevice.reset_defaults()
        self.assertIsNone(AttributeDevice._defaults)

    def test_reset_defaults_clears_class_registry(self):
        AttributeDevice("tag_int", "INT")
        AttributeDevice.reset_defaults()
        self.assertEqual(AttributeDevice.registry, {})

    def test_reset_defaults_allows_fresh_rebuild(self):
        AttributeDevice._ensure_defaults()
        AttributeDevice.reset_defaults()
        AttributeDevice._ensure_defaults()
        self.assertEqual(self.mock_tag_registry.build.call_count, 2)

    def test_module_level_actions_is_class_actions(self):
        import importlib
        device_mod = importlib.import_module("src.ethernetip_emulator.server.device")
        module_actions = device_mod.actions
        self.assertIs(module_actions, AttributeDevice._actions)


if __name__ == "__main__":
    unittest.main()
