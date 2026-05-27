# Copyright 2026 Merck KGaA, Darmstadt, Germany and/or its affiliates.
# All rights reserved

# src/server/actions.py
from __future__ import annotations

import threading
import time
import weakref
from typing import Any, Callable, Dict, List, Optional, Union


class AttributeActions:
    """
    Coordinate background actions on attribute-like objects (device tags).

    Typical usage:
    - Bind to an attribute class that exposes a `registry` of attributes.
    - Start workers that periodically modify attributes (e.g. increment counters).
    - React to attribute writes via `on_set` and custom handlers.
    - Start counter workers that simulate PLC COUNTER behaviour (ACC, PRE, DN, OV, UN).
    - Listen for tag value changes via `on_change`.
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

        # Registry of change listeners: tag_name -> list of (callback, key_filter)
        # key_filter=None means fire for any key; otherwise only fire when key matches.
        # Callback signature: (attr, key, value) — same as on_set.
        self._listeners: Dict[
            str, List[tuple[Callable[[Any, Any, Any], None], Optional[Any]]]
        ] = {}
        # Lock protecting _listeners so on_set and on_change are thread-safe
        self._listener_lock = threading.Lock()

        # Provide a default thread factory if none is supplied
        if thread_factory is None:

            def default_thread_factory(**kwargs: Any) -> threading.Thread:
                # Create a standard Python thread with the given kwargs
                return threading.Thread(**kwargs)

            thread_factory = default_thread_factory

        # Factory used to create worker threads
        self._thread_factory = thread_factory

    def __enter__(self) -> "AttributeActions":
        """Support use as a context manager; returns self."""
        return self

    def __exit__(
        self,
        exc_type: Optional[type],
        exc_val: Optional[BaseException],
        exc_tb: Optional[Any],
    ) -> None:
        """
        Support use as a context manager.

        Signals all worker threads to stop and joins each one, ensuring a
        clean shutdown when the ``with`` block exits — whether normally or
        due to an exception. Exceptions are never suppressed.

        Example::

            with AttributeActions().bind(MyAttrClass) as actions:
                actions.start_counter("MyTag")
            # All workers have been stopped and joined here.
        """
        self.stop()
        for t in self._threads:
            t.join()


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

    # -------------------------------------------------------------------------
    # Private attribute I/O helpers
    # -------------------------------------------------------------------------

    def _read_attr(self, attr: Any, key: Any) -> Optional[int]:
        """
        Read the current value of an attribute.

        Tries item access first (array-like attributes), then falls back to
        the `.value` property.
        """
        try:
            return int(attr[key])
        except Exception:
            val = getattr(attr, "value", None)
            return int(val) if val is not None else None

    def _write_attr(self, attr: Any, key: Any, value: int) -> None:
        """
        Write a value to an attribute.

        Tries item assignment first, then falls back to setting `.value`.
        """
        try:
            attr[key] = value
        except Exception:
            if hasattr(attr, "__setitem__"):
                pass  # Item assignment is supported but failed — ignore
            elif hasattr(attr, "value"):
                setattr(attr, "value", value)

    def _lookup(self, tag_name: str) -> Optional[Any]:
        """
        Resolve a tag name to its attribute object via the bound class registry.

        Returns None if the class or tag is unavailable.
        """
        attr_class = self._get_attr_class()
        if attr_class is None:
            self._logger(f"AttributeActions: attr_class is None for {tag_name}")
            return None
        attr = getattr(attr_class, "registry", {}).get(tag_name)
        if attr is None:
            self._logger(f"AttributeActions: attr is None for {tag_name}")
        return attr

    # -------------------------------------------------------------------------
    # Change listeners
    # -------------------------------------------------------------------------

    def on_change(
        self,
        tag_name: str,
        callback: Callable[[Any, Any, Any], None],
        *,
        key: Optional[Any] = None,
    ) -> "AttributeActions":
        """
        Register a callback to be fired whenever a tag's value is written.

        The callback is invoked synchronously inside ``on_set``, which is
        called from ``AttributeDevice.__setitem__`` on every write —
        including writes from background workers.

        Args:
            tag_name: The tag to watch, e.g. ``"O_Timer.DN"``.
            callback: A callable with the signature::

                          def handler(attr: Any, key: Any, value: Any) -> None:
                              ...

                      ``attr``  — the attribute object that was written (same as in ``on_set``).
                      ``key``      — the index/key that was written.
                      ``value``    — the new value.

            key:      Optional key filter. When provided, the callback fires
                      only when the written key matches this value. When
                      ``None`` (default), the callback fires for every key.

        Returns:
            ``self`` for chaining::

                actions\
                    .on_change("O_Timer.DN", on_timer_done)\
                    .on_change("O_Updates.DN", on_updates_done)

        Example::

            def on_timer_done(attr, key, value):
                if value:
                    print(f"{tag_name}[{key}] went high — timer finished")

            actions.on_change("O_Timer.DN", on_timer_done)

            # One-shot style with a lambda:
            actions.on_change("O_Timer.DN", lambda t, k, v: print("Done!") if v else None)
        """
        with self._listener_lock:
            self._listeners.setdefault(tag_name, []).append((callback, key))
        return self

    def remove_listener(
        self,
        tag_name: str,
        callback: Callable[[Any, Any, Any], None],
    ) -> "AttributeActions":
        """
        Remove a previously registered change listener.

        If the same callable was registered multiple times (e.g. with
        different key filters), all registrations for that callable are
        removed.

        Args:
            tag_name: The tag the listener was registered on.
            callback: The callable that was passed to ``on_change``.
        """
        with self._listener_lock:
            entries = self._listeners.get(tag_name, [])
            self._listeners[tag_name] = [
                (cb, k) for cb, k in entries if cb is not callback
            ]
        return self

    def _fire_listeners(self, tag_name: str, attr: Any, key: Any, value: Any) -> None:
        """
        Invoke all registered listeners for ``tag_name``.

        Called internally from ``on_set``. Exceptions raised by individual
        callbacks are caught and forwarded to the logger so one bad callback
        cannot break the dispatch chain.
        """
        with self._listener_lock:
            entries = list(self._listeners.get(tag_name, []))

        for callback, key_filter in entries:
            if key_filter is not None and key_filter != key:
                continue
            try:
                callback(attr, key, value)
            except Exception as exc:
                self._logger(
                    f"AttributeActions: listener error for {tag_name}: {exc}"
                )

    # -------------------------------------------------------------------------
    # Increment worker
    # -------------------------------------------------------------------------

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
            self.run_increment_worker(
                tag_name=tag_name,
                period=period,
                key=key,
                start=start,
                increment=increment,
                wrap=wrap,
                initial_delay=initial_delay,
            )

        t = self._thread_factory(
            target=worker,
            daemon=True,
            name=f"{tag_name}-increment",
        )
        t.start()
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
        if initial_delay > 0:
            self._sleep(initial_delay)

        n: Optional[int] = start

        while not self._stop.is_set():
            attr_class = self._get_attr_class()
            if attr_class is None:
                self._logger(f"AttributeActions: attr_class is None for {tag_name}")
                self._sleep(period)
                continue

            attr = getattr(attr_class, "registry", {}).get(tag_name)
            if attr is None:
                self._logger(f"AttributeActions: attr is None for {tag_name}")
                self._sleep(period)
                continue

            if n is None:
                try:
                    current = attr[key]
                except Exception:
                    current = getattr(attr, "value", None)
                n = int(current or 0)

            n += increment

            if wrap is not None:
                n %= wrap

            try:
                attr[key] = n
            except Exception:
                if hasattr(attr, "__setitem__"):
                    pass
                elif hasattr(attr, "value"):
                    setattr(attr, "value", n)

            self._sleep(period)

    # -------------------------------------------------------------------------
    # Counter worker
    # -------------------------------------------------------------------------

    DINT_MAX: int = 2_147_483_647
    DINT_MIN: int = -2_147_483_648

    def start_counter(
        self,
        tag_prefix: str,
        *,
        period: float = 1.0,
        key: Any = 0,
        preset: Optional[int] = None,
        initial_delay: float = 1.0,
        enable: Optional[Union[str, Callable[[], bool]]] = None,
    ) -> "AttributeActions":
        """
        Start a background thread that simulates PLC COUNTER behaviour.

        The counter increments `<tag_prefix>.ACC` by 1 every `period` seconds
        and manages the standard COUNTER status bits:

        - **CU**  (Count-Up)  — held True while the counter is running.
        - **DN**  (Done)      — set True when ACC >= PRE; ACC is reset to 0
                                and DN is cleared on the next cycle.
        - **OV**  (Overflow)  — set True for one cycle when ACC would exceed
                                DINT_MAX; ACC wraps to 0.
        - **UN**  (Underflow) — not driven by this worker (no count-down logic);
                                left at its current value.
        - **CD**  (Count-Down)— not driven by this worker; left at its current value.

        The PRE tag is read from the registry each cycle, so it can be changed
        at runtime by an external write without restarting the worker.

        Args:
            tag_prefix:    Common prefix for the counter tags, e.g. ``"MyTag"``.
                           The worker will look up ``<tag_prefix>.PRE``,
                           ``<tag_prefix>.ACC``, ``<tag_prefix>.CU``, etc.
            period:        Seconds between successive increments.
            key:           Index/key used for all attribute reads and writes.
            preset:        Override value written to PRE on startup. If None,
                           the existing value in the registry is used.
            initial_delay: One-time delay (seconds) before the first increment.
            enable:        Optional gate that controls whether the counter
                           increments on each cycle. Accepts either:

                           - A **callable** ``() -> bool``: called each cycle;
                             the counter increments only when it returns True.
                           - A **tag name string**: the named tag is read from
                             the registry each cycle; the counter increments
                             only when the tag's value is truthy.

                           When the gate is False the worker sleeps for
                           ``period`` and tries again next cycle — ACC and all
                           status bits are left unchanged. If ``enable`` is
                           None (default), the counter always increments.
        """

        def worker() -> None:
            self.run_counter_worker(
                tag_prefix=tag_prefix,
                period=period,
                key=key,
                preset=preset,
                initial_delay=initial_delay,
                enable=enable,
            )

        t = self._thread_factory(
            target=worker,
            daemon=True,
            name=f"{tag_prefix}-counter",
        )
        t.start()
        self._threads.append(t)
        return self

    def run_counter_worker(
        self,
        *,
        tag_prefix: str,
        period: float,
        key: Any,
        preset: Optional[int],
        initial_delay: float,
        enable: Optional[Union[str, Callable[[], bool]]] = None,
    ) -> None:
        """
        Core loop for the counter worker; meant to run inside a thread.

        Resolves tags as ``<tag_prefix>.ACC``, ``<tag_prefix>.PRE``, etc.
        Runs until ``stop()`` is called.
        """
        acc_tag = f"{tag_prefix}.ACC"
        pre_tag = f"{tag_prefix}.PRE"
        cu_tag  = f"{tag_prefix}.CU"
        dn_tag  = f"{tag_prefix}.DN"
        ov_tag  = f"{tag_prefix}.OV"

        if initial_delay > 0:
            self._sleep(initial_delay)

        # Write the preset override once at startup, if provided
        if preset is not None:
            pre_attr = self._lookup(pre_tag)
            if pre_attr is not None:
                self._write_attr(pre_attr, key, preset)

        # Set CU = True: this worker is a count-up counter
        cu_attr = self._lookup(cu_tag)
        if cu_attr is not None:
            self._write_attr(cu_attr, key, 1)

        # Read the current ACC so we resume correctly if the server was already running
        acc_attr = self._lookup(acc_tag)
        acc: int = self._read_attr(acc_attr, key) if acc_attr is not None else 0

        while not self._stop.is_set():
            # Re-resolve attrs each cycle so late binding and hot-reload work correctly
            acc_attr = self._lookup(acc_tag)
            pre_attr = self._lookup(pre_tag)
            dn_attr  = self._lookup(dn_tag)
            ov_attr  = self._lookup(ov_tag)

            if acc_attr is None or pre_attr is None:
                # Essential tags not available yet — wait and retry
                self._sleep(period)
                continue

            # Read the live preset (supports runtime changes to PRE)
            pre: int = self._read_attr(pre_attr, key) or 0

            # --- Enable gate check ---
            # Evaluate the gate before doing any work this cycle.
            if enable is not None:
                if callable(enable):
                    # Callable gate: call it and check the result
                    gate_open = bool(enable())
                else:
                    # Tag-name gate: read the named tag from the registry
                    gate_attr = self._lookup(enable)
                    gate_open = bool(self._read_attr(gate_attr, key)) if gate_attr is not None else False

                if not gate_open:
                    # Gate is closed — skip this cycle entirely
                    self._sleep(period)
                    continue

            # --- Overflow guard: ACC is at the DINT ceiling ---
            if acc >= self.DINT_MAX:
                if ov_attr is not None:
                    self._write_attr(ov_attr, key, 1)
                acc = 0
                self._write_attr(acc_attr, key, acc)
                self._sleep(period)
                # Clear OV on the next cycle
                if ov_attr is not None:
                    self._write_attr(ov_attr, key, 0)
                continue

            # --- Increment ACC ---
            acc += 1
            self._write_attr(acc_attr, key, acc)

            # --- Done check: ACC has reached or passed PRE ---
            if pre > 0 and acc >= pre:
                if dn_attr is not None:
                    self._write_attr(dn_attr, key, 1)
                self._sleep(period)
                # Reset ACC and clear DN after one cycle
                acc = 0
                self._write_attr(acc_attr, key, acc)
                if dn_attr is not None:
                    self._write_attr(dn_attr, key, 0)
                continue

            self._sleep(period)

        # Worker is stopping — clear CU to indicate the counter is no longer running
        cu_attr = self._lookup(cu_tag)
        if cu_attr is not None:
            self._write_attr(cu_attr, key, 0)

    # -------------------------------------------------------------------------
    # Counter manual controls
    # -------------------------------------------------------------------------

    def counter_increment(self, tag_prefix: str, *, key: Any = 0) -> None:
        """
        Manually increment the counter's ACC by 1.

        Mirrors the logic of the counter worker for a single step:
        - If ACC would exceed DINT_MAX, OV is set and ACC wraps to 0.
        - If ACC reaches PRE, DN is set and ACC resets to 0.
        - Otherwise ACC is incremented and all status bits are left unchanged.

        This is safe to call concurrently with a running counter worker.
        """
        acc_attr = self._lookup(f"{tag_prefix}.ACC")
        pre_attr = self._lookup(f"{tag_prefix}.PRE")
        dn_attr  = self._lookup(f"{tag_prefix}.DN")
        ov_attr  = self._lookup(f"{tag_prefix}.OV")

        if acc_attr is None or pre_attr is None:
            self._logger(f"AttributeActions.counter_increment: essential tags missing for {tag_prefix}")
            return

        acc = self._read_attr(acc_attr, key) or 0
        pre = self._read_attr(pre_attr, key) or 0

        # Overflow guard
        if acc >= self.DINT_MAX:
            if ov_attr is not None:
                self._write_attr(ov_attr, key, 1)
            acc = 0
            self._write_attr(acc_attr, key, acc)
            return

        acc += 1
        self._write_attr(acc_attr, key, acc)

        # Clear any leftover OV from a previous overflow
        if ov_attr is not None:
            self._write_attr(ov_attr, key, 0)

        # Done check
        if pre > 0 and acc >= pre:
            if dn_attr is not None:
                self._write_attr(dn_attr, key, 1)

    def counter_decrement(self, tag_prefix: str, *, key: Any = 0) -> None:
        """
        Manually decrement the counter's ACC by 1.

        - If ACC would go below DINT_MIN, UN is set and ACC wraps to 0.
        - DN is cleared if ACC drops below PRE.
        - Otherwise ACC is decremented and all other status bits are left unchanged.

        This is safe to call concurrently with a running counter worker.
        """
        acc_attr = self._lookup(f"{tag_prefix}.ACC")
        pre_attr = self._lookup(f"{tag_prefix}.PRE")
        dn_attr  = self._lookup(f"{tag_prefix}.DN")
        un_attr  = self._lookup(f"{tag_prefix}.UN")

        if acc_attr is None:
            self._logger(f"AttributeActions.counter_decrement: ACC tag missing for {tag_prefix}")
            return

        acc = self._read_attr(acc_attr, key) or 0
        pre = self._read_attr(pre_attr, key) or 0 if pre_attr is not None else 0

        # Underflow guard
        if acc <= self.DINT_MIN:
            if un_attr is not None:
                self._write_attr(un_attr, key, 1)
            acc = 0
            self._write_attr(acc_attr, key, acc)
            return

        acc -= 1
        self._write_attr(acc_attr, key, acc)

        # Clear any leftover UN
        if un_attr is not None:
            self._write_attr(un_attr, key, 0)

        # Clear DN if ACC has dropped back below PRE
        if dn_attr is not None and pre > 0 and acc < pre:
            self._write_attr(dn_attr, key, 0)

    def counter_reset(self, tag_prefix: str, *, key: Any = 0) -> None:
        """
        Reset the counter to its initial state.

        Writes:
        - ACC = 0
        - DN  = 0
        - OV  = 0
        - UN  = 0

        PRE and CU/CD are intentionally left unchanged so that a running
        counter worker can resume counting toward the same preset.
        """
        for tag, value in [
            (f"{tag_prefix}.ACC", 0),
            (f"{tag_prefix}.DN",  0),
            (f"{tag_prefix}.OV",  0),
            (f"{tag_prefix}.UN",  0),
        ]:
            attr = self._lookup(tag)
            if attr is not None:
                self._write_attr(attr, key, value)

    # -------------------------------------------------------------------------
    # Timer worker
    # -------------------------------------------------------------------------

    def start_timer(
        self,
        tag_prefix: str,
        *,
        period: float = 0.1,
        key: Any = 0,
        preset_ms: Optional[int] = None,
        initial_delay: float = 1.0,
        enable: Optional[Union[str, Callable[[], bool]]] = None,
    ) -> "AttributeActions":
        """
        Start a background thread that simulates a PLC TON (Timer On-Delay).

        The timer accumulates elapsed time in milliseconds in ACC and manages
        the standard TIMER status bits:

        - **EN** (Enable)       — set True when the enable gate is active.
        - **TT** (Timer Timing) — True while EN is set and ACC < PRE.
        - **DN** (Done)         — set True when ACC >= PRE; stays True while
                                  EN remains active (mirroring TON behaviour).

        ACC accumulates real elapsed milliseconds via ``time.monotonic()``.
        When EN drops the timer resets: ACC = 0, TT = 0, DN = 0, EN = 0.
        PRE is read each cycle so it can be changed at runtime.

        Args:
            tag_prefix:    Common prefix, e.g. ``"Timer"``.
            period:        Poll interval in seconds (default 0.1 s = 100 ms).
            key:           Index/key for all attribute reads and writes.
            preset_ms:     Override value (ms) written to PRE on startup.
            initial_delay: One-time delay before the worker starts.
            enable:        Gate — callable, tag name string, or None (always on).
        """
        def worker() -> None:
            self.run_timer_worker(
                tag_prefix=tag_prefix,
                period=period,
                key=key,
                preset_ms=preset_ms,
                initial_delay=initial_delay,
                enable=enable,
            )

        t = self._thread_factory(
            target=worker,
            daemon=True,
            name=f"{tag_prefix}-timer",
        )
        t.start()
        self._threads.append(t)
        return self

    def run_timer_worker(
        self,
        *,
        tag_prefix: str,
        period: float,
        key: Any,
        preset_ms: Optional[int],
        initial_delay: float,
        enable: Optional[Union[str, Callable[[], bool]]] = None,
    ) -> None:
        """
        Core loop for the timer worker; meant to run inside a thread.

        Resolves tags as ``<tag_prefix>.PRE``, ``<tag_prefix>.ACC``, etc.
        Runs until ``stop()`` is called.
        """
        acc_tag = f"{tag_prefix}.ACC"
        pre_tag = f"{tag_prefix}.PRE"
        en_tag  = f"{tag_prefix}.EN"
        tt_tag  = f"{tag_prefix}.TT"
        dn_tag  = f"{tag_prefix}.DN"

        if initial_delay > 0:
            self._sleep(initial_delay)

        if preset_ms is not None:
            pre_attr = self._lookup(pre_tag)
            if pre_attr is not None:
                self._write_attr(pre_attr, key, preset_ms)

        was_enabled = False
        t_start: Optional[float] = None

        while not self._stop.is_set():
            acc_attr = self._lookup(acc_tag)
            pre_attr = self._lookup(pre_tag)
            en_attr  = self._lookup(en_tag)
            tt_attr  = self._lookup(tt_tag)
            dn_attr  = self._lookup(dn_tag)

            if acc_attr is None or pre_attr is None:
                self._sleep(period)
                continue

            # --- Evaluate enable gate ---
            if enable is None:
                gate_open = True
            elif callable(enable):
                gate_open = bool(enable())
            else:
                gate_attr = self._lookup(enable)
                gate_open = bool(self._read_attr(gate_attr, key)) if gate_attr is not None else False

            # --- Falling edge: gate just closed — reset timer ---
            if was_enabled and not gate_open:
                t_start = None
                for attr, val in [
                    (acc_attr, 0), (en_attr, 0), (tt_attr, 0), (dn_attr, 0),
                ]:
                    if attr is not None:
                        self._write_attr(attr, key, val)
                was_enabled = False
                self._sleep(period)
                continue

            if not gate_open:
                self._sleep(period)
                continue

            # --- Rising edge: gate just opened — start timing ---
            if not was_enabled:
                t_start = time.monotonic()
                was_enabled = True
                if en_attr is not None:
                    self._write_attr(en_attr, key, 1)

            pre = self._read_attr(pre_attr, key) or 0
            elapsed_ms = int((time.monotonic() - t_start) * 1000) if t_start is not None else 0
            acc = min(elapsed_ms, pre) if pre > 0 else elapsed_ms
            self._write_attr(acc_attr, key, acc)

            if pre > 0 and elapsed_ms >= pre:
                if tt_attr is not None:
                    self._write_attr(tt_attr, key, 0)
                if dn_attr is not None:
                    self._write_attr(dn_attr, key, 1)
            else:
                if tt_attr is not None:
                    self._write_attr(tt_attr, key, 1)
                if dn_attr is not None:
                    self._write_attr(dn_attr, key, 0)

            self._sleep(period)

        # Worker stopping — clean up all timer bits
        for tag in [acc_tag, en_tag, tt_tag, dn_tag]:
            attr = self._lookup(tag)
            if attr is not None:
                self._write_attr(attr, key, 0)

    # -------------------------------------------------------------------------
    # Timer manual controls
    # -------------------------------------------------------------------------

    def timer_reset(self, tag_prefix: str, *, key: Any = 0) -> None:
        """
        Manually reset a timer to its initial state.

        Writes ACC = 0, EN = 0, TT = 0, DN = 0. PRE is left unchanged.
        Safe to call while a timer worker is running.
        """
        for tag in [
            f"{tag_prefix}.ACC",
            f"{tag_prefix}.EN",
            f"{tag_prefix}.TT",
            f"{tag_prefix}.DN",
        ]:
            attr = self._lookup(tag)
            if attr is not None:
                self._write_attr(attr, key, 0)

    # -------------------------------------------------------------------------
    # Lifecycle
    # -------------------------------------------------------------------------

    def stop(self) -> None:
        """Signal all workers to stop."""
        self._stop.set()

    # -------------------------------------------------------------------------
    # on_set dispatcher
    # -------------------------------------------------------------------------

    def on_set(self, attr: Any, key: Any, value: Any) -> None:
        """
        Dispatch logic whenever an attribute value is set.

        Called by ``AttributeDevice.__setitem__`` on every write. Fires
        registered ``on_change`` listeners for the tag, then routes to any
        named handler method via the match block below.
        """
        tag_name = getattr(attr, "name", None)

        # Fire all on_change listeners registered for this tag
        if tag_name is not None:
            self._fire_listeners(tag_name, attr, key, value)
