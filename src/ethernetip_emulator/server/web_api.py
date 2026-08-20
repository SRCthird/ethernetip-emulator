# Copyright 2026 Merck KGaA, Darmstadt, Germany and/or its affiliates.
# All rights reserved

# src/ethernetip_emulator/server/web_api.py
from __future__ import annotations

import functools
import json
import logging
import threading
from collections import defaultdict
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, TYPE_CHECKING
from wsgiref.simple_server import WSGIServer, WSGIRequestHandler, make_server

import web

if TYPE_CHECKING:
    from .actions import AttributeActions
    from .device import AttributeDevice
    from .tag_specs import TagRegistry

log = logging.getLogger(__name__)


class ApiError(Exception):
    status = "500 Internal Server Error"
    code = "internal_error"

    def as_body(self) -> Dict[str, str]:
        return {"error": self.code, "message": str(self)}


class TagNotFoundError(ApiError, KeyError):
    status = "404 Not Found"
    code = "tag_not_found"

    def __init__(self, tag_name: str) -> None:
        super().__init__(f"unknown tag {tag_name!r}")


class TagReadOnlyError(ApiError, PermissionError):
    status = "403 Forbidden"
    code = "tag_read_only"

    def __init__(self, tag_name: str) -> None:
        super().__init__(f"tag {tag_name!r} is read-only")


class TagTypeError(ApiError, ValueError):
    status = "400 Bad Request"
    code = "type_mismatch"


class DatatypeNotFoundError(ApiError, KeyError):
    status = "404 Not Found"
    code = "datatype_not_found"

    def __init__(self, type_name: str) -> None:
        super().__init__(f"unknown datatype {type_name!r}")


class BadRequestError(ApiError):
    status = "400 Bad Request"
    code = "bad_request"


class _QuietWSGIRequestHandler(WSGIRequestHandler):
    def log_message(self, format, *args):
        log.debug("%s - %s", self.address_string(), format % args)


def _respond(status: str, body: Mapping[str, Any]) -> str:
    web.ctx.status = status
    web.header("Content-Type", "application/json")
    return json.dumps(body)


def endpoint(func: Callable[..., Mapping[str, Any]]) -> Callable[..., str]:

    @functools.wraps(func)
    def wrapper(*args, **kwargs) -> str:
        try:
            return _respond("200 OK", func(*args, **kwargs))
        except ApiError as exc:
            return _respond(exc.status, exc.as_body())
        except Exception as exc:
            log.exception("unhandled error in WebApi request")
            return _respond(
                "500 Internal Server Error",
                {"error": "internal_error", "message": str(exc)},
            )

    return wrapper


class WebApi:

    _URLS = (
        "/health",
        "health",
        "/tags",
        "tags",
        "/tag/(.+)",
        "tag",
        "/datatypes/?",
        "datatypes",
        "/datatype/(.+)",
        "datatype",
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

    @staticmethod
    def _device_cls() -> type["AttributeDevice"]:
        from .device import AttributeDevice

        return AttributeDevice

    def _type_map(self) -> Dict[str, str]:
        return self.tag_registry.build_type_map()

    def _known_types(self) -> List[str]:
        return list(getattr(self.actions._datatypes.get("type"), "_types", ()))

    @staticmethod
    def _parser_name(attr: "AttributeDevice") -> Optional[str]:
        parser = getattr(attr, "parser", None)
        return type(parser).__name__ if parser is not None else None

    def _lookup(self, tag_name: str) -> "AttributeDevice":
        attr = self.actions._lookup(tag_name)
        if attr is None:
            raise TagNotFoundError(tag_name)
        return attr

    def _tag_types(self, tags: Iterable[str]) -> Dict[str, Optional[str]]:
        return {tag: self._parser_name(self._lookup(tag)) for tag in tags}

    def _datatype_groups(self, include_empty: bool = False) -> List[Dict[str, Any]]:
        grouped: Dict[str, Dict[str, Optional[str]]] = defaultdict(dict)
        for tag, group in self._type_map().items():
            grouped[group][tag] = self._parser_name(self._lookup(tag))

        known = self._known_types()
        order = known + [g for g in grouped if g not in known]
        return [
            {"name": group, "tags": grouped.get(group, {})}
            for group in order
            if include_empty or grouped.get(group)
        ]

    def _datatype_group(self, name: str) -> Dict[str, Any]:
        tags = [tag for tag, group in self._type_map().items() if group == name]
        if not tags and name not in self._known_types():
            raise DatatypeNotFoundError(name)
        return {"name": name, "tags": self._tag_types(tags)}

    def _serialize(
        self,
        name: str,
        attr: "AttributeDevice",
        type_map: Optional[Mapping[str, str]] = None,
    ) -> Dict[str, Any]:
        if type_map is None:
            type_map = self._type_map()

        try:
            raw = attr.value
        except AttributeError:
            value = None
        else:
            value = list(raw) if isinstance(raw, (list, tuple)) else raw

        return {
            "name": name,
            "value": value,
            "group": type_map.get(name),
            "type": self._parser_name(attr),
            "readonly": self._device_cls().is_protected(name),
        }

    def _serialize_all(self) -> List[Dict[str, Any]]:
        type_map = self._type_map()
        return [
            self._serialize(name, attr, type_map)
            for name, attr in self.actions._registry().items()
        ]

    def _validator_for(self, attr: "AttributeDevice") -> Callable[[Any], Any]:
        type_name = self._parser_name(attr)
        if type_name is None:
            raise TagTypeError("tag has no parser and cannot be written")

        type_attr = self.actions._datatypes.get(type_name.lower())
        validator = getattr(type_attr, "type_validator", None)
        if validator is None:
            raise TagTypeError(f"type {type_name!r} has no type_validator method")
        return validator

    def _write(self, tag_name: str, raw_value: Any) -> Dict[str, Any]:
        attr = self._lookup(tag_name)
        if self._device_cls().is_protected(tag_name):
            raise TagReadOnlyError(tag_name)

        validator = self._validator_for(attr)

        if isinstance(raw_value, list):
            for index, item in enumerate(validator(v) for v in raw_value):
                attr[index] = item
        else:
            attr[slice(0, 1)] = [validator(raw_value)]

        return self._serialize(tag_name, attr)

    @staticmethod
    def _read_value_payload() -> Any:
        raw_body = web.data()
        try:
            payload = json.loads(raw_body) if raw_body else None
        except json.JSONDecodeError as exc:
            raise BadRequestError(f"request body is not valid JSON: {exc}") from exc
        if not isinstance(payload, dict) or "value" not in payload:
            raise BadRequestError('request body must be JSON: {"value": <...>}')
        return payload["value"]

    def _build_application(self) -> "web.application":
        api = self

        class health:
            @endpoint
            def GET(self) -> Dict[str, Any]:
                return {"status": "ok"}

        class tags:
            @endpoint
            def GET(self) -> Dict[str, Any]:
                return {"tags": api._serialize_all()}

        class tag:
            @endpoint
            def GET(self, tag_name: str) -> Dict[str, Any]:
                return api._serialize(tag_name, api._lookup(tag_name))

            @endpoint
            def PUT(self, tag_name: str) -> Dict[str, Any]:
                return api._write(tag_name, api._read_value_payload())

            POST = PUT

        class datatypes:
            @endpoint
            def GET(self) -> Dict[str, Any]:
                return {"datatypes": api._datatype_groups()}

        class datatype:
            @endpoint
            def GET(self, type_name: str) -> Dict[str, Any]:
                return api._datatype_group(type_name)

        handlers = {
            "health": health,
            "tags": tags,
            "tag": tag,
            "datatypes": datatypes,
            "datatype": datatype,
        }
        return web.application(self._URLS, handlers, autoreload=False)

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
            server, thread = self._server, self._server_thread
            self._server = self._server_thread = None

        if server is not None:
            server.shutdown()
            server.server_close()
        if thread is not None:
            thread.join(timeout=5)
            if thread.is_alive():
                log.warning("WebApi server thread did not stop within 5s")

    def __enter__(self) -> "WebApi":
        self.start()
        return self

    def __exit__(self, *exc_info) -> None:
        self.stop()
