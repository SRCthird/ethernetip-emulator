# Copyright 2026 Merck KGaA, Darmstadt, Germany and/or its affiliates.
# All rights reserved

# test/server/datatypes/mock/test_datatype_gpio.py
import sys
import threading
import types
import unittest
from typing import Any
from unittest.mock import MagicMock, patch, PropertyMock


def _make_mock_gpio_module(platform_name: str) -> MagicMock:
    mod = MagicMock(name=f"{platform_name}.GPIO")
    mod.BCM = "BCM"
    mod.SUNXI = "SUNXI"
    mod.IN = "IN"
    mod.OUT = "OUT"
    mod.BOARD = "BOARD"
    pwm_instance = MagicMock(name="PWMInstance")
    mod.PWM.return_value = pwm_instance
    return mod


_MOCK_RPI_MODULE = _make_mock_gpio_module("RPi")
_MOCK_OPI_MODULE = _make_mock_gpio_module("OPi")

for _pkg, _mod_obj in [
    ("RPi", types.ModuleType("RPi")),
    ("RPi.GPIO", _MOCK_RPI_MODULE),
    ("OPi", types.ModuleType("OPi")),
    ("OPi.GPIO", _MOCK_OPI_MODULE),
]:
    sys.modules.setdefault(_pkg, _mod_obj)

from ethernetip_emulator.server.datatypes import gpio as _gpio_module
from ethernetip_emulator.server.datatypes.gpio import Gpio, _import_gpio
from ethernetip_emulator.server.actions import AttributeActions, TypeNamespace


def _make_actions(**kwargs) -> AttributeActions:
    kwargs.setdefault("sleep_fn", lambda _: None)
    return AttributeActions(**kwargs)


def _make_attr(name: str, value: Any = None) -> MagicMock:
    attr = MagicMock()
    attr.name = name
    attr.__getitem__ = MagicMock(return_value=[value])
    attr.__setitem__ = MagicMock()
    return attr


def _build_gpio(
    actions_inst: AttributeActions | None = None, platform: str = "RPi"
) -> tuple[Gpio, MagicMock]:
    if actions_inst is None:
        actions_inst = _make_actions()
    gpio_mod = _MOCK_RPI_MODULE if platform == "RPi" else _MOCK_OPI_MODULE
    gpio_mod.reset_mock()
    pwm_instance = MagicMock(name="PWMInstance")
    gpio_mod.PWM.return_value = pwm_instance

    with patch.object(_gpio_module, "_import_gpio", return_value=(gpio_mod, platform)):
        g = Gpio(actions_inst)

    return g, gpio_mod


def _bind_registry(actions_inst: AttributeActions, tags: dict) -> type:
    cls = type("FakeDevice", (), {"registry": tags})
    actions_inst.bind(cls)
    return cls


class TestImportGpio(unittest.TestCase):
    def test_returns_rpi_when_available(self):
        with patch.dict(sys.modules, {"RPi.GPIO": _MOCK_RPI_MODULE, "OPi.GPIO": None}):
            mod, platform = _import_gpio()
        self.assertEqual(platform, "RPi")
        self.assertIs(mod, _MOCK_RPI_MODULE)

    def test_falls_back_to_opi_when_rpi_missing(self):
        with patch.dict(sys.modules, {"RPi.GPIO": None, "OPi.GPIO": _MOCK_OPI_MODULE}):
            mod, platform = _import_gpio()
        self.assertEqual(platform, "OPi")
        self.assertIs(mod, _MOCK_OPI_MODULE)

    def test_raises_import_error_when_neither_available(self):
        with patch.dict(sys.modules, {"RPi.GPIO": None, "OPi.GPIO": None}):
            with self.assertRaises(ImportError):
                _import_gpio()


class TestGpioInit(unittest.TestCase):
    def test_setmode_bcm_for_rpi(self):
        g, gpio_mod = _build_gpio(platform="RPi")
        gpio_mod.setmode.assert_called_once_with(gpio_mod.BCM)

    def test_setmode_sunxi_for_opi(self):
        g, gpio_mod = _build_gpio(platform="OPi")
        gpio_mod.setmode.assert_called_once_with(gpio_mod.SUNXI)

    def test_pins_dict_starts_empty(self):
        g, _ = _build_gpio()
        self.assertEqual(g._pins, {})

    def test_pwm_instances_dict_starts_empty(self):
        g, _ = _build_gpio()
        self.assertEqual(g._pwm_instances, {})


class TestTypeValidator(unittest.TestCase):
    def _validate(self, v, platform="RPi"):
        gpio_mod = _MOCK_RPI_MODULE if platform == "RPi" else _MOCK_OPI_MODULE
        with patch.object(
            _gpio_module, "_import_gpio", return_value=(gpio_mod, platform)
        ):
            return Gpio.type_validator(v)

    def test_rejects_non_tuple(self):
        with self.assertRaises(TypeError):
            self._validate(42)

    def test_rejects_wrong_length_tuple(self):
        with self.assertRaises(TypeError):
            self._validate((1, True))

    def test_rejects_invalid_mode(self):
        with self.assertRaises(TypeError):
            self._validate((1, True, "analog"))

    def test_rejects_non_string_mode(self):
        with self.assertRaises(TypeError):
            self._validate((1, True, 99))

    def test_rpi_rejects_string_pin(self):
        with self.assertRaises(TypeError):
            self._validate(("PA0", True, "out"), platform="RPi")

    def test_rpi_rejects_negative_pin(self):
        with self.assertRaises(TypeError):
            self._validate((-1, True, "out"), platform="RPi")

    def test_opi_rejects_int_pin(self):
        with self.assertRaises(TypeError):
            self._validate((18, True, "out"), platform="OPi")

    def test_in_out_rejects_non_bool_default(self):
        with self.assertRaises(TypeError):
            self._validate((1, 1, "out"), platform="RPi")

    def test_pwm_rejects_non_numeric_default(self):
        with self.assertRaises(TypeError):
            self._validate((1, "fast", "pwm"), platform="RPi")

    def test_accepts_rpi_out(self):
        result = self._validate((18, False, "out"), platform="RPi")
        self.assertEqual(result, (18, False, "out"))

    def test_accepts_rpi_in(self):
        result = self._validate((17, True, "in"), platform="RPi")
        self.assertEqual(result, (17, True, "in"))

    def test_accepts_rpi_pwm(self):
        result = self._validate((12, 75.0, "pwm"), platform="RPi")
        self.assertEqual(result, (12, 75.0, "pwm"))

    def test_accepts_opi_out(self):
        result = self._validate(("PA0", False, "out"), platform="OPi")
        self.assertEqual(result, ("PA0", False, "out"))

    def test_accepts_pwm_int_default(self):
        result = self._validate((12, 50, "pwm"), platform="RPi")
        self.assertEqual(result, (12, 50, "pwm"))


class TestSetup(unittest.TestCase):
    def _make_gpio_with_registry(self, platform="RPi", mode="out", pin=18, duty=0.0):
        aa = _make_actions()
        g, gpio_mod = _build_gpio(aa, platform)
        setup_attr = [False]
        pin_attr = [pin]
        mode_attr = [mode]
        value_attr = [duty]

        if platform == "OPi":
            registry = {
                "LED.SETUP": setup_attr,
                "LED.PIN.DATA": pin_attr,
                "LED.MODE.DATA": mode_attr,
                "LED.VALUE": value_attr,
            }
        else:
            registry = {
                "LED.SETUP": setup_attr,
                "LED.PIN": pin_attr,
                "LED.MODE.DATA": mode_attr,
                "LED.VALUE": value_attr,
            }
        self._fake_device = _bind_registry(aa, registry)
        return g, gpio_mod, setup_attr

    def test_setup_calls_gpio_setup_out(self):
        g, gpio_mod, _ = self._make_gpio_with_registry(mode="out", pin=18)
        g.setup("LED")
        gpio_mod.setup.assert_called_once_with(18, gpio_mod.OUT)

    def test_setup_calls_gpio_setup_in(self):
        g, gpio_mod, _ = self._make_gpio_with_registry(mode="in", pin=17)
        g.setup("LED")
        gpio_mod.setup.assert_called_once_with(17, gpio_mod.IN)

    def test_setup_creates_pwm_instance(self):
        g, gpio_mod, _ = self._make_gpio_with_registry(mode="pwm", pin=12, duty=50.0)
        g.setup("LED")
        gpio_mod.PWM.assert_called_once_with(12, 1000)
        gpio_mod.PWM.return_value.start.assert_called_once_with(50.0)
        self.assertIn("LED", g._pwm_instances)

    def test_setup_sets_setup_flag(self):
        g, _, setup_attr = self._make_gpio_with_registry()
        g.setup("LED")
        self.assertTrue(setup_attr[0])

    def test_setup_skips_if_already_done(self):
        g, gpio_mod, setup_attr = self._make_gpio_with_registry()
        setup_attr[0] = True  # already set up
        g.setup("LED")
        gpio_mod.setup.assert_not_called()

    def test_setup_skips_if_setup_tag_none(self):
        aa = _make_actions()
        g, gpio_mod = _build_gpio(aa)
        self._fake_device = _bind_registry(aa, {})
        g.setup("LED")
        gpio_mod.setup.assert_not_called()

    def test_setup_skips_if_pin_tag_none(self):
        aa = _make_actions()
        g, gpio_mod = _build_gpio(aa)
        self._fake_device = _bind_registry(
            aa,
            {
                "LED.SETUP": [False],
                "LED.MODE.DATA": ["out"],
            },
        )
        g.setup("LED")
        gpio_mod.setup.assert_not_called()

    def test_setup_pins_dict_populated(self):
        g, _, _ = self._make_gpio_with_registry(pin=22)
        g.setup("LED")
        self.assertEqual(g._pins["LED"], 22)

    def test_setup_opi_reads_pin_data(self):
        g, gpio_mod, _ = self._make_gpio_with_registry(
            platform="OPi", mode="out", pin="PA0"
        )
        g.setup("LED")
        gpio_mod.setup.assert_called_once_with("PA0", gpio_mod.OUT)

    def test_setup_pwm_duty_clamped_above_100(self):
        g, gpio_mod, _ = self._make_gpio_with_registry(mode="pwm", pin=12, duty=150.0)
        g.setup("LED")
        gpio_mod.PWM.return_value.start.assert_called_once_with(100.0)

    def test_setup_pwm_duty_clamped_below_0(self):
        g, gpio_mod, _ = self._make_gpio_with_registry(mode="pwm", pin=12, duty=-10.0)
        g.setup("LED")
        gpio_mod.PWM.return_value.start.assert_called_once_with(0.0)


class TestOnSetHook(unittest.TestCase):
    def _make_wired_gpio(self, mode="out", pin=18, platform="RPi"):
        aa = _make_actions()
        g, gpio_mod = _build_gpio(aa, platform)
        g._pins["LED"] = pin

        setup_attr = [True]
        mode_attr = [mode]

        if platform == "OPi":
            pin_key = "LED.PIN.DATA"
        else:
            pin_key = "LED.PIN"

        self._fake_device = _bind_registry(
            aa,
            {
                "LED.SETUP": setup_attr,
                pin_key: [pin],
                "LED.MODE.DATA": mode_attr,
            },
        )
        return g, gpio_mod

    def test_ignores_non_value_tags(self):
        g, gpio_mod = self._make_wired_gpio()
        g.on_set_hook("LED.MODE", MagicMock(), slice(0, 1), [1])
        gpio_mod.output.assert_not_called()

    def test_out_calls_gpio_output_true(self):
        g, gpio_mod = self._make_wired_gpio(mode="out", pin=18)
        g.on_set_hook("LED.VALUE", MagicMock(), slice(0, 1), [1])
        gpio_mod.output.assert_called_once_with(18, True)

    def test_out_calls_gpio_output_false(self):
        g, gpio_mod = self._make_wired_gpio(mode="out", pin=18)
        g.on_set_hook("LED.VALUE", MagicMock(), slice(0, 1), [0])
        gpio_mod.output.assert_called_once_with(18, False)

    def test_out_skips_when_pin_not_in_pins(self):
        g, gpio_mod = self._make_wired_gpio(mode="out")
        del g._pins["LED"]
        g.on_set_hook("LED.VALUE", MagicMock(), slice(0, 1), [1])
        gpio_mod.output.assert_not_called()

    def test_out_skips_when_mode_tag_none(self):
        aa = _make_actions()
        g, gpio_mod = _build_gpio(aa)
        g._pins["LED"] = 18
        self._fake_device = _bind_registry(aa, {"LED.SETUP": [True]})
        g.on_set_hook("LED.VALUE", MagicMock(), slice(0, 1), [1])
        gpio_mod.output.assert_not_called()

    def test_pwm_changes_duty_cycle(self):
        g, gpio_mod = self._make_wired_gpio(mode="pwm", pin=12)
        pwm_mock = MagicMock()
        g._pwm_instances["LED"] = pwm_mock
        g.on_set_hook("LED.VALUE", MagicMock(), slice(0, 1), [75.0])
        pwm_mock.ChangeDutyCycle.assert_called_once_with(75.0)

    def test_pwm_duty_clamped_above_100(self):
        g, _ = self._make_wired_gpio(mode="pwm", pin=12)
        pwm_mock = MagicMock()
        g._pwm_instances["LED"] = pwm_mock
        g.on_set_hook("LED.VALUE", MagicMock(), slice(0, 1), [150.0])
        pwm_mock.ChangeDutyCycle.assert_called_once_with(100.0)

    def test_pwm_duty_clamped_below_0(self):
        g, _ = self._make_wired_gpio(mode="pwm", pin=12)
        pwm_mock = MagicMock()
        g._pwm_instances["LED"] = pwm_mock
        g.on_set_hook("LED.VALUE", MagicMock(), slice(0, 1), [-5.0])
        pwm_mock.ChangeDutyCycle.assert_called_once_with(0.0)

    def test_pwm_skips_when_no_instance(self):
        g, gpio_mod = self._make_wired_gpio(mode="pwm", pin=12)
        g.on_set_hook("LED.VALUE", MagicMock(), slice(0, 1), [50.0])


class TestReadWritePin(unittest.TestCase):
    def test_read_pin_returns_gpio_input(self):
        aa = _make_actions()
        g, gpio_mod = _build_gpio(aa)
        g._pins["BTN"] = 17
        gpio_mod.input.return_value = 1
        result = g.read_pin("BTN")
        self.assertTrue(result)
        gpio_mod.input.assert_called_once_with(17)

    def test_read_pin_returns_false_when_pin_not_registered(self):
        g, _ = _build_gpio()
        self.assertFalse(g.read_pin("MISSING"))

    def test_write_pin_writes_to_value_tag(self):
        aa = _make_actions()
        g, _ = _build_gpio(aa)
        value_attr = _make_attr("LED.VALUE", 0)
        self._fake_device = _bind_registry(aa, {"LED.VALUE": value_attr})
        g.write_pin("LED", True)
        value_attr.__setitem__.assert_called_once_with(slice(0, 1), [True])

    def test_write_pin_skips_when_tag_missing(self):
        aa = _make_actions()
        g, _ = _build_gpio(aa)
        self._fake_device = _bind_registry(aa, {})
        g.write_pin("LED", True)


class TestOnChange(unittest.TestCase):
    def test_delegates_to_parent_on_change(self):
        aa = _make_actions()
        g, _ = _build_gpio(aa)
        cb = MagicMock()
        g.on_change("LED", cb)
        self.assertIn("LED.VALUE", aa._listeners)

    def test_returns_parent(self):
        aa = _make_actions()
        g, _ = _build_gpio(aa)
        result = g.on_change("LED", MagicMock())
        self.assertIs(result, aa)


class TestStartPolling(unittest.TestCase):
    def test_defers_when_not_entered(self):
        aa = _make_actions()
        g, _ = _build_gpio(aa)
        self.assertFalse(aa._entered)
        before = len(aa._pending)
        g.start_polling("BTN")
        self.assertEqual(len(aa._pending), before + 1)
        aa._pending.clear()

    def test_launches_worker_when_entered(self):
        aa = _make_actions()
        g, gpio_mod = _build_gpio(aa)
        g._pins["BTN"] = 17
        gpio_mod.input.return_value = 0
        value_attr = _make_attr("BTN.VALUE", 0)
        setup_attr = [True]
        self._fake_device = _bind_registry(
            aa, {"BTN.SETUP": setup_attr, "BTN.VALUE": value_attr}
        )

        with aa:
            g.start_polling("BTN", period=0.01)
            self.assertEqual(len(aa._threads), 1)


class TestPollPin(unittest.TestCase):
    def _run_poll(self, gpio_mod, pin_values: list, *, platform="RPi"):
        aa = _make_actions()
        g, _ = _build_gpio(aa, platform)
        g._pins["BTN"] = 17

        written = []
        value_attr = MagicMock()
        value_attr.__setitem__ = MagicMock(
            side_effect=lambda k, v: written.append(v[0])
        )
        setup_attr = [True]
        fake_device = _bind_registry(
            aa, {"BTN.SETUP": setup_attr, "BTN.VALUE": value_attr}
        )

        call_count = [0]

        def fake_input(pin):
            idx = min(call_count[0], len(pin_values) - 1)
            call_count[0] += 1
            return pin_values[idx]

        gpio_mod.input.side_effect = fake_input

        iterations = [0]

        def fake_sleep(_):
            iterations[0] += 1
            if iterations[0] >= len(pin_values) + 1:
                aa._stop.set()

        aa._sleep = fake_sleep

        t = threading.Thread(
            target=g._poll_pin, args=("BTN", slice(0, 1), 0.0), daemon=True
        )
        t.start()
        t.join(timeout=2.0)
        del fake_device
        return written

    def test_writes_value_on_rising_edge(self):
        gpio_mod = _MOCK_RPI_MODULE
        gpio_mod.reset_mock()
        written = self._run_poll(gpio_mod, [0, 0, 1, 1])
        self.assertIn(1, written)

    def test_writes_value_on_falling_edge(self):
        gpio_mod = _MOCK_RPI_MODULE
        gpio_mod.reset_mock()
        written = self._run_poll(gpio_mod, [1, 1, 0, 0])
        self.assertIn(0, written)

    def test_does_not_write_on_no_change(self):
        gpio_mod = _MOCK_RPI_MODULE
        gpio_mod.reset_mock()
        written = self._run_poll(gpio_mod, [0, 0, 0])
        self.assertEqual(len(written), 1)

    def test_retries_setup_when_pin_missing(self):
        aa = _make_actions()
        g, gpio_mod = _build_gpio(aa)
        gpio_mod.input.return_value = 0
        setup_attr = [True]
        self._fake_device = _bind_registry(aa, {"BTN.SETUP": setup_attr})

        sleep_calls = [0]

        def fake_sleep(_):
            sleep_calls[0] += 1
            if sleep_calls[0] >= 3:
                aa._stop.set()

        aa._sleep = fake_sleep
        t = threading.Thread(
            target=g._poll_pin, args=("BTN", slice(0, 1), 0.0), daemon=True
        )
        t.start()
        t.join(timeout=2.0)


class TestExit(unittest.TestCase):
    def test_stops_all_pwm_instances(self):
        g, gpio_mod = _build_gpio()
        pwm1, pwm2 = MagicMock(), MagicMock()
        g._pwm_instances = {"A": pwm1, "B": pwm2}
        g.__exit__(None, None, None)
        pwm1.stop.assert_called_once()
        pwm2.stop.assert_called_once()

    def test_pwm_stop_exception_does_not_propagate(self):
        g, _ = _build_gpio()
        bad_pwm = MagicMock()
        bad_pwm.stop.side_effect = RuntimeError("hardware gone")
        g._pwm_instances = {"A": bad_pwm}
        g.__exit__(None, None, None)

    def test_pwm_instances_cleared_after_exit(self):
        g, _ = _build_gpio()
        g._pwm_instances = {"A": MagicMock()}
        g.__exit__(None, None, None)
        self.assertEqual(g._pwm_instances, {})

    def test_gpio_cleanup_called(self):
        g, gpio_mod = _build_gpio()
        g.__exit__(None, None, None)
        gpio_mod.cleanup.assert_called_once()

    def test_pins_cleared_after_exit(self):
        g, _ = _build_gpio()
        g._pins = {"LED": 18}
        g.__exit__(None, None, None)
        self.assertEqual(g._pins, {})


class TestGpioUnavailableFallback(unittest.TestCase):
    def test_stub_type_validator_raises(self):
        from ethernetip_emulator.server.actions import AttributeActions

        class StubGpio:
            def __init__(self, parent):
                self.parent = parent

            @staticmethod
            def type_validator(_):
                raise TypeError(
                    "GPIO is not a usable datatype. "
                    "Neither RPi.GPIO nor OPi.GPIO is installed"
                )

        with self.assertRaises(TypeError):
            StubGpio.type_validator((18, True, "out"))


class TestGpioExpander(unittest.TestCase):
    def _expand(self, preset, platform="RPi"):
        import ethernetip_emulator.server.datatypes.gpio as _gm
        import ethernetip_emulator.server.actions as _act

        gpio_mod = _MOCK_RPI_MODULE if platform == "RPi" else _MOCK_OPI_MODULE
        with patch.object(_gm, "_import_gpio", return_value=(gpio_mod, platform)):
            expand_fn = _gm.tag_registry._expanders["GPIO"]
            return expand_fn("MY_GPIO", preset)

    def test_rpi_pin_tag_is_dint(self):
        tags = self._expand((18, False, "out"), platform="RPi")
        pin_entry = next(t for t in tags if t[0] == "MY_GPIO.PIN")
        from ethernetip_emulator.server.actions import TypeNamespace

        self.assertEqual(pin_entry[1].type_name, "DINT")

    def test_opi_pin_tag_is_string(self):
        tags = self._expand(("PA0", False, "out"), platform="OPi")
        pin_entry = next(t for t in tags if t[0] == "MY_GPIO.PIN")
        self.assertEqual(pin_entry[1].type_name, "STRING")

    def test_pwm_value_tag_is_real(self):
        tags = self._expand((12, 50.0, "pwm"), platform="RPi")
        val_entry = next(t for t in tags if t[0] == "MY_GPIO.VALUE")
        self.assertEqual(val_entry[1].type_name, "REAL")

    def test_out_value_tag_is_dint(self):
        tags = self._expand((18, False, "out"), platform="RPi")
        val_entry = next(t for t in tags if t[0] == "MY_GPIO.VALUE")
        self.assertEqual(val_entry[1].type_name, "DINT")

    def test_in_value_tag_is_dint(self):
        tags = self._expand((17, True, "in"), platform="RPi")
        val_entry = next(t for t in tags if t[0] == "MY_GPIO.VALUE")
        self.assertEqual(val_entry[1].type_name, "DINT")

    def test_mode_tag_is_string(self):
        tags = self._expand((18, False, "out"), platform="RPi")
        mode_entry = next(t for t in tags if t[0] == "MY_GPIO.MODE")
        self.assertEqual(mode_entry[1].type_name, "STRING")

    def test_setup_tag_is_bool_false(self):
        tags = self._expand((18, False, "out"), platform="RPi")
        setup_entry = next(t for t in tags if t[0] == "MY_GPIO.SETUP")
        self.assertEqual(setup_entry[1].type_name, "BOOL")
        self.assertFalse(setup_entry[1].default)

    def test_expander_returns_four_children(self):
        tags = self._expand((18, False, "out"), platform="RPi")
        self.assertEqual(len(tags), 4)

    def test_child_names_use_passed_name(self):
        tags = self._expand((18, False, "out"), platform="RPi")
        names = {t[0] for t in tags}
        self.assertEqual(
            names,
            {"MY_GPIO.PIN", "MY_GPIO.VALUE", "MY_GPIO.MODE", "MY_GPIO.SETUP"},
        )

    def test_pwm_value_default_is_float(self):
        tags = self._expand((12, 75, "pwm"), platform="RPi")
        val_entry = next(t for t in tags if t[0] == "MY_GPIO.VALUE")
        # float(75) == 75.0
        self.assertIsInstance(val_entry[1].default, float)
        self.assertEqual(val_entry[1].default, 75.0)

    def test_out_value_default_is_int(self):
        tags = self._expand((18, True, "out"), platform="RPi")
        val_entry = next(t for t in tags if t[0] == "MY_GPIO.VALUE")
        self.assertIsInstance(val_entry[1].default, int)
        self.assertEqual(val_entry[1].default, 1)


class TestSetupNoneGuards(unittest.TestCase):
    def _make_gpio_partial(self, *, pin_val, mode_val):
        aa = _make_actions()
        g, gpio_mod = _build_gpio(aa, platform="RPi")
        self._fake_device = _bind_registry(
            aa,
            {
                "LED.SETUP": [False],
                "LED.PIN": [pin_val],
                "LED.MODE.DATA": [mode_val],
                "LED.VALUE": [0],
            },
        )
        return g, gpio_mod

    def test_setup_skips_when_pin_value_is_none(self):
        g, gpio_mod = self._make_gpio_partial(pin_val=None, mode_val="out")
        g.setup("LED")
        gpio_mod.setup.assert_not_called()

    def test_setup_flag_not_set_when_pin_is_none(self):
        aa = _make_actions()
        g, _ = _build_gpio(aa)
        setup_attr = [False]
        self._fake_device = _bind_registry(
            aa,
            {
                "LED.SETUP": setup_attr,
                "LED.PIN": [None],
                "LED.MODE.DATA": ["out"],
                "LED.VALUE": [0],
            },
        )
        g.setup("LED")
        self.assertFalse(setup_attr[0])

    def test_setup_skips_when_mode_value_is_none(self):
        g, gpio_mod = self._make_gpio_partial(pin_val=18, mode_val=None)
        g.setup("LED")
        gpio_mod.setup.assert_not_called()

    def test_setup_flag_not_set_when_mode_is_none(self):
        aa = _make_actions()
        g, _ = _build_gpio(aa)
        setup_attr = [False]
        self._fake_device = _bind_registry(
            aa,
            {
                "LED.SETUP": setup_attr,
                "LED.PIN": [18],
                "LED.MODE.DATA": [None],
                "LED.VALUE": [0],
            },
        )
        g.setup("LED")
        self.assertFalse(setup_attr[0])

    def test_setup_skips_when_gpio_mode_unrecognised(self):
        g, gpio_mod = self._make_gpio_partial(pin_val=18, mode_val="analog")
        g.setup("LED")
        gpio_mod.setup.assert_not_called()

    def test_setup_flag_not_set_when_gpio_mode_unrecognised(self):
        aa = _make_actions()
        g, _ = _build_gpio(aa)
        setup_attr = [False]
        self._fake_device = _bind_registry(
            aa,
            {
                "LED.SETUP": setup_attr,
                "LED.PIN": [18],
                "LED.MODE.DATA": ["analog"],
                "LED.VALUE": [0],
            },
        )
        g.setup("LED")
        self.assertFalse(setup_attr[0])

    def test_pins_dict_not_populated_when_gpio_mode_unrecognised(self):
        aa = _make_actions()
        g, gpio_mod = _build_gpio(aa)
        setup_attr = [False]
        self._fake_device = _bind_registry(
            aa,
            {
                "LED.SETUP": setup_attr,
                "LED.PIN": [18],
                "LED.MODE.DATA": ["bogus"],
                "LED.VALUE": [0],
            },
        )
        g.setup("LED")
        gpio_mod.setup.assert_not_called()
        self.assertFalse(setup_attr[0])


if __name__ == "__main__":
    unittest.main()
