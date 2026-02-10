# Copyright 2022 Merck KGaA, Darmstadt, Germany and/or its affiliates.
# All rights reserved

# src/server/device.py
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from cpppo.server.enip import device
from src.server.tag_specs import TAG_SPECS
from src.server.actions import AttributeActions


def build_argv(
    tag_specs: Iterable[Tuple[str, str, Any]],
    base_args: Optional[Sequence[str]] = None,
) -> List[str]:
    """
    Build a command-line style argv list from tag specifications.

    Each tag spec is a tuple: (name, type_spec, default).
    This converts them into strings of the form "name=type_spec" and appends
    them to an optional base argument sequence.
    """
    if base_args is None:
        # If no base args are provided, start with an empty list
        base_args = []

    # Start from a mutable copy of base_args
    argv = list(base_args)
    # Add "name=type_spec" for each tag spec
    argv.extend(f"{name}={type_spec}" for (name, type_spec, _) in tag_specs)
    return argv


def build_defaults(tag_specs: Iterable[Tuple[str, str, Any]]) -> Dict[str, Any]:
    """
    Build a mapping from tag name to its default value.

    Only include entries where a non-None default is specified in the tag spec.
    """
    return {name: default for (name, _, default) in tag_specs if default is not None}


class AttributeDevice(device.Attribute):
    """
    Extension of cpppo.server.enip.device.Attribute with:

    - A shared registry of AttributeDevice instances, keyed by tag name.
    - A shared AttributeActions instance to handle side-effect logic.
    - Automatic application of default values from TAG_SPECS.
    """

    # Global registry of all AttributeDevice instances by tag name
    registry: Dict[str, "AttributeDevice"] = {}
    # Shared actions handler for all AttributeDevice instances
    _actions: AttributeActions = AttributeActions()
    # Shared defaults built from TAG_SPECS (name -> default value)
    _defaults: Mapping[str, Any] = build_defaults(TAG_SPECS)

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
        """
        Initialize an AttributeDevice.

        Args:
            name: Tag name (used as key in the registry and default lookup).
            type_cls: Underlying data type/class for the attribute.
            defaults: Optional per-instance override of the defaults mapping.
                      Falls back to the class-level _defaults if not provided.
            actions: Optional AttributeActions instance; defaults to class-level.
            registry: Optional registry dict; defaults to the class-level registry.
            **kwargs: Additional arguments forwarded to the base Attribute ctor.
        """
        # Select defaults mapping (instance-level override or shared class-level)
        self._defaults = defaults if defaults is not None else type(self)._defaults
        # Select actions handler (instance-level override or shared class-level)
        self._actions = actions if actions is not None else type(self)._actions
        # Select registry (instance-level override or shared class-level registry)
        self._registry = registry if registry is not None else type(self).registry

        # Apply a default value for this attribute, if defined
        self._apply_default(name, kwargs)

        # Initialize the base cpppo Attribute with the possibly updated kwargs
        super().__init__(name, type_cls, **kwargs)

        # Register this instance by name so others (e.g. AttributeActions) can find it
        self._registry[name] = self

    def _apply_default(self, name: str, kwargs: Dict[str, Any]) -> None:
        """
        Inject a default value for this attribute into kwargs if available.

        The logic:
        - If the tag name has a configured default in self._defaults,
          and there is no conflicting configured default, set kwargs["default"].
        - If kwargs["default"] is a non-empty list, it is treated as an
          array-like default where the first element is replaced by the
          configured default value.
        """
        # If there is no configured default for this name, do nothing
        if name not in self._defaults:
            return

        # User-provided default passed in kwargs (if any)
        configured_default = kwargs.get("default")
        # Default value from our defaults mapping
        value = self._defaults[name]

        # If default is a list, override only the first element
        if isinstance(configured_default, list) and configured_default:
            # Copy so we don't mutate the original list
            new_default = list(configured_default)
            # Replace first element with our configured default
            new_default[0] = value
            kwargs["default"] = new_default
        else:
            # Simple (scalar) default
            kwargs["default"] = value

    def __setitem__(self, key: Any, value: Any) -> None:
        """
        Override item assignment to hook into AttributeActions.

        After writing the value using the base class implementation, this method
        notifies the actions handler so it can trigger any configured side effects
        (e.g. mirroring values, triggering counters, etc.).
        """
        # Perform the actual write using the base Attribute implementation
        super().__setitem__(key, value)
        # Notify the actions handler that this attribute was written
        self._actions.on_set(self, key, value)
