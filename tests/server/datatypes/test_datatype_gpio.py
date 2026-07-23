# Copyright 2026 Merck KGaA, Darmstadt, Germany and/or its affiliates.
# All rights reserved

# test/server/datatypes/test_datatype_gpio.py
import importlib
import unittest
from unittest.mock import patch

import threading
import time
import cpppo
from cpppo.server.enip.main import main as enip_main

import ethernetip_emulator.server.datatypes.gpio as gpio_mod
from ethernetip_emulator.server.device import AttributeDevice
from ethernetip_emulator.server.tag_specs import tag_registry
from ethernetip_emulator.server.device import actions
from tests.server import next_port


def _start_server(port: int) -> tuple:
    server_control = cpppo.apidict(timeout=1.0)
    AttributeDevice.set_server_control(server_control)

    def background_task():
        with AttributeDevice._actions.bind(AttributeDevice):
            enip_main(
                argv=tag_registry.build_argv(base_args=["--address", f":{port}"]),
                attribute_class=AttributeDevice,
                server={"control": server_control},
            )

    thread = threading.Thread(target=background_task, daemon=True)
    thread.start()
    time.sleep(0.5)
    return server_control, thread


def _stop_server(server_control, thread) -> None:
    server_control["done"] = True
    thread.join(timeout=5.0)
    tag_registry.invalidate()
    tag_registry._raw.clear()
    AttributeDevice.reset_defaults()


class TestGpioImportError(unittest.TestCase):
    def test_type_validator_raises_on_importerror(self):
        with patch.dict("sys.modules", {"RPi.GPIO": None, "OPi.GPIO": None}):
            # Re-import to pick up ImportError path
            import ethernetip_emulator.server.datatypes.gpio as gpio_mod  # noqa: F401

            importlib.reload(gpio_mod)
            self.assertTrue(hasattr(gpio_mod, "Gpio"))
            with self.assertRaises(TypeError) as cm:
                gpio_mod.Gpio.type_validator((0, True, "in"))  # type: ignore
            self.assertIn("GPIO is not a usable datatype", str(cm.exception))


class TestDatatypeGPIORegistry(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.server_control, cls.thread = _start_server(next_port())

    @classmethod
    def tearDownClass(cls) -> None:
        _stop_server(cls.server_control, cls.thread)

    def test_type_validator_above_max(self):
        with self.assertRaises(ValueError):
            tag_registry.register(lambda: [("tag_gpio", actions.type.GPIO("FAIL"))])
