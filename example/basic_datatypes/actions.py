# Copyright 2026 Merck KGaA, Darmstadt, Germany and/or its affiliates.
# All rights reserved

# example/basic_datatypes/actions.py
from time import sleep

from ethernetip_emulator.server.device import AttributeDevice, actions


@actions.string.on_change("I_TEXT")
def handle_i_text(attr, key, value) -> None:
    if value[0] == "Shutdown":
        AttributeDevice.shutdown()
    actions.counter.increment("O_Updates")
    actions.increment.increment("O_Updates.LAZY")
    if actions.counter.is_done("O_Updates"):
        actions.string.set_val("O_TEXT", "Count Completed")
    else:
        actions.string.set_val("O_TEXT", value)


@actions.usintarray.on_change("O_UsintArray", key=slice(0, 1))
def node_1_changed(attr, key, value):
    print(f"Node 1 has changed: {value[0]}")


@actions.usintarray.on_change("O_UsintArray", key=slice(1, 2))
def node_2_changed(attr, key, value):
    print(f"Node 2 has changed: {value[0]}")


@actions.usintarray.on_change("O_UsintArray", key=slice(2, 3))
def node_3_changed(attr, key, value):
    print(f"Node 3 has changed: {value[0]}")


@actions.usintarray.on_change("O_UsintArray", key=slice(3, 4))
def node_4_changed(attr, key, value):
    print(f"Node 4 has changed: {value[0]}")


@actions.usintarray.on_change("O_UsintArray", key=slice(0, 4))
def nodes_changed(attr, key, value):
    print(f"All Nodes have changed: {value[0]}")


@actions.timer.is_done("O_Timer")
def handle_timer_done(attr, key, value) -> None:
    actions.bool.set_val("O_Timer.EN", False)


actions.increment.start(tag_name="O_INCR", start=0, wrap=actions.int.MAX)


@actions.bool.on_change("O_BOOL", defer=True)
def handle_bool(attr, key, value) -> None:
    if value[0]:
        actions.bool.set_val("O_BOOL", False)

        print(actions.boolarray.get_val("O_BoolArray"))
        actions.boolarray.set_val("O_BoolArray", [0, 0, 0, 0])
        print(f"Size of boolarray: {actions.boolarray.size('O_BoolArray')}")
        actions.boolarray.toggle_bit("O_BoolArray", 0)
        actions.boolarray.append("O_BoolArray", 1)
        actions.boolarray.prepend("O_BoolArray", 1)
        print(f"Final list: {actions.boolarray.get_val('O_BoolArray')}")
        actions.boolarray.clear("O_BoolArray")
