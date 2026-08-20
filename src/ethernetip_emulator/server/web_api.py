# Copyright 2026 Merck KGaA, Darmstadt, Germany and/or its affiliates.
# All rights reserved

# src/ethernetip_emulator/server/web_api.py
from __future__ import annotations

import json
import logging
import threading
from typing import Any, Dict, Mapping, Optional, TYPE_CHECKING
from wsgiref.simple_server import WSGIServer, WSGIRequestHandler, make_server

import web

from ethernetip_emulator.server.tag_specs import TagRegistry


if TYPE_CHECKING:
    from .actions import AttributeActions
    from .device import AttributeDevice

log = logging.getLogger(__name__)


class TagNotFoundError(KeyError):
    """Raised when a requested tag does not exist in the registry."""


class TagReadOnlyError(PermissionError):
    """Raised when a write is attempted against a protected tag."""


class TagTypeError(ValueError):
    """Raised when a supplied value does not satisfy a tag's type safety."""


class _QuietWSGIRequestHandler(WSGIRequestHandler):
    """Routes access log lines through :mod:`logging` instead of stderr."""

    def log_message(self, format, *args):
        log.debug("%s - %s", self.address_string(), format % args)


class WebApi:

    _URLS = (
        "/health",
        "health",
        "/tags",
        "tags",
        "/tag/(.+)",
        "tag",
        "/datatypes/",
        "datatypes",
    )

    def __init__(
        self,
        host: str,
        port: int,
        actions: "AttributeActions",
        tag_registry: "TagRegistry",
    ) -> None:
        self.host = host
        self.port = port
        self.actions = actions
        self.tag_registry = tag_registry

        self._server: Optional[WSGIServer] = None
        self._server_thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

        self.app = self._build_application()

    def _get_attribute(self, tag_name: str) -> "AttributeDevice":
        attr = self.actions._lookup(tag_name)
        if attr is None:
            raise TagNotFoundError(tag_name)
        return attr

    def _serialize(self, name: str, attr: "AttributeDevice") -> Dict[str, Any]:
        from .device import AttributeDevice

        try:
            value = (
                list(attr.value)
                if isinstance(attr.value, (list, tuple))
                else attr.value
            )
        except AttributeError:
            value = None

        type_cls = getattr(attr, "parser", None)

        type_group = self.tag_registry.build_type_map().get(name)

        return {
            "name": name,
            "value": value,
            "group": type_group,
            "type": type(type_cls).__name__ if type_cls is not None else None,
            "readonly": AttributeDevice.is_protected(name),
        }

    def _write(self, tag_name: str, raw_value: Any) -> Dict[str, Any]:
        from .device import AttributeDevice

        attr = self._get_attribute(tag_name)

        if AttributeDevice.is_protected(tag_name):
            raise TagReadOnlyError(tag_name)

        origin_type = type(getattr(attr, "parser", None)).__name__
        type_attr = self.actions._datatypes.get(origin_type.lower())
        type_validator = getattr(type_attr, "type_validator", None)
        if type_validator is None:
            raise TagTypeError(f"Type, {origin_type}, has no type_validator method")

        if isinstance(raw_value, list):
            cast_value = [type_validator(v) for v in raw_value]
        else:
            cast_value = type_validator(raw_value)

        if isinstance(cast_value, list):
            for index, item in enumerate(cast_value):
                attr[index] = item
        else:
            attr[slice(0, 1)] = [cast_value]

        return self._serialize(tag_name, attr)

    @staticmethod
    def _respond(status: str, body: Dict[str, Any]) -> str:
        web.ctx.status = status
        web.header("Content-Type", "application/json")
        return json.dumps(body)

    def _handle_error(self, exc: Exception) -> str:
        if isinstance(exc, TagNotFoundError):
            return self._respond(
                "404 Not Found",
                {"error": "tag_not_found", "message": f"unknown tag '{exc}'"},
            )
        if isinstance(exc, TagReadOnlyError):
            return self._respond(
                "403 Forbidden",
                {"error": "tag_read_only", "message": f"tag '{exc}' is read-only"},
            )
        if isinstance(exc, TagTypeError):
            return self._respond(
                "400 Bad Request",
                {"error": "type_mismatch", "message": str(exc)},
            )
        log.exception("unhandled error in WebApi request")
        return self._respond(
            "500 Internal Server Error",
            {"error": "internal_error", "message": str(exc)},
        )

    def _build_application(self) -> "web.application":
        outer = self

        class health:
            def GET(self) -> str:
                return outer._respond("200 OK", {"status": "ok"})

        class tags:
            def GET(self) -> str:
                try:
                    body = {
                        "tags": [
                            outer._serialize(n, a)
                            for n, a in outer.actions._registry().items()
                        ]
                    }
                except Exception as exc:
                    return outer._handle_error(exc)
                return outer._respond("200 OK", body)

        class tag:
            def GET(self, tag_name: str) -> str:
                try:
                    attr = outer._get_attribute(tag_name)
                    body = outer._serialize(tag_name, attr)
                except Exception as exc:
                    return outer._handle_error(exc)
                return outer._respond("200 OK", body)

            def _write_request(self, tag_name: str) -> str:
                try:
                    raw_body = web.data()
                    payload = json.loads(raw_body) if raw_body else None
                    if not isinstance(payload, dict) or "value" not in payload:
                        return outer._respond(
                            "400 Bad Request",
                            {
                                "error": "bad_request",
                                "message": 'request body must be JSON: {"value": <...>}',
                            },
                        )
                    result = outer._write(tag_name, payload["value"])
                except Exception as exc:
                    return outer._handle_error(exc)
                return outer._respond("200 OK", result)

            def PUT(self, tag_name: str) -> str:
                return self._write_request(tag_name)

            def POST(self, tag_name: str) -> str:
                return self._write_request(tag_name)

        fvars = {"health": health, "tags": tags, "tag": tag}
        return web.application(self._URLS, fvars, autoreload=False)

    def start(self) -> None:
        with self._lock:
            if self._server_thread is not None:
                return
            self._server = make_server(
                self.host,
                self.port,
                self.app.wsgifunc(),
                handler_class=_QuietWSGIRequestHandler,
            )
            self._server_thread = threading.Thread(
                target=self._server.serve_forever,
                name="WebApiServer",
                daemon=True,
            )
            self._server_thread.start()
            log.info("WebApi listening on %s:%s", self.host, self.port)

    def stop(self) -> None:
        with self._lock:
            if self._server is not None:
                self._server.shutdown()
            if self._server_thread is not None:
                self._server_thread.join(timeout=5)
            self._server = None
            self._server_thread = None
