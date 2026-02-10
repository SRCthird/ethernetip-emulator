# Copyright 2022 Merck KGaA, Darmstadt, Germany and/or its affiliates.
# All rights reserved

from cpppo.server.enip.main import main as enip_main
from src.server.device import AttributeDevice
from src.server.tag_specs import TAG_ARGV

if __name__ == "__main__":
    # EXAMPLE:
    AttributeDevice._actions.bind(AttributeDevice).start_increment(tag_name="O_INCR")

    enip_main(
        argv=TAG_ARGV,
        attribute_class=AttributeDevice,
    )
