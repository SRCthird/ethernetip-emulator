# Copyright 2026 Merck KGaA, Darmstadt, Germany and/or its affiliates.
# All rights reserved

# example/basic_datatypes/actions.py
from time import sleep

from src.ethernetip_emulator.server.device import actions

@actions.string.on_change("I_TEXT")
def handle_i_text(attr, key, value) -> None:
    """
    Mirror I_TEXT.DATA -> O_TEXT.DATA, maintaining the update counter.

    Increments O_Updates (COUNTER) and O_Updates.LAZY (INT) on every write.
    When O_Updates.DN is set, writes the sentinel "Count Completed" instead.
    """
    actions.counter.increment("O_Updates")
    actions.increment.increment("O_Updates.LAZY")
    if actions.counter.is_done("O_Updates"):
        actions.string.set_val("O_TEXT", key, "Count Completed")
    else:
        actions.string.set_val("O_TEXT", key, value)

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

actions.increment.start(tag_name="O_INCR", start=32_757, wrap=actions.int.MAX)

@actions.bool.on_change("O_BOOL")
def handle_bool(attr, key, value) -> None:
    if value[0] is True:
        actions.boolarray.set_val("O_BoolArray", slice(2,3), True)
        print(actions.boolarray.get_val("O_BoolArray", slice(2,3)))
    if value[0] is False:
        actions.boolarray.set_val("O_BoolArray", slice(0,4), [False,True,False,True])
        print(actions.boolarray.get_val("O_BoolArray", slice(0,4)))
