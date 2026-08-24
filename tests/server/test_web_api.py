# Copyright 2026 Merck KGaA, Darmstadt, Germany and/or its affiliates.
# All rights reserved

# test/server/test_web_api.py
import unittest

import threading
import time
import cpppo
from cpppo.server.enip.main import main as enip_main
import requests
from unittest import mock

from ethernetip_emulator.server.web_api import TagTypeError, WebApi
from ethernetip_emulator.server.device import AttributeDevice
from ethernetip_emulator.server.tag_specs import tag_registry
from ethernetip_emulator.server.device import actions
from tests.server import next_port


def _start_server(port: int) -> tuple:
    server_control = cpppo.apidict(timeout=1.0)
    AttributeDevice.set_server_control(server_control)

    AttributeDevice._web_api = WebApi(host="localhost", port=8080)
    AttributeDevice._web_api.__enter__()

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
    AttributeDevice._web_api.__exit__()  # type: ignore
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
                ("tag_boolarray", actions.type.boolarray([False, False, False, False])),
            ]

        cls.server_control, cls.thread = _start_server(next_port())

    @classmethod
    def tearDownClass(cls) -> None:
        _stop_server(cls.server_control, cls.thread)

    def setUp(self) -> None:
        AttributeDevice._ensure_defaults()
        AttributeDevice.unprotect("tag_string.DATA")
        actions._lookup("tag_string.DATA")[slice(0, 1)] = ["TEST"]  # type: ignore
        AttributeDevice.protect("tag_string.LEN")
        AttributeDevice.unprotect("tag_boolarray")
        actions._lookup("tag_boolarray")[slice(0, 4)] = [False, False, False, False]  # type: ignore

    def test_get_health(self):
        url = "http://localhost:8080/health"
        response = requests.get(url)
        data = response.json()
        self.assertEqual(data.get("status"), "ok")

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
        url = "http://localhost:8080/tag/tag_string.DATA"
        response = requests.get(url)
        data = response.json()
        self.assertEqual(data.get("value"), "TEST")

    def test_get_len(self):
        url = "http://localhost:8080/tag/tag_string.LEN"
        response = requests.get(url)
        data = response.json()
        self.assertEqual(data.get("value"), 4)

    def test_post_val(self):
        url = "http://localhost:8080/tag/tag_string.DATA"
        body = {"value": "UPDATED"}
        requests.post(url, json=body)
        self.assertEqual(actions.string.get_val("tag_string"), "UPDATED")

    def test_put_val(self):
        url = "http://localhost:8080/tag/tag_string.DATA"
        body = {"value": "UPDATED"}
        requests.put(url, json=body)
        self.assertEqual(actions.string.get_val("tag_string"), "UPDATED")

    def test_post_array(self):
        url = "http://localhost:8080/tag/tag_boolarray"
        body = {"value": [True, True, True, True]}
        requests.post(url, json=body)
        self.assertEqual(
            actions.boolarray.get_val("tag_boolarray"), [True, True, True, True]
        )

    def test_put_array(self):
        url = "http://localhost:8080/tag/tag_boolarray"
        body = {"value": [True, True, True, True]}
        requests.put(url, json=body)
        self.assertEqual(
            actions.boolarray.get_val("tag_boolarray"), [True, True, True, True]
        )

    def test_get_datatypes(self):
        url = "http://localhost:8080/datatypes"
        response = requests.get(url)
        data = response.json()
        datatype = data["datatypes"][0]
        self.assertEqual(datatype["name"], "STRING")
        self.assertIn("tag_string.LEN", datatype["tags"])
        self.assertIn("tag_string.DATA", datatype["tags"])

    def test_get_datatype(self):
        url = "http://localhost:8080/datatype/STRING"
        response = requests.get(url)
        datatype = response.json()
        self.assertEqual(datatype["name"], "STRING")
        self.assertIn("tag_string.LEN", datatype["tags"])
        self.assertIn("tag_string.DATA", datatype["tags"])

    def test_get_unknown_tag_returns_404(self):
        response = requests.get("http://localhost:8080/tag/does_not_exist")
        self.assertEqual(response.status_code, 404)
        body = response.json()
        self.assertEqual(body.get("error"), "tag_not_found")

    def test_write_unknown_tag_returns_404(self):
        response = requests.put(
            "http://localhost:8080/tag/does_not_exist", json={"value": "x"}
        )
        self.assertEqual(response.status_code, 404)
        body = response.json()
        self.assertEqual(body.get("error"), "tag_not_found")

    def test_write_readonly_tag_returns_403(self):
        response = requests.put(
            "http://localhost:8080/tag/tag_string.LEN", json={"value": 99}
        )
        self.assertEqual(response.status_code, 403)
        body = response.json()
        self.assertEqual(body.get("error"), "tag_read_only")

    def test_write_with_invalid_json_body_returns_400(self):
        response = requests.put(
            "http://localhost:8080/tag/tag_string.DATA",
            data="{not-valid-json",
            headers={"Content-Type": "application/json"},
        )
        self.assertEqual(response.status_code, 400)
        body = response.json()
        self.assertEqual(body.get("error"), "bad_request")

    def test_write_with_missing_value_key_returns_400(self):
        response = requests.put(
            "http://localhost:8080/tag/tag_string.DATA",
            json={"not_value": "oops"},
        )
        self.assertEqual(response.status_code, 400)
        body = response.json()
        self.assertEqual(body.get("error"), "bad_request")

    def test_get_unknown_datatype_returns_404(self):
        response = requests.get("http://localhost:8080/datatype/nonexistent_type")
        self.assertEqual(response.status_code, 404)
        body = response.json()
        self.assertEqual(body.get("error"), "datatype_not_found")

    def test_unhandled_exception_returns_500(self):
        from ethernetip_emulator.server import web_api as web_api_module

        with (
            mock.patch.object(
                WebApi,
                "_serialize_all",
                side_effect=RuntimeError("unexpected failure"),
            ),
            mock.patch.object(web_api_module.log, "exception") as fake_log,
        ):
            response = requests.get("http://localhost:8080/tags")

        self.assertEqual(response.status_code, 500)
        body = response.json()
        self.assertEqual(body.get("error"), "internal_error")
        self.assertEqual(body.get("message"), "unexpected failure")
        fake_log.assert_called_once()

    def test_serialize_sets_value_none_on_attribute_error(self):
        api = WebApi.__new__(WebApi)

        attr = mock.Mock(spec=["parser"])
        attr.parser = None
        type(attr).value = mock.PropertyMock(side_effect=AttributeError)

        with mock.patch.object(WebApi, "_device_cls") as fake_device_cls:
            fake_device_cls.return_value.is_protected.return_value = False
            result = api._serialize("some_tag", attr, type_map={"some_tag": "group_a"})

        self.assertIsNone(result["value"])
        self.assertEqual(result["name"], "some_tag")
        self.assertEqual(result["group"], "group_a")
        self.assertFalse(result["readonly"])

    def test_validator_for_raises_when_type_name_is_none(self):
        api = WebApi.__new__(WebApi)

        attr = mock.Mock(spec=["parser"])
        attr.parser = None

        with self.assertRaises(TagTypeError) as ctx:
            api._validator_for(attr)
        self.assertIn("has no parser", str(ctx.exception))

    def test_validator_for_raises_when_type_validator_is_none(self):
        api = WebApi.__new__(WebApi)

        fake_parser = mock.Mock()
        fake_parser.__class__.__name__ = "SomeType"
        attr = mock.Mock(spec=["parser"])
        attr.parser = fake_parser

        fake_type_attr = mock.Mock(spec=[])
        fake_actions = mock.Mock()
        fake_actions._datatypes.get.return_value = fake_type_attr

        with mock.patch.object(WebApi, "_actions", return_value=fake_actions):
            with self.assertRaises(TagTypeError) as ctx:
                api._validator_for(attr)

        fake_actions._datatypes.get.assert_called_once_with("sometype")
        self.assertIn("SomeType", str(ctx.exception))
        self.assertIn("has no type_validator method", str(ctx.exception))

    def test_stop_logs_warning_when_thread_does_not_terminate(self):
        from ethernetip_emulator.server import web_api as web_api_module

        api = WebApi.__new__(WebApi)
        api._lock = threading.Lock()
        api._server = mock.Mock()

        stuck_thread = mock.Mock()
        stuck_thread.is_alive.return_value = True
        api._server_thread = stuck_thread

        with mock.patch.object(web_api_module.log, "warning") as fake_warning:
            api.stop()

        stuck_thread.join.assert_called_once_with(timeout=5)
        stuck_thread.is_alive.assert_called()
        fake_warning.assert_called_once()
        self.assertIsNone(api._server)
        self.assertIsNone(api._server_thread)

    def test_start_is_noop_when_already_started(self):
        assert AttributeDevice._web_api is not None
        first_server = AttributeDevice._web_api._server
        first_thread = AttributeDevice._web_api._server_thread
        self.assertIsNotNone(first_server)
        self.assertIsNotNone(first_thread)
        self.assertTrue(first_thread.is_alive())

        AttributeDevice._web_api.start()

        self.assertIs(AttributeDevice._web_api._server, first_server)
        self.assertIs(AttributeDevice._web_api._server_thread, first_thread)
        self.assertTrue(first_thread.is_alive())
