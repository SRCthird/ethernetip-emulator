# Copyright 2026 Merck KGaA, Darmstadt, Germany and/or its affiliates.
# All rights reserved

# src/server/device.py
from typing import Any, Dict, Mapping, Optional

from cpppo.server.enip import device
from src.ethernetip_emulator.server.tag_specs import tag_registry
from src.ethernetip_emulator.server.actions import AttributeActions


class AttributeDevice(device.Attribute):
    registry: Dict[str, "AttributeDevice"] = {}
    _actions: AttributeActions = AttributeActions()
    _defaults: Optional[Mapping[str, Any]] = None

    @classmethod
    def _ensure_defaults(cls) -> None:
        if cls._defaults is None:
            cls._defaults = {
                name: default
                for name, _, default in tag_registry.build()
                if default is not None
            }

    def __init__(
        self,
        name: str,
        type_cls: Any,
        *,
        defaults: Optional[Mapping[str, Any]] = None,
        actions: Optional[AttributeActions] = None,
        registry: Optional[Dict[str, "AttributeDevice"]] = None,
        **kwargs: Any,
    ) -> None:
        type(self)._ensure_defaults()
        self._defaults = defaults if defaults is not None else type(self)._defaults
        self._actions = actions if actions is not None else type(self)._actions
        self._registry = registry if registry is not None else type(self).registry
        self._apply_default(name, kwargs)
        super().__init__(name, type_cls, **kwargs)
        self._registry[name] = self

    def _apply_default(self, name: str, kwargs: Dict[str, Any]) -> None:
        if self._defaults is None:
            return
        if name not in self._defaults:
            return

        configured_default = kwargs.get("default")
        value = self._defaults[name]

        if isinstance(value, list):
            if isinstance(configured_default, list) and configured_default:
                new_default = list(configured_default)
                for i, v in enumerate(value):
                    if i < len(new_default):
                        new_default[i] = v
                kwargs["default"] = new_default
            else:
                kwargs["default"] = value
        elif isinstance(configured_default, list) and configured_default:
            new_default = list(configured_default)
            new_default[0] = value
            kwargs["default"] = new_default
        else:
            kwargs["default"] = value


    def __setitem__(self, key: Any, value: Any) -> None:
        super().__setitem__(key, value)
        self._actions.on_set(self, key, value)

    @classmethod
    def reset_defaults(cls) -> None:
        cls._defaults = None
        cls.registry.clear()

actions = AttributeDevice._actions
