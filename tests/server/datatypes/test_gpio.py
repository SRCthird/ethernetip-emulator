# Copyright 2026 Merck KGaA, Darmstadt, Germany and/or its affiliates.
# All rights reserved

# tests/server/datatypes/test_gpio.py
from __future__ import annotations

import sys
import types
import importlib
import unittest
from unittest.mock import MagicMock, patch
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


def _make_gpio_mock(platform: str = "RPi") -> MagicMock:
    """Return a MagicMock that looks like RPi.GPIO or OPi.GPIO."""
    gpio = MagicMock()
    gpio.BCM = "BCM"
    gpio.SUNXI = "SUNXI"
    gpio.IN = "IN"
    gpio.OUT = "OUT"
    gpio.input.return_value = 0
    pwm_instance = MagicMock()
    gpio.PWM.return_value = pwm_instance
    return gpio


def _install_gpio_stub(module_name: str, platform: str) -> MagicMock:
    gpio = _make_gpio_mock(platform)
    stub = types.ModuleType(module_name)
    stub.GPIO = gpio   # type: ignore
    for attr in ["BCM", "SUNXI", "IN", "OUT", "setmode", "setup",
                 "input", "output", "cleanup", "PWM"]:
        setattr(stub, attr, getattr(gpio, attr))
    sys.modules[module_name] = stub
    parent_pkg = module_name.split(".")[0]
    if parent_pkg not in sys.modules:
        sys.modules[parent_pkg] = types.ModuleType(parent_pkg)
    return gpio

_GPIO_MODULE_PREFIXES = (
    "src.ethernetip_emulator.server.actions",
    "src.ethernetip_emulator.server.tag_specs",
    "src.ethernetip_emulator.server.device",
    "src.ethernetip_emulator.server.datatypes",
)


def _purge_gpio_modules() -> None:
    to_delete = [
        key for key in sys.modules
        if any(key == p or key.startswith(p + ".") for p in _GPIO_MODULE_PREFIXES)
    ]
    for key in to_delete:
        del sys.modules[key]


def _load_gpio_module(platform: str = "RPi"):
    _purge_gpio_modules()

    if platform == "RPi":
        gpio_mock = _install_gpio_stub("RPi.GPIO", "RPi")
        for mod in ("OPi.GPIO", "OPi"):
            sys.modules.pop(mod, None)
    else:
        gpio_mock = _install_gpio_stub("OPi.GPIO", "OPi")
        for mod in ("RPi.GPIO", "RPi"):
            sys.modules.pop(mod, None)

    mod = importlib.import_module("src.ethernetip_emulator.server.datatypes.gpio")
    Gpio = mod.Gpio
    return Gpio, gpio_mock


def _make_parent(registry: Dict | None = None, stop_after: int = 1):
    parent = MagicMock()
    parent._logger = MagicMock()
    parent._sleep = MagicMock()
    parent._entered = False
    parent._pending = []

    call_count = [0]
    def _is_set():
        call_count[0] += 1
        return call_count[0] > stop_after
    parent._stop.is_set.side_effect = _is_set

    _attrs = dict(registry or {})
    parent._lookup.side_effect = lambda tag: _attrs.get(tag)
    parent._read_attr.return_value = [0]
    return parent, _attrs


class TestGpioStub(unittest.TestCase):
    def setUp(self):
        for mod in ("RPi", "RPi.GPIO", "OPi", "OPi.GPIO"):
            sys.modules.pop(mod, None)
        _purge_gpio_modules()
        self.mod = importlib.import_module(
            "src.ethernetip_emulator.server.datatypes.gpio"
        )
        self.Gpio = self.mod.Gpio

    def test_stub_registered_on_actions(self):
        from src.ethernetip_emulator.server.device import actions
        self.assertIn("gpio", actions._datatypes)

    def test_stub_type_validator_raises_type_error(self):
        with self.assertRaises(TypeError):
            self.Gpio.type_validator((1, True, "out"))

    def test_stub_instantiates(self):
        parent = MagicMock()
        instance = self.Gpio(parent)
        self.assertIsNotNone(instance)


class TestGpioRPi(unittest.TestCase):

    def setUp(self):
        self.Gpio, self.gpio_mock = _load_gpio_module("RPi")
        self.parent, self.attrs = _make_parent()
        self.gpio = self.Gpio(self.parent)

    def test_init_sets_bcm_mode(self):
        self.gpio_mock.setmode.assert_called_with(self.gpio_mock.BCM)

    def test_type_validator_valid_out(self):
        result = self.Gpio.type_validator((17, True, "out"))
        self.assertEqual(result, (17, True, "out"))

    def test_type_validator_valid_in(self):
        result = self.Gpio.type_validator((17, False, "in"))
        self.assertEqual(result, (17, False, "in"))

    def test_type_validator_valid_pwm(self):
        result = self.Gpio.type_validator((18, 50.0, "pwm"))
        self.assertEqual(result, (18, 50.0, "pwm"))

    def test_type_validator_not_tuple_raises(self):
        with self.assertRaises(TypeError):
            self.Gpio.type_validator(17)

    def test_type_validator_wrong_length_raises(self):
        with self.assertRaises(TypeError):
            self.Gpio.type_validator((17, True))

    def test_type_validator_invalid_mode_raises(self):
        with self.assertRaises(TypeError):
            self.Gpio.type_validator((17, True, "bad"))

    def test_type_validator_non_int_pin_raises(self):
        with self.assertRaises(TypeError):
            self.Gpio.type_validator(("PA5", True, "out"))

    def test_type_validator_negative_pin_raises(self):
        with self.assertRaises(TypeError):
            self.Gpio.type_validator((-1, True, "out"))

    def test_type_validator_non_bool_default_for_out_raises(self):
        with self.assertRaises(TypeError):
            self.Gpio.type_validator((17, 1, "out"))

    def test_type_validator_non_numeric_pwm_default_raises(self):
        with self.assertRaises(TypeError):
            self.Gpio.type_validator((18, "bad", "pwm"))

    def test_expander_registered(self):
        from src.ethernetip_emulator.server.tag_specs import tag_registry
        self.assertIn("GPIO", tag_registry._expanders)

    def test_expander_returns_4_tags(self):
        from src.ethernetip_emulator.server.tag_specs import tag_registry
        expander = tag_registry._expanders["GPIO"]
        result = list(expander("LED", (17, True, "out")))
        self.assertEqual(len(result), 4)

    def test_expander_pin_tag_is_dint_for_rpi(self):
        from src.ethernetip_emulator.server.tag_specs import tag_registry
        expander = tag_registry._expanders["GPIO"]
        entries = {name: spec for name, spec in expander("LED", (17, True, "out"))}
        self.assertIn("DINT", entries["LED.PIN"].type_name)

    def test_expander_value_tag_is_real_for_pwm(self):
        from src.ethernetip_emulator.server.tag_specs import tag_registry
        expander = tag_registry._expanders["GPIO"]
        entries = {name: spec for name, spec in expander("LED", (18, 50.0, "pwm"))}
        self.assertIn("REAL", entries["LED.VALUE"].type_name)

    def test_expander_value_tag_is_dint_for_out(self):
        from src.ethernetip_emulator.server.tag_specs import tag_registry
        expander = tag_registry._expanders["GPIO"]
        entries = {name: spec for name, spec in expander("LED", (17, True, "out"))}
        self.assertIn("DINT", entries["LED.VALUE"].type_name)

    def test_expander_setup_default_is_false(self):
        from src.ethernetip_emulator.server.tag_specs import tag_registry
        expander = tag_registry._expanders["GPIO"]
        entries = {name: spec for name, spec in expander("LED", (17, True, "out"))}
        self.assertFalse(entries["LED.SETUP"].default)

    def _make_setup_attrs(self, pin=17, mode="out"):
        setup_attr = MagicMock()
        setup_attr.__getitem__ = MagicMock(return_value=False)
        setup_attr.__setitem__ = MagicMock()
        pin_attr = MagicMock()
        pin_attr.__getitem__ = MagicMock(return_value=pin)
        mode_attr = MagicMock()
        mode_attr.__getitem__ = MagicMock(return_value=mode)
        return setup_attr, pin_attr, mode_attr

    def test_setup_calls_gpio_setup_for_out(self):
        setup_attr, pin_attr, mode_attr = self._make_setup_attrs(17, "out")
        self.parent._lookup.side_effect = lambda t: {
            "LED.SETUP": setup_attr,
            "LED.PIN": pin_attr,
            "LED.MODE.DATA": mode_attr,
        }.get(t)
        self.gpio.setup("LED")
        self.gpio_mock.setup.assert_called_with(17, self.gpio_mock.OUT)

    def test_setup_calls_gpio_setup_for_in(self):
        setup_attr, pin_attr, mode_attr = self._make_setup_attrs(17, "in")
        self.parent._lookup.side_effect = lambda t: {
            "LED.SETUP": setup_attr,
            "LED.PIN": pin_attr,
            "LED.MODE.DATA": mode_attr,
        }.get(t)
        self.gpio.setup("LED")
        self.gpio_mock.setup.assert_called_with(17, self.gpio_mock.IN)

    def test_setup_creates_pwm_instance(self):
        setup_attr, pin_attr, mode_attr = self._make_setup_attrs(18, "pwm")
        value_attr = MagicMock()
        value_attr.__getitem__ = MagicMock(return_value=50.0)
        self.parent._lookup.side_effect = lambda t: {
            "LED.SETUP": setup_attr,
            "LED.PIN": pin_attr,
            "LED.MODE.DATA": mode_attr,
            "LED.VALUE": value_attr,
        }.get(t)
        self.gpio.setup("LED")
        self.gpio_mock.PWM.assert_called_with(18, 1000)
        self.gpio_mock.PWM.return_value.start.assert_called_once()
        self.assertIn("LED", self.gpio._pwm_instances)

    def test_setup_skips_when_already_set_up(self):
        setup_attr = MagicMock()
        setup_attr.__getitem__ = MagicMock(return_value=True)
        self.parent._lookup.side_effect = lambda t: {"LED.SETUP": setup_attr}.get(t)
        self.gpio.setup("LED")
        self.gpio_mock.setup.assert_not_called()

    def test_setup_skips_when_setup_tag_missing(self):
        self.parent._lookup.return_value = None
        self.gpio.setup("LED")
        self.gpio_mock.setup.assert_not_called()

    def test_setup_skips_when_pin_value_is_wrong_type(self):
        setup_attr = MagicMock()
        setup_attr.__getitem__ = MagicMock(return_value=False)
        setup_attr.__setitem__ = MagicMock()
        pin_attr = MagicMock()
        pin_attr.__getitem__ = MagicMock(return_value=None)
        mode_attr = MagicMock()
        mode_attr.__getitem__ = MagicMock(return_value="out")
        self.parent._lookup.side_effect = lambda t: {
            "LED.SETUP": setup_attr,
            "LED.PIN": pin_attr,
            "LED.MODE.DATA": mode_attr,
        }.get(t)
        self.gpio.setup("LED")
        self.gpio_mock.setup.assert_not_called()
        setup_attr.__setitem__.assert_not_called()

    def test_setup_skips_when_mode_value_is_wrong_type(self):
        setup_attr = MagicMock()
        setup_attr.__getitem__ = MagicMock(return_value=False)
        setup_attr.__setitem__ = MagicMock()
        pin_attr = MagicMock()
        pin_attr.__getitem__ = MagicMock(return_value=17)
        mode_attr = MagicMock()
        mode_attr.__getitem__ = MagicMock(return_value=42)
        self.parent._lookup.side_effect = lambda t: {
            "LED.SETUP": setup_attr,
            "LED.PIN": pin_attr,
            "LED.MODE.DATA": mode_attr,
        }.get(t)
        self.gpio.setup("LED")
        self.gpio_mock.setup.assert_not_called()
        setup_attr.__setitem__.assert_not_called()

    def test_setup_skips_when_pin_or_mode_missing(self):
        setup_attr = MagicMock()
        setup_attr.__getitem__ = MagicMock(return_value=False)
        self.parent._lookup.side_effect = lambda t: {
            "LED.SETUP": setup_attr,
        }.get(t)
        self.gpio.setup("LED")
        self.gpio_mock.setup.assert_not_called()

    def test_setup_skips_gpio_setup_when_mode_unrecognised(self):
        setup_attr = MagicMock()
        setup_attr.__getitem__ = MagicMock(return_value=False)
        setup_attr.__setitem__ = MagicMock()
        pin_attr = MagicMock()
        pin_attr.__getitem__ = MagicMock(return_value=17)
        mode_attr = MagicMock()
        mode_attr.__getitem__ = MagicMock(return_value="bogus")
        self.parent._lookup.side_effect = lambda t: {
            "LED.SETUP": setup_attr,
            "LED.PIN": pin_attr,
            "LED.MODE.DATA": mode_attr,
        }.get(t)
        self.gpio.setup("LED")
        self.gpio_mock.setup.assert_not_called()
        setup_attr.__setitem__.assert_not_called()

    def test_on_set_hook_ignores_non_value_tags(self):
        with patch.object(self.gpio, "setup") as mock_setup:
            self.gpio.on_set_hook("LED.MODE", MagicMock(), slice(0, 1), [1])
            mock_setup.assert_not_called()

    def test_on_set_hook_calls_setup(self):
        with patch.object(self.gpio, "setup") as mock_setup:
            self.gpio.on_set_hook("LED.VALUE", MagicMock(), slice(0, 1), [1])
            mock_setup.assert_called_once_with("LED")

    def test_on_set_hook_drives_gpio_output_for_out_mode(self):
        mode_attr = MagicMock()
        mode_attr.__getitem__ = MagicMock(return_value="out")
        self.parent._lookup.side_effect = lambda t: {
            "LED.MODE.DATA": mode_attr,
        }.get(t)
        self.gpio._pins["LED"] = 17
        with patch.object(self.gpio, "setup"):
            self.gpio.on_set_hook("LED.VALUE", MagicMock(), slice(0, 1), [1])
        self.gpio_mock.output.assert_called_with(17, True)

    def test_on_set_hook_changes_pwm_duty_cycle(self):
        mode_attr = MagicMock()
        mode_attr.__getitem__ = MagicMock(return_value="pwm")
        self.parent._lookup.side_effect = lambda t: {
            "LED.MODE.DATA": mode_attr,
        }.get(t)
        self.gpio._pins["LED"] = 18
        pwm_mock = MagicMock()
        self.gpio._pwm_instances["LED"] = pwm_mock
        with patch.object(self.gpio, "setup"):
            self.gpio.on_set_hook("LED.VALUE", MagicMock(), slice(0, 1), [75.0])
        pwm_mock.ChangeDutyCycle.assert_called_with(75.0)

    def test_on_set_hook_pwm_duty_clamped_to_100(self):
        mode_attr = MagicMock()
        mode_attr.__getitem__ = MagicMock(return_value="pwm")
        self.parent._lookup.side_effect = lambda t: {"LED.MODE.DATA": mode_attr}.get(t)
        self.gpio._pins["LED"] = 18
        pwm_mock = MagicMock()
        self.gpio._pwm_instances["LED"] = pwm_mock
        with patch.object(self.gpio, "setup"):
            self.gpio.on_set_hook("LED.VALUE", MagicMock(), slice(0, 1), [150.0])
        pwm_mock.ChangeDutyCycle.assert_called_with(100.0)

    def test_on_set_hook_pwm_duty_clamped_to_0(self):
        mode_attr = MagicMock()
        mode_attr.__getitem__ = MagicMock(return_value="pwm")
        self.parent._lookup.side_effect = lambda t: {"LED.MODE.DATA": mode_attr}.get(t)
        self.gpio._pins["LED"] = 18
        pwm_mock = MagicMock()
        self.gpio._pwm_instances["LED"] = pwm_mock
        with patch.object(self.gpio, "setup"):
            self.gpio.on_set_hook("LED.VALUE", MagicMock(), slice(0, 1), [-10.0])
        pwm_mock.ChangeDutyCycle.assert_called_with(0.0)

    def test_on_set_hook_skips_output_when_pin_not_registered(self):
        mode_attr = MagicMock()
        mode_attr.__getitem__ = MagicMock(return_value="out")
        self.parent._lookup.side_effect = lambda t: {"LED.MODE.DATA": mode_attr}.get(t)
        with patch.object(self.gpio, "setup"):
            self.gpio.on_set_hook("LED.VALUE", MagicMock(), slice(0, 1), [1])
        self.gpio_mock.output.assert_not_called()

    def test_on_set_hook_skips_when_mode_tag_missing(self):
        self.gpio._pins["LED"] = 17
        self.parent._lookup.return_value = None
        with patch.object(self.gpio, "setup"):
            self.gpio.on_set_hook("LED.VALUE", MagicMock(), slice(0, 1), [1])
        self.gpio_mock.output.assert_not_called()

    def test_on_change_delegates_to_parent(self):
        cb = MagicMock()
        self.gpio.on_change("LED", cb, key=slice(0, 1))
        self.parent.on_change.assert_called_once_with(
            "LED.VALUE", cb, key=slice(0, 1)
        )

    def test_start_polling_appends_to_pending_when_not_entered(self):
        self.parent._entered = False
        self.gpio.start_polling("LED", period=0.05)
        self.assertEqual(len(self.parent._pending), 1)
        self.parent._start_worker.assert_not_called()

    def test_start_polling_launches_immediately_when_entered(self):
        self.parent._entered = True
        self.gpio.start_polling("LED", period=0.05)
        self.parent._start_worker.assert_called_once()
        name = self.parent._start_worker.call_args[0][0]
        self.assertEqual(name, "gpio.poll.LED")

    def test_start_polling_returns_parent(self):
        result = self.gpio.start_polling("LED")
        self.assertIs(result, self.parent)

    def test_poll_pin_writes_value_on_change(self):
        value_attr = MagicMock()
        self.parent._lookup.side_effect = lambda t: {
            "LED.VALUE": value_attr,
        }.get(t)
        self.gpio._pins["LED"] = 17
        self.gpio_mock.input.return_value = 1

        parent, _ = _make_parent({"LED.VALUE": value_attr}, stop_after=1)
        gpio = self.Gpio(parent)
        gpio._pins["LED"] = 17
        gpio._gpio = self.gpio_mock
        parent._lookup.side_effect = lambda t: {"LED.VALUE": value_attr}.get(t)
        gpio._poll_pin("LED", slice(0, 1), 0.0)

        parent._write_attr.assert_called()

    def test_poll_pin_retries_setup_when_pin_unknown(self):
        parent, _ = _make_parent({}, stop_after=1)
        gpio = self.Gpio(parent)
        gpio._gpio = self.gpio_mock
        with patch.object(gpio, "setup") as mock_setup:
            gpio._poll_pin("LED", slice(0, 1), 0.0)
        mock_setup.assert_called()

    def test_read_pin_returns_false_when_unregistered(self):
        self.assertFalse(self.gpio.read_pin("LED"))

    def test_read_pin_calls_gpio_input(self):
        self.gpio._pins["LED"] = 17
        self.gpio_mock.input.return_value = 1
        result = self.gpio.read_pin("LED")
        self.assertTrue(result)
        self.gpio_mock.input.assert_called_with(17)

    def test_write_pin_writes_to_value_attr(self):
        value_attr = MagicMock()
        self.parent._lookup.side_effect = lambda t: {"LED.VALUE": value_attr}.get(t)
        self.gpio.write_pin("LED", True)
        self.parent._write_attr.assert_called_once_with(value_attr, slice(0, 1), [True])

    def test_write_pin_skips_when_value_tag_missing(self):
        self.parent._lookup.return_value = None
        self.gpio.write_pin("LED", True)
        self.parent._write_attr.assert_not_called()

    def test_exit_stops_all_pwm_instances(self):
        pwm1, pwm2 = MagicMock(), MagicMock()
        self.gpio._pwm_instances = {"LED1": pwm1, "LED2": pwm2}
        self.gpio.__exit__(None, None, None)
        pwm1.stop.assert_called_once()
        pwm2.stop.assert_called_once()

    def test_exit_clears_pwm_instances(self):
        self.gpio._pwm_instances = {"LED": MagicMock()}
        self.gpio.__exit__(None, None, None)
        self.assertEqual(self.gpio._pwm_instances, {})

    def test_exit_calls_gpio_cleanup(self):
        self.gpio.__exit__(None, None, None)
        self.gpio_mock.cleanup.assert_called_once()

    def test_exit_clears_pins(self):
        self.gpio._pins = {"LED": 17}
        self.gpio.__exit__(None, None, None)
        self.assertEqual(self.gpio._pins, {})

    def test_exit_swallows_pwm_stop_exceptions(self):
        pwm = MagicMock()
        pwm.stop.side_effect = RuntimeError("boom")
        self.gpio._pwm_instances = {"LED": pwm}
        self.gpio.__exit__(None, None, None)


class TestGpioOPi(unittest.TestCase):

    def setUp(self):
        self.Gpio, self.gpio_mock = _load_gpio_module("OPi")
        self.parent, self.attrs = _make_parent()
        self.gpio = self.Gpio(self.parent)

    def test_init_sets_sunxi_mode(self):
        self.gpio_mock.setmode.assert_called_with(self.gpio_mock.SUNXI)

    def test_type_validator_valid_opi_pin(self):
        result = self.Gpio.type_validator(("PA5", True, "out"))
        self.assertEqual(result, ("PA5", True, "out"))

    def test_type_validator_int_pin_raises_for_opi(self):
        with self.assertRaises(TypeError):
            self.Gpio.type_validator((17, True, "out"))

    def test_expander_pin_tag_is_string_for_opi(self):
        from src.ethernetip_emulator.server.tag_specs import tag_registry
        expander = tag_registry._expanders["GPIO"]
        entries = {name: spec for name, spec in expander("LED", ("PA5", True, "out"))}
        self.assertIn("STRING", entries["LED.PIN"].type_name)

    def test_setup_uses_pin_data_tag_for_opi(self):
        setup_attr = MagicMock()
        setup_attr.__getitem__ = MagicMock(return_value=False)
        setup_attr.__setitem__ = MagicMock()
        pin_attr = MagicMock()
        pin_attr.__getitem__ = MagicMock(return_value="PA5")
        mode_attr = MagicMock()
        mode_attr.__getitem__ = MagicMock(return_value="out")
        self.parent._lookup.side_effect = lambda t: {
            "LED.SETUP": setup_attr,
            "LED.PIN.DATA": pin_attr,
            "LED.MODE.DATA": mode_attr,
        }.get(t)
        self.gpio.setup("LED")
        self.gpio_mock.setup.assert_called_with("PA5", self.gpio_mock.OUT)


if __name__ == "__main__":
    unittest.main()
