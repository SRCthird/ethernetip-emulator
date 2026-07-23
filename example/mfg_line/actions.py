# Copyright 2026 Merck KGaA, Darmstadt, Germany and/or its affiliates.
# All rights reserved

# example/mfg_line/actions.py

import random
from time import sleep
from ethernetip_emulator.server.device import actions


@actions.sint.on_change("I_SerialNumber")
def unit_loaded(attr, key, value) -> None:
    ln = actions.string.get_val("I_LotNumber")
    cn = actions.string.get_val("I_CatalogNumber")
    if ln is None or cn is None:
        return
    if ln == "" or cn == "":
        return
    if actions.mfgcontainer.is_empty("O_Container"):
        actions.mfgcontainer.set_container("O_Container", value[0], ln, cn)
    else:
        actions.mfgcontainer.set_sn("O_Container", value[0])


@actions.bool.on_change("I_ClearLine", defer=True)
def clear_line(attr, key, value) -> None:
    if not value[0]:
        return
    actions.mfgcontainer.clear("O_Container")
    actions.uintarray.clear("O_Passed")
    actions.uintarray.clear("O_Failed")
    actions.string.set_val("I_LotNumber", "")
    actions.string.set_val("I_CatalogNumber", "")
    actions.uint.set_val("I_SerialNumber", 0)
    actions.bool.set_val("I_ClearLine", False)


@actions.bool.on_change("I_ProcessUnit", defer=True)
def process_unit(attr, key, value) -> None:
    if not value[0]:
        return
    actions.bool.set_val("I_ProcessUnit", False)
    if True in actions.boolarray.get_val("O_Step"):
        print("Step Fault, try again later")
        return
    sn, ssn, ln, cn, flt = actions.mfgcontainer.get_container("O_Container")
    if ssn is None or ln is None or cn is None or flt is None:
        print("Container not found")
        return
    if sn == 0 or ln == "" or cn == "":
        print("Container values must not be empty")
        return
    if actions.uintarray.is_full("O_Failed") or actions.uintarray.is_full("O_Passed"):
        print("Line is full, please clear before processing next part")
        return
    if not process_steps():
        print("Unit failed")
        actions.uintarray.append("O_Failed", sn)
        return
    actions.uintarray.append("O_Passed", sn)


def process_steps() -> bool:
    actions.boolarray.set_val("O_Step", [1], slice(0, 1))
    if not process_step1():
        actions.mfgcontainer.set_flt("O_Container", True)
        actions.boolarray.set_val("O_Step", [0, 0, 0])
        return False
    sleep(2)
    actions.boolarray.set_val("O_Step", [1], slice(1, 2))
    if not process_step2():
        actions.mfgcontainer.set_flt("O_Container", True)
        actions.boolarray.set_val("O_Step", [0, 0, 0])
        return False
    sleep(2)
    actions.boolarray.set_val("O_Step", [1], slice(2, 3))
    if not process_step3():
        actions.mfgcontainer.set_flt("O_Container", True)
        actions.boolarray.set_val("O_Step", [0, 0, 0])
        return False
    sleep(2)
    actions.boolarray.set_val("O_Step", [0, 0, 0])
    return True


def process_step1() -> bool:
    pass_rate = 98
    return random.randint(1, 100) < pass_rate


def process_step2():
    pass_rate = 97
    return random.randint(1, 100) < pass_rate


def process_step3():
    pass_rate = 80
    return random.randint(1, 100) < pass_rate
