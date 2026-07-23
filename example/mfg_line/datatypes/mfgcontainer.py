# Copyright 2026 Merck KGaA, Darmstadt, Germany and/or its affiliates.
# All rights reserved

# example/mfg_line/datatype/mfgcontainer.py
from __future__ import annotations
from typing import TYPE_CHECKING, Any, List, Tuple
from ethernetip_emulator.server.tag_specs import tag_registry
from ethernetip_emulator.server.device import actions

if TYPE_CHECKING:
    from ethernetip_emulator.server.actions import AttributeActions


def _is_integer(string_value):
    try:
        int(string_value)
        return True
    except ValueError:
        return False


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
            (f"{name}.SN", actions.type.UINT(int(sn))),
            (f"{name}.SSN", actions.type.STRING(sn)),
            (f"{name}.LN", actions.type.STRING(lot)),
            (f"{name}.CN", actions.type.STRING(container)),
            (f"{name}.FLT", actions.type.BOOL(False)),
        ]

    def on_set_hook(
        self, tag_name: str, attr: Any, key: slice, value: List[Any]
    ) -> None:
        # Formats int Serial Number to String Serial Number
        if tag_name.endswith(".SN"):
            name_prefix = tag_name[: -len(".SN")]
            ssn = self.get_ssn(name_prefix)
            if _is_integer(ssn) and value == int(ssn):
                return
            self._set_ssn(name_prefix, f"{value[0]:04}")

        # Reverts any write to SSN
        if tag_name.endswith(".SSN.DATA"):
            name_prefix = tag_name[: -len(".SSN.DATA")]
            sn = self.get_sn(name_prefix)
            if _is_integer(value[0]) and int(value[0]) == sn:
                return
            self._set_ssn(name_prefix, f"{sn:04}")

        # String length helper for String types
        if tag_name.endswith(".DATA"):
            name_prefix = tag_name[: -len(".DATA")]
            actions.string._len_helper(name_prefix, value[0])

    def clear(self, name_prefix: str):
        self.set_sn(name_prefix, 0)
        self.set_ln(name_prefix, "")
        self.set_cn(name_prefix, "")
        self.set_flt(name_prefix, False)

    def set_container(
        self, name_prefix: str, sn: int, ln: str, cn: str, flt: bool = False
    ):
        self.set_sn(name_prefix, sn)
        self.set_ln(name_prefix, ln)
        self.set_cn(name_prefix, cn)
        self.set_flt(name_prefix, flt)

    def get_container(self, name_prefix: str) -> Tuple[int, str, str, str, bool]:
        return (
            self.get_sn(name_prefix),
            self.get_ssn(name_prefix),
            self.get_ln(name_prefix),
            self.get_cn(name_prefix),
            self.get_flt(name_prefix),
        )

    def is_empty(self, name_prefix) -> bool:
        return (
            self.get_sn(name_prefix) == 0
            and self.get_ln(name_prefix) == ""
            and self.get_cn(name_prefix) == ""
        )

    def get_sn(self, name_prefix: str) -> int:
        return actions.uint.get_val(f"{name_prefix}.SN")

    def set_sn(self, name_prefix: str, value: int):
        return actions.uint.set_val(f"{name_prefix}.SN", value)

    def get_ssn(self, name_prefix: str) -> str:
        return actions.string.get_val(f"{name_prefix}.SSN")

    def _set_ssn(self, name_prefix: str, value: str):
        return actions.string.set_val(f"{name_prefix}.SSN", value)

    def get_ln(self, name_prefix: str) -> str:
        return actions.string.get_val(f"{name_prefix}.LN")

    def set_ln(self, name_prefix: str, value: str):
        return actions.string.set_val(f"{name_prefix}.LN", value)

    def get_cn(self, name_prefix: str) -> str:
        return actions.string.get_val(f"{name_prefix}.CN")

    def set_cn(self, name_prefix: str, value: str):
        return actions.string.set_val(f"{name_prefix}.CN", value)

    def get_flt(self, name_prefix: str) -> bool:
        return actions.bool.get_val(f"{name_prefix}.FLT")

    def set_flt(self, name_prefix: str, value: bool):
        return actions.bool.set_val(f"{name_prefix}.FLT", value)
