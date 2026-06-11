# Copyright 2026 Merck KGaA, Darmstadt, Germany and/or its affiliates.
# All rights reserved

from typing import Any, List, Tuple
from cpppo.server.enip.main import main as enip_main
from time import sleep
from src.server.device import AttributeDevice
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

def I_TEXT(attr, key, value) -> None:
    registry = getattr(type(attr), "registry", {})
    output_tag = registry.get("O_TEXT.DATA")
    output_count_done = registry.get("O_Updates.DN")
    if output_tag is not None:
        try:
            AttributeDevice._actions.counter.increment("O_Updates")
            AttributeDevice._actions.increment.increment("O_Updates.LAZY")
            if output_count_done is not None and output_count_done[key][0]:
                AttributeDevice._actions.string.set_val("O_TEXT", key, ["Count Completed"])
            else:
                AttributeDevice._actions.string.set_val("O_TEXT", key, value)
        except Exception:
            if hasattr(output_tag, "value"):
                setattr(output_tag, "value", value)

def on_timer_done(attr, key, value):
    if value:
        registry = getattr(type(attr), "registry", {})
        timer_enabled = registry.get("O_Timer.EN")
        sleep(10)
        if timer_enabled is not None:
            timer_enabled[key] = 0

def reset_timer(attr, key, value):
    registry = getattr(type(attr), "registry", {})
    counter_reset = registry.get("O_Updates.RES")
    if counter_reset is not None and counter_reset[key][0]:
        AttributeDevice._actions.counter.reset("O_Updates")

if __name__ == "__main__":
    # EXAMPLE:
    with AttributeDevice._actions.bind(AttributeDevice) as actions:
        actions.increment.start(tag_name="O_INCR", wrap=32766)
        actions.timer.start("O_Timer", enable="O_Timer.EN")
        actions.on_change("O_Timer.DN", on_timer_done)
        actions.on_change("I_TEXT.DATA", I_TEXT)
        actions.on_change("O_Updates.RES", reset_timer)
    
        enip_main(
            argv=tag_registry.build_argv(base_args=["--print"]),
            attribute_class=AttributeDevice,
        )
