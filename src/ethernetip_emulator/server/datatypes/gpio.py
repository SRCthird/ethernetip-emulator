# Copyright 2026 Merck KGaA, Darmstadt, Germany and/or its affiliates.
# All rights reserved

# src/ethernetip_emulator/server/datatypes/gpio.py
from __future__ import annotations
from typing import TYPE_CHECKING, Any, Tuple
from ..device import actions
from ..tag_specs import tag_registry

if TYPE_CHECKING:
    from ..actions import AttributeActions


def _import_gpio():
    try:
        import RPi.GPIO as GPIO
        return GPIO, "RPi"
    except ImportError:
        pass
    try:
        import OPi.GPIO as GPIO
        return GPIO, "OPi"
    except ImportError:
        pass
    raise ImportError("Neither RPi.GPIO nor OPi.GPIO is installed")


try:
    _import_gpio()
    @actions.datatype
    class Gpio:
        def __init__(self, parent: AttributeActions):
            self.parent = parent
            self._gpio, self._platform = _import_gpio()
            self._gpio.setmode(
                self._gpio.BCM if self._platform == "RPi" else self._gpio.SUNXI
            )
            self._pins: dict[str, Any] = {}
            self._pwm_instances: dict[str, Any] = {}

        @staticmethod
        def type_validator(v: Any) -> Tuple[Any, bool | float, str]:
            if not isinstance(v, tuple) or len(v) != 3:
                raise TypeError(
                    f"GPIO default must be a (pin, default, mode) tuple, got {type(v).__name__!r}: {v!r}"
                )
            pin, default, mode = v
            if not isinstance(mode, str) or mode not in ("in", "out", "pwm"):
                raise TypeError(
                    f"GPIO mode must be 'in', 'out', or 'pwm', got {mode!r}"
                )
            _, platform = _import_gpio()
            if platform == "RPi":
                if not isinstance(pin, int) or pin < 0:
                    raise TypeError(
                        f"GPIO pin for RPi must be a non-negative int, got {type(pin).__name__!r}: {pin!r}"
                    )
            else:
                if not isinstance(pin, str):
                    raise TypeError(
                        f"GPIO pin for OPi must be a str (SUNXI name), got {type(pin).__name__!r}: {pin!r}"
                    )
            if mode == "pwm":
                try:
                    float(default)
                except (TypeError, ValueError):
                    raise TypeError(
                        f"GPIO PWM default must be numeric, got {type(default).__name__!r}: {default!r}"
                    )
            else:
                if not isinstance(default, bool):
                    raise TypeError(
                        f"GPIO in/out default must be bool, got {type(default).__name__!r}: {default!r}"
                    )
            return (pin, default, mode)

        @staticmethod
        @tag_registry.expander("GPIO")
        def _(name: str, preset: Tuple[Any, Any, str]):
            pin, default, mode = preset
            _, platform = _import_gpio()
            pin_tag = (
                (f"{name}.PIN", actions.type.DINT(pin))
                if platform == "RPi"
                else (f"{name}.PIN", actions.type.STRING(pin))
            )
            value_tag = (
                (f"{name}.VALUE", actions.type.REAL(float(default)))
                if mode == "pwm"
                else (f"{name}.VALUE", actions.type.DINT(int(default)))
            )
            return [
                pin_tag,
                value_tag,
                (f"{name}.MODE", actions.type.STRING(mode)),
                (f"{name}.SETUP", actions.type.BOOL(False)),
            ]

        def on_set_hook(self, tag_name: str, attr: Any, key: Any, value: Any) -> None:
            if not tag_name.endswith(".VALUE"):
                return
            name_prefix = tag_name[: -len(".VALUE")]
            self.setup(name_prefix)
            pin = self._pins.get(name_prefix)
            if pin is None:
                return
            mode_tag = self.parent._lookup(f"{name_prefix}.MODE.DATA")
            if mode_tag is None:
                return
            mode = mode_tag[0] if isinstance(mode_tag[0], str) else None
            if mode == "out":
                self._gpio.output(pin, bool(value[0] if isinstance(value, list) else value))
            elif mode == "pwm":
                pwm = self._pwm_instances.get(name_prefix)
                if pwm is not None:
                    duty = float(value[0] if isinstance(value, list) else value)
                    pwm.ChangeDutyCycle(max(0.0, min(100.0, duty)))

        def on_change(self, name_prefix: str, callback=None, *, key=slice(0, 1)):
            return self.parent.on_change(f"{name_prefix}.VALUE", callback, key=key)

        def setup(self, name_prefix: str) -> None:
            setup_tag = self.parent._lookup(f"{name_prefix}.SETUP")
            if setup_tag is None or setup_tag[0] is True:
                return
            if self._platform == "OPi":
                pin_tag = self.parent._lookup(f"{name_prefix}.PIN.DATA")
            else:
                pin_tag = self.parent._lookup(f"{name_prefix}.PIN")
            mode_tag = self.parent._lookup(f"{name_prefix}.MODE.DATA")
            if pin_tag is None or mode_tag is None:
                return
            pin = pin_tag[0] if isinstance(pin_tag[0], (int, str)) else None
            mode = mode_tag[0] if isinstance(mode_tag[0], str) else None
            if pin is None or mode is None:
                return
            self._pins[name_prefix] = pin
            gpio_mode = {
                "in":  self._gpio.IN,
                "out": self._gpio.OUT,
                "pwm": self._gpio.OUT,
            }.get(mode)
            if gpio_mode is None:
                return
            self._gpio.setup(pin, gpio_mode)
            if mode == "pwm":
                value_tag = self.parent._lookup(f"{name_prefix}.VALUE")
                initial_duty = float(value_tag[0]) if value_tag is not None else 0.0
                pwm = self._gpio.PWM(pin, 1000)
                pwm.start(max(0.0, min(100.0, initial_duty)))
                self._pwm_instances[name_prefix] = pwm
            setup_tag[0] = True

        def start_polling(
            self,
            name_prefix: str,
            *,
            period: float = 0.01,
            key: slice = slice(0, 1),
        ) -> "AttributeActions":
            def _launch() -> None:
                self.parent._start_worker(
                    f"gpio.poll.{name_prefix}",
                    lambda: self._poll_pin(name_prefix, key, period),
                )

            if self.parent._entered:
                _launch()
            else:
                self.parent._pending.append(_launch)

            return self.parent

        def _poll_pin(self, name_prefix: str, key: slice, period: float) -> None:
            self.setup(name_prefix)
            pin = self._pins.get(name_prefix)
            last = None
            while not self.parent._stop.is_set():
                if pin is None:
                    self.setup(name_prefix)
                    pin = self._pins.get(name_prefix)
                    self.parent._sleep(period)
                    continue
                current = bool(self._gpio.input(pin))
                if current != last:
                    value_tag = self.parent._lookup(f"{name_prefix}.VALUE")
                    if value_tag is not None:
                        self.parent._write_attr(value_tag, key, [int(current)])
                    last = current
                self.parent._sleep(period)

        def read_pin(self, tag_name: str) -> bool:
            pin = self._pins.get(tag_name)
            if pin is None:
                return False
            return bool(self._gpio.input(pin))

        def write_pin(self, name_prefix: str, value: bool, key: slice = slice(0,1)) -> None:
            data_tag = self.parent._lookup(f"{name_prefix}.VALUE")
            if data_tag is None:
                return
            self.parent._write_attr(data_tag, key, [value])

        def __exit__(
            self,
            exc_type: type | None,
            exc_val: BaseException | None,
            exc_tb: Any | None,
        ) -> None:
            for pwm in self._pwm_instances.values():
                try:
                    pwm.stop()
                except Exception:
                    pass
            self._pwm_instances.clear()
            self._gpio.cleanup()
            self._pins.clear()

except ImportError:
    @actions.datatype
    class Gpio:
        def __init__(self, parent: AttributeActions):
            self.parent = parent

        @staticmethod
        def type_validator(_: Any) -> int:
            raise TypeError(f"GPIO is not a usable datatype. Neither RPi.GPIO nor OPi.GPIO is installed")
