# Copyright 2026 Merck KGaA, Darmstadt, Germany and/or its affiliates.
# All rights reserved

# __main__.py
from cpppo.server.enip.main import main as enip_main

from scope import actions, tags
from src.server.device import AttributeDevice
from src.server.tag_specs import tag_registry


if __name__ == "__main__":
    with AttributeDevice._actions.bind(AttributeDevice):
        enip_main(
            argv=tag_registry.build_argv(base_args=["--print"]),
            attribute_class=AttributeDevice,
        )
