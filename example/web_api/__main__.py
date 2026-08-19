# Copyright 2026 Merck KGaA, Darmstadt, Germany and/or its affiliates.
# All rights reserved

# example/web_api/__main__.py
from ethernetip_emulator.server.device import (
    AttributeDevice,
    apidict,
    device_controller,
)
from ethernetip_emulator.server.web_api import WebApi
from ethernetip_emulator.server.tag_specs import tag_registry

if __name__ == "__main__":
    server_control = apidict(timeout=1.0)
    AttributeDevice.set_server_control(server_control)

    AttributeDevice._web_api = WebApi(host="0.0.0.0", port=8080)

    with AttributeDevice._actions.bind(AttributeDevice):
        AttributeDevice.start_web()
        device_controller(
            argv=tag_registry.build_argv(base_args=["--print"]),
            attribute_class=AttributeDevice,
            server={"control": server_control},
        )
