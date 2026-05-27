# Copyright 2026 Merck KGaA, Darmstadt, Germany and/or its affiliates.
# All rights reserved

from cpppo.server.enip.main import main as enip_main
from src.server.device import AttributeDevice
from src.server.tag_specs import TAG_ARGV

def I_TEXT(attr, key, value) -> None:
    """
    Handler for attribute "I_TEXT".

    Mirrors the written value to "O_TEXT", counting each update via
    the O_Updates counter. Once the counter is done, O_TEXT is locked
    to "Count Completed".
    """
    registry = getattr(type(attr), "registry", {})
    output_tag = registry.get("O_TEXT")
    output_count_done = registry.get("O_Updates.DN")
    if output_tag is not None:
        try:
            AttributeDevice._actions.counter_increment("O_Updates")
            if output_count_done is not None and output_count_done[key][0]:
                output_tag[key] = ["Count Completed"]
            else:
                output_tag[key] = value
        except Exception:
            if hasattr(output_tag, "value"):
                setattr(output_tag, "value", value)

def on_timer_done(attr, key, value):
    if value:
        registry = getattr(type(attr), "registry", {})
        timer_enabled = registry.get("O_Timer.EN")
        if timer_enabled is not None:
            timer_enabled[key] = 0

if __name__ == "__main__":
    # EXAMPLE:
    # AttributeDevice._actions.bind(AttributeDevice).start_increment(tag_name="O_INCR")
    AttributeDevice._actions.bind(AttributeDevice).start_timer("O_Timer", enable="O_Timer.EN")
    # AttributeDevice._actions.bind(AttributeDevice).on_change("O_Timer.DN", on_timer_done)
    AttributeDevice._actions.bind(AttributeDevice).on_change("I_TEXT", I_TEXT)
    
    enip_main(
        argv=TAG_ARGV,
        attribute_class=AttributeDevice,
    )
