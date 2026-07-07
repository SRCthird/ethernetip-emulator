# Copyright 2026 Merck KGaA, Darmstadt, Germany and/or its affiliates.
# All rights reserved

# src/server/actions/gpio.py
from __future__ import annotations
from typing import TYPE_CHECKING, Any, Tuple
from src.server.device import actions
from src.server.tag_specs import tag_registry

if TYPE_CHECKING:
    from src.server.actions import AttributeActions


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


@actions.datatype
class Gpio:
    def __init__(self, parent: AttributeActions):
        try:
            _import_gpio()
        except ImportError:
            return
        self.parent = parent
        self._gpio, self._platform = _import_gpio()
        self._gpio.setmode(
            self._gpio.BOARD if self._platform == "RPi" else self._gpio.SUNXI
        )
        self._pins: dict[str, Any] = {}

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

    def on_change(self, name_prefix: str, callback=None, *, key=None):
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
        setup_tag[0] = True

    def start_polling(
        self,
        name_prefix: str,
        *,
        period: float = 0.01,
        key: Any = 0,
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

    def _poll_pin(self, name_prefix: str, key: Any, period: float) -> None:
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
                    value_tag[key] = int(current)
                last = current
            self.parent._sleep(period)


    def read_pin(self, tag_name: str) -> bool:
        pin = self._pins.get(tag_name)
        if pin is None:
            return False
        return bool(self._gpio.input(pin))

    def write_pin(self, name_prefix: str, attr, key: Any, value: str):
        data_tag = self.parent._lookup(f"{name_prefix}.VALUE")
        if data_tag is None:
            return
        data_tag[key] = value

    def __exit__(self) -> None:
        self._gpio.cleanup()
        self._pins.clear()
