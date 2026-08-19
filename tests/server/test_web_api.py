# Copyright 2026 Merck KGaA, Darmstadt, Germany and/or its affiliates.
# All rights reserved

# test/server/test_web_api.py
import unittest

import threading
import time
import cpppo
from cpppo.server.enip.main import main as enip_main
import requests

from ethernetip_emulator.server.web_api import WebApi
from ethernetip_emulator.server.device import AttributeDevice
from ethernetip_emulator.server.tag_specs import tag_registry
from ethernetip_emulator.server.device import actions
from tests.server import next_port


def _start_server(port: int) -> tuple:
    server_control = cpppo.apidict(timeout=1.0)
    AttributeDevice.set_server_control(server_control)
    AttributeDevice._web_api = WebApi(host="0.0.0.0", port=8080)

    def background_task():
        with AttributeDevice._actions.bind(AttributeDevice):
            AttributeDevice.start_web()
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


class TestWebApi(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        @tag_registry.register
        def _():
            return [
                ("tag_string", actions.type.string("TEST")),
            ]

        cls.server_control, cls.thread = _start_server(next_port())

    @classmethod
    def tearDownClass(cls) -> None:
        _stop_server(cls.server_control, cls.thread)

    def setUp(self) -> None:
        AttributeDevice._ensure_defaults()
        AttributeDevice.unprotect("tag_string")
        actions._lookup("tag_string.DATA")[slice(0, 1)] = ["TEST"]  # type: ignore
        AttributeDevice.protect("tag_string.LEN")

    def test_tag_in_request(self):
        url = "http://localhost:8080/tags"
        response = requests.get(url)
        data = response.json()
        self.assertTrue(
            any(tags.get("name") == "tag_string.DATA" for tags in data.get("tags"))
        )
        self.assertTrue(
            any(tags.get("name") == "tag_string.LEN" for tags in data.get("tags"))
        )

    def test_get_val(self):
        url = "http://localhost:8080/tags/tag_string.DATA"
        response = requests.get(url)
        data = response.json()
        self.assertEqual(data.get("value"), "TEST")

    def test_get_len(self):
        url = "http://localhost:8080/tags/tag_string.LEN"
        response = requests.get(url)
        data = response.json()
        self.assertEqual(data.get("value"), 4)

    def test_post_val(self):
        url = "http://localhost:8080/tags/tag_string.DATA"
        body = {"value": "UPDATED"}
        requests.post(url, json=body)
        self.assertEqual(actions.string.get_val("tag_string"), "UPDATED")

    def test_put_val(self):
        url = "http://localhost:8080/tags/tag_string.DATA"
        body = {"value": "UPDATED"}
        requests.put(url, json=body)
        self.assertEqual(actions.string.get_val("tag_string"), "UPDATED")
