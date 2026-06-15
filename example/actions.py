# Copyright 2026 Merck KGaA, Darmstadt, Germany and/or its affiliates.
# All rights reserved

# scope/actions.py
from time import sleep

from src.server.device import actions

@actions.on_change("I_TEXT.DATA")
def handle_i_text(attr, key, value) -> None:
    """
    Mirror I_TEXT.DATA -> O_TEXT.DATA, maintaining the update counter.

    Increments O_Updates (COUNTER) and O_Updates.LAZY (INT) on every write.
    When O_Updates.DN is set, writes the sentinel "Count Completed" instead.
    """
    registry = getattr(type(attr), "registry", {})
    output_tag        = registry.get("O_TEXT.DATA")
    output_count_done = registry.get("O_Updates.DN")

    if output_tag is None:
        return

    try:
        actions.counter.increment("O_Updates")
        actions.increment.increment("O_Updates.LAZY")
        # if actions.counter.is_done("O_Updates"):
        if output_count_done is not None and output_count_done[key][0]:
            actions.string.set_val("O_TEXT", key, ["Count Completed"])
        else:
            actions.string.set_val("O_TEXT", key, value)
    except Exception:
        if hasattr(output_tag, "value"):
            setattr(output_tag, "value", value)

@actions.timer.is_done("O_Timer")
def handle_timer_done(attr, key, value) -> None:
    """When the timer fires, pause 10 s then disable it."""
    if not value:
        return
    registry = getattr(type(attr), "registry", {})
    timer_enabled = registry.get("O_Timer.EN")
    sleep(10)
    if timer_enabled is not None:
        timer_enabled[key] = 0

actions.increment.start(tag_name="O_INCR", wrap=32766)
