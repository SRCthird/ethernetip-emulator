# Copyright 2026 Merck KGaA, Darmstadt, Germany and/or its affiliates.
# All rights reserved

# src/server/datatype/mfgcontainer.py
from __future__ import annotations
from typing import TYPE_CHECKING, Any, Tuple
from src.server.tag_specs import tag_registry
from src.server.device import actions

if TYPE_CHECKING:
    from src.server.actions import AttributeActions


@actions.datatype
class MFGContainer:
    def __init__(self, parent: AttributeActions):
        self.parent = parent

    @staticmethod
    def type_validator(v: Any) -> Tuple[str, str, str]:
        if (
            not isinstance(v, tuple)
            or len(v) != 3
            or not all(isinstance(x, str) for x in v)
        ):
            raise TypeError(
                f"MFGCONTAINER default must be a (sn: str, lot: str, container: str) "
                f"tuple, got {v!r}"
            )
        return v

    @staticmethod
    @tag_registry.expander("MFGCONTAINER")
    def _(name: str, preset: Tuple[str, str, str]):
        sn, lot, container = preset
        return [
            (f"{name}.SN",  actions.type.DINT(int(sn))),
            (f"{name}.SSN", actions.type.STRING(sn)),
            (f"{name}.LN",  actions.type.STRING(lot)),
            (f"{name}.CN",  actions.type.STRING(container)),
        ]

    def on_set_hook(self, tag_name: str, attr: Any, key: Any, value: Any) -> None:
        # Formats int Serial Number to String Serial Number
        if tag_name.endswith(".SN"):
            name_prefix = tag_name[: -len(".SN")]
            actions.string.set_val(f"{name_prefix}.SSN", key, f"{value[0]:04}")

        # Reverts any write to SSN
        if tag_name.endswith(".SSN.DATA"):
            name_prefix = tag_name[: -len(".SSN.DATA")]
            data_tag = self.parent._lookup(f"{name_prefix}.SN")
            if data_tag is None:
                return None
            old_val = data_tag[key]
            actions.string.set_val(f"{name_prefix}.SSN", key, f"{old_val[0]:04}")

        # String length helper for String types
        if tag_name.endswith(".DATA"):
            name_prefix = tag_name[: -len(".DATA")]
            actions.string._len_helper(name_prefix, key, value)
