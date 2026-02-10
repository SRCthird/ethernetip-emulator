# Copyright 2022 Merck KGaA, Darmstadt, Germany and/or its affiliates.
# All rights reserved

# src/server/actions.py
from __future__ import annotations

import threading
import time
import weakref
from typing import Any, Callable, Dict, Optional


class AttributeActions:
    """
    Coordinate background actions on attribute-like objects (device tags).

    Typical usage:
    - Bind to an attribute class that exposes a `registry` of attributes.
    - Start workers that periodically modify attributes (e.g. increment counters).
    - React to attribute writes via `on_set` and custom handlers.
    """

    def __init__(
        self,
        *,
        sleep_fn: Callable[[float], None] = time.sleep,
        thread_factory: Callable[..., Any] | None = None,
        logger: Callable[[str], None] = (lambda _: None),
    ) -> None:
        # Event used to signal all worker threads to stop
        self._stop = threading.Event()
        # Keep references to all worker threads so they can be joined externally if needed
        self._threads: list[threading.Thread] = []
        # Weak reference to the attribute class (so we do not prevent it from being GC'd)
        self._attr_class_ref: Optional[weakref.ReferenceType[Any]] = None

        # Injectable sleep function (useful for testing)
        self._sleep = sleep_fn
        # Simple logger callback (can be replaced by a real logger)
        self._logger = logger

        # Provide a default thread factory if none is supplied
        if thread_factory is None:

            def default_thread_factory(**kwargs: Any) -> threading.Thread:
                # Create a standard Python thread with the given kwargs
                return threading.Thread(**kwargs)

            thread_factory = default_thread_factory

        # Factory used to create worker threads
        self._thread_factory = thread_factory

    def bind(self, attr_class: type) -> "AttributeActions":
        """
        Bind this actions object to an attribute class.

        The class is expected to define a `registry` mapping tag names to
        attribute instances. A weak reference is stored so that the bound class
        can still be garbage-collected.
        """
        self._attr_class_ref = weakref.ref(attr_class)
        return self

    def _get_attr_class(self) -> Optional[type]:
        """
        Resolve and return the bound attribute class, if it is still alive.

        Returns None if nothing has been bound yet, or if the weak reference
        target has been garbage-collected.
        """
        return self._attr_class_ref() if self._attr_class_ref else None

    def start_increment(
        self,
        tag_name: str,
        *,
        period: float = 1.0,
        key: Any = 0,
        start: Optional[int] = 0,
        increment: int = 1,
        wrap: Optional[int] = None,
        initial_delay: float = 1.0,
    ) -> "AttributeActions":
        """
        Start a background thread that periodically increments an attribute.

        Args:
            tag_name: Name of the attribute in `attr_class.registry`.
            period: Delay (seconds) between successive increments.
            key: Index/key used when writing to the attribute (e.g. array index).
            start: Initial value to start from; if None, read the current value.
            increment: Step to add on each period.
            wrap: If not None, apply modulo `wrap` after increment (cyclic counter).
            initial_delay: One-time delay before the worker starts updating.
        """

        def worker() -> None:
            # Worker wrapper that calls the core implementation.
            self.run_increment_worker(
                tag_name=tag_name,
                period=period,
                key=key,
                start=start,
                increment=increment,
                wrap=wrap,
                initial_delay=initial_delay,
            )

        # Create a daemon worker thread for this incrementer
        t = self._thread_factory(
            target=worker,
            daemon=True,
            name=f"{tag_name}-increment",
        )
        t.start()
        # Track the thread so callers can manage it if needed
        self._threads.append(t)
        return self

    def run_increment_worker(
        self,
        *,
        tag_name: str,
        period: float,
        key: Any,
        start: Optional[int],
        increment: int,
        wrap: Optional[int],
        initial_delay: float,
    ) -> None:
        """
        Core loop for the increment worker; meant to run inside a thread.

        This:
        - waits for an initial delay,
        - resolves the bound attribute class and the specific attribute,
        - initializes the counter (from `start` or from the current value),
        - increments the value periodically until `stop()` is called.
        """

        # Optional initial delay before we start modifying the attribute
        if initial_delay > 0:
            self._sleep(initial_delay)

        # Current counter value (None means "need to initialize from attribute")
        n: Optional[int] = start

        # Main loop: run until someone sets the stop event
        while not self._stop.is_set():
            # Resolve the bound attribute class
            attr_class = self._get_attr_class()
            if attr_class is None:
                # If class is gone or never bound, log and retry after a sleep
                self._logger(f"AttributeActions: attr_class is None for {tag_name}")
                self._sleep(period)
                continue

            # Look up the attribute in the class registry by tag name
            attr = getattr(attr_class, "registry", {}).get(tag_name)
            if attr is None:
                # Attribute missing; log and retry later
                self._logger(f"AttributeActions: attr is None for {tag_name}")
                self._sleep(period)
                continue

            # If n is not yet determined, try to read the current value from attr
            if n is None:
                try:
                    # Try indexing (e.g. array-like attribute)
                    current = attr[key]
                except Exception:
                    # Fallback to simple `.value` attribute if indexing is not supported
                    current = getattr(attr, "value", None)
                # Use 0 as default if current is falsy/None
                n = int(current or 0)

            # Increment the counter
            n += increment

            # Apply wrapping (modulo) if configured
            if wrap is not None:
                n %= wrap

            # Attempt to write back the new value
            try:
                # Prefer item assignment for array-like attributes
                attr[key] = n
            except Exception:
                # If item assignment fails, check other ways of setting the value
                if hasattr(attr, "__setitem__"):
                    # Attribute claims to support item assignment; ignore the error
                    pass
                elif hasattr(attr, "value"):
                    # Fallback to setting `.value` directly
                    setattr(attr, "value", n)

            # Wait for the next cycle
            self._sleep(period)

    def stop(self) -> None:
        """Signal all workers to stop."""
        self._stop.set()

    def on_set(self, attr: Any, key: Any, value: Any) -> None:
        """
        Dispatch logic whenever an attribute value is set.

        This method is intended to be called by `AttributeDevice.__setitem__`
        (or an equivalent mechanism) whenever an attribute is written.

        Based on `attr.name`, it routes to specific handler methods, enabling
        custom side effects when certain attributes change.
        """
        match getattr(attr, "name", None):
            # EXAMPLE:
            case "I_TEXT":
                # Delegate to a dedicated handler for I_TEXT writes
                self.I_TEXT(attr, key, value)
            case _:
                # No special handling for this attribute name
                pass

    # -------------------------------------------------------------------------
    # Custom handler(s)
    # -------------------------------------------------------------------------

    # EXAMPLE:
    def I_TEXT(self, attr: Any, key: Any, value: Any) -> None:
        """
        Example handler for attribute "I_TEXT".

        Behaviour:
        - When "I_TEXT" is written, mirror that value to "O_TEXT" in the same
          attribute class registry, if such an attribute exists.

        This demonstrates how to implement cross-attribute side effects.
        """
        # Look up the attribute registry on the class of `attr`
        registry: Dict[str, Any] = getattr(type(attr), "registry", {})
        # Find the corresponding "O_TEXT" attribute
        other = registry.get("O_TEXT")
        if other is not None:
            try:
                # Prefer item assignment (e.g. other[key] = value)
                other[key] = value
            except Exception:
                # Fallback to setting `.value` if item assignment is not supported
                if hasattr(other, "value"):
                    setattr(other, "value", value)
