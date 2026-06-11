# Copyright 2026 Merck KGaA, Darmstadt, Germany and/or its affiliates.
# All rights reserved

# src/server/main.py
from typing import Any, List, Tuple
from time import sleep
from cpppo.server.enip.main import main as enip_main

from src.server.device import AttributeDevice, actions
from src.server.tag_specs import tag_registry

@tag_registry.register
def _tags() -> List[Tuple[str, str, Any]]:
    return [
        # (tag_name,          type_spec,  default)
        ("I_TEXT",            "STRING",   ""),
        ("O_TEXT",            "STRING",   ""),

        ("O_INCR",            "INT",       0),
        ("O_Updates.LAZY",    "INT",       0),   # lazy counter (separate)

        # Sized integer / float types
        ("O_8Bit",            "SINT",      0),
        ("O_16Bit",           "INT",       0),
        ("O_32Bit",           "DINT",      0),
        ("O_32Bit_Float",     "REAL",      0.0),

        # Built-in composite types
        ("O_Updates",         "COUNTER",  1000),
        ("O_Timer",           "TIMER",    5000),
        ("O_String",          "STRING",   "HELLO"),
    ]


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
        if output_count_done is not None and output_count_done[key][0]:
            actions.string.set_val("O_TEXT", key, ["Count Completed"])
        else:
            actions.string.set_val("O_TEXT", key, value)
    except Exception:
        if hasattr(output_tag, "value"):
            setattr(output_tag, "value", value)


@actions.on_change("O_Timer.DN")
def handle_timer_done(attr, key, value) -> None:
    """When the timer fires, pause 10 s then disable it."""
    if not value:
        return
    registry = getattr(type(attr), "registry", {})
    timer_enabled = registry.get("O_Timer.EN")
    sleep(10)
    if timer_enabled is not None:
        timer_enabled[key] = 0


@actions.on_change("O_Updates.RES")
def handle_reset_timer(attr, key, value) -> None:
    """Reset O_Updates COUNTER when its RES bit is written."""
    registry = getattr(type(attr), "registry", {})
    counter_reset = registry.get("O_Updates.RES")
    if counter_reset is not None and counter_reset[key][0]:
        actions.counter.reset("O_Updates")

if __name__ == "__main__":
    with AttributeDevice._actions.bind(AttributeDevice) as actions:
        actions.increment.start(tag_name="O_INCR", wrap=32766)
        actions.timer.start("O_Timer", enable="O_Timer.EN")

        enip_main(
            argv=tag_registry.build_argv(base_args=["--print"]),
            attribute_class=AttributeDevice,
        )
