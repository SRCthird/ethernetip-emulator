# Copyright 2026 Merck KGaA, Darmstadt, Germany and/or its affiliates.
# All rights reserved

# example/mfg_line/datatype/mfgcontainer.py
from __future__ import annotations
from typing import TYPE_CHECKING, Any, Tuple
from src.ethernetip_emulator.server.tag_specs import tag_registry
from src.ethernetip_emulator.server.device import actions

if TYPE_CHECKING:
    from src.ethernetip_emulator.server.actions import AttributeActions


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
            (f"{name}.SN",  actions.type.UINT(int(sn))),
            (f"{name}.SSN", actions.type.STRING(sn)),
            (f"{name}.LN",  actions.type.STRING(lot)),
            (f"{name}.CN",  actions.type.STRING(container)),
            (f"{name}.FLT", actions.type.BOOL(False)),
        ]

    def on_set_hook(self, tag_name: str, attr: Any, value: Any, key: slice | None) -> None:
        # Formats int Serial Number to String Serial Number
        if tag_name.endswith(".SN"):
            name_prefix = tag_name[: -len(".SN")]
            ssn = self.get_ssn(name_prefix, key)
            if _is_integer(ssn) and value == int(ssn):
                return
            self._set_ssn(name_prefix, f"{value[0]:04}", key)

        # Reverts any write to SSN
        if tag_name.endswith(".SSN.DATA"):
            name_prefix = tag_name[: -len(".SSN.DATA")]
            sn = self.get_sn(name_prefix, key)
            if _is_integer(value[0]) and int(value[0]) == sn:
                return
            self._set_ssn(name_prefix, f"{sn:04}", key)

        # String length helper for String types
        if tag_name.endswith(".DATA"):
            name_prefix = tag_name[: -len(".DATA")]
            actions.string._len_helper(name_prefix, key, value)

    def clear(self, name_prefix: str, key: slice | None = slice(0, 1)):
        self.set_sn(name_prefix, 0, key)
        self.set_ln(name_prefix, "", key)
        self.set_cn(name_prefix, "", key)
        self.set_flt(name_prefix, False, key)

    def set_container(self, name_prefix: str, sn: int, ln: str, cn: str, flt: bool = False, key: slice | None = slice(0, 1)):
        self.set_sn(name_prefix, sn, key)
        self.set_ln(name_prefix, ln, key)
        self.set_cn(name_prefix, cn, key)
        self.set_flt(name_prefix, flt, key)

    def get_container(self, name_prefix: str, key: slice | None = None) -> Tuple[int, str, str, str, bool]:
        return (
            self.get_sn(name_prefix, key),
            self.get_ssn(name_prefix, key),
            self.get_ln(name_prefix, key),
            self.get_cn(name_prefix, key),
            self.get_flt(name_prefix, key),
        )

    def is_empty(self, name_prefix, key: slice | None = None) -> bool:
        return self.get_sn(name_prefix, key) == 0 and \
            self.get_ln(name_prefix, key) == "" and \
            self.get_cn(name_prefix, key) == ""


    def get_sn(self, name_prefix: str, key: slice | None = slice(0, 1, None)) -> int:
        return actions.uint.get_val(f"{name_prefix}.SN", key)

    def set_sn(self, name_prefix: str, value: int, key: slice | None = slice(0, 1, None)):
        return actions.uint.set_val(f"{name_prefix}.SN", value, key)

    def get_ssn(self, name_prefix: str, key: slice | None = slice(0, 1, None)) -> str:
        return actions.string.get_val(f"{name_prefix}.SSN", key)

    def _set_ssn(self, name_prefix: str, value: str, key: slice | None = slice(0, 1, None)):
        return actions.string.set_val(f"{name_prefix}.SSN", value, key)

    def get_ln(self, name_prefix: str, key: slice | None = slice(0, 1, None)) -> str:
        return actions.string.get_val(f"{name_prefix}.LN", key)

    def set_ln(self, name_prefix: str, value: str, key: slice | None = slice(0, 1, None)):
        return actions.string.set_val(f"{name_prefix}.LN", value, key)

    def get_cn(self, name_prefix: str, key: slice | None = slice(0, 1, None)) -> str:
        return actions.string.get_val(f"{name_prefix}.CN", key)

    def set_cn(self, name_prefix: str, value: str, key: slice | None = slice(0, 1, None)):
        return actions.string.set_val(f"{name_prefix}.CN", value, key)

    def get_flt(self, name_prefix: str, key: slice | None = slice(0, 1, None)) -> bool:
        return actions.bool.get_val(f"{name_prefix}.FLT", key)

    def set_flt(self, name_prefix: str, value: bool, key: slice | None = slice(0, 1, None)):
        return actions.bool.set_val(f"{name_prefix}.FLT", value, key)
