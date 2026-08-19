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

    def log_message(self, fmt: str, *args: Any) -> None:
        log.debug("%s - %s", self.address_string(), fmt % args)


class WebApi:

    _URLS = (
        "/health",
        "health",
        "/tags",
        "tags",
        "/tag/(.+)",
        "tag",
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

    @staticmethod
    def _serialize(name: str, attr: "AttributeDevice") -> Dict[str, Any]:
        from .device import AttributeDevice

        try:
            value = (
                list(attr.value)
                if isinstance(attr.value, (list, tuple))
                else attr.value
            )
        except AttributeError:
            value = None

        type_cls = getattr(attr, "parser", None) or getattr(attr, "type_cls", None)

        return {
            "name": name,
            "value": value,
            "type": type(type_cls).__name__ if type_cls is not None else None,
            "readonly": AttributeDevice.is_protected(name),
        }

    @staticmethod
    def _cast_scalar(type_cls: Any, raw: Any) -> Any:
        candidate_ctor = None

        if hasattr(type_cls, "ctype"):
            candidate_ctor = type_cls.ctype
        elif isinstance(type_cls, type):
            candidate_ctor = type_cls

        if candidate_ctor is not None:
            return candidate_ctor(raw)

        if isinstance(raw, bool):
            return bool(raw)
        if isinstance(raw, int):
            return int(raw)
        if isinstance(raw, float):
            return float(raw)
        if isinstance(raw, str):
            return str(raw)

        raise TagTypeError(f"cannot determine target type for value {raw!r}")

    @classmethod
    def _validate_and_cast(cls, attr: "AttributeDevice", raw_value: Any) -> Any:
        type_cls = getattr(attr, "parser", None) or getattr(attr, "type_cls", None)
        current = getattr(attr, "value", None)
        is_array = isinstance(current, (list, tuple))

        try:
            if is_array:
                if not isinstance(raw_value, (list, tuple)):
                    raw_value = [raw_value]
                if len(raw_value) != len(current):
                    raise TagTypeError(
                        f"expected {len(current)} value(s), got {len(raw_value)}"
                    )
                return [cls._cast_scalar(type_cls, v) for v in raw_value]
            if isinstance(raw_value, (list, tuple)):
                if len(raw_value) != 1:
                    raise TagTypeError("expected a single scalar value")
                raw_value = raw_value[0]
            return cls._cast_scalar(type_cls, raw_value)
        except TagTypeError:
            raise
        except (TypeError, ValueError, OverflowError) as exc:
            raise TagTypeError(str(exc)) from exc

    def _write(self, tag_name: str, raw_value: Any) -> Dict[str, Any]:
        from .device import AttributeDevice

        attr = self._get_attribute(tag_name)

        if AttributeDevice.is_protected(tag_name):
            raise TagReadOnlyError(tag_name)

        cast_value = self._validate_and_cast(attr, raw_value)

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
