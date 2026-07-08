# Copyright 2026 Merck KGaA, Darmstadt, Germany and/or its affiliates.
# All rights reserved

# example/mfg_line/__main__.py
from cpppo.server.enip.main import main as enip_main

from src.ethernetip_emulator.server.device import AttributeDevice
from src.ethernetip_emulator.server.tag_specs import tag_registry

if __name__ == "__main__":
    with AttributeDevice._actions.bind(AttributeDevice):
        enip_main(
            argv=tag_registry.build_argv(base_args=["--print"]),
            attribute_class=AttributeDevice,
        )
