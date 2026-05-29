# Copyright 2026 Merck KGaA, Darmstadt, Germany and/or its affiliates.
# All rights reserved

from cpppo.server.enip.main import main as enip_main
from time import sleep
from src.server.device import AttributeDevice
from src.server.tag_specs import TAG_ARGV

def I_TEXT(attr, key, value) -> None:
    registry = getattr(type(attr), "registry", {})
    output_tag = registry.get("O_TEXT")
    output_count_done = registry.get("O_Updates.DN")
    if output_tag is not None:
        try:
            AttributeDevice._actions.counter.increment("O_Updates")
            AttributeDevice._actions.increment.increment("O_Updates.LAZY")
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
        actions.on_change("I_TEXT", I_TEXT)
        actions.on_change("O_Updates.RES", reset_timer)
    
        enip_main(
            argv=TAG_ARGV,
            attribute_class=AttributeDevice,
        )
