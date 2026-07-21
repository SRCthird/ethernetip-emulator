# Copyright 2026 Merck KGaA, Darmstadt, Germany and/or its affiliates.
# All rights reserved

# tests/__init__.py
import itertools
import logging

logging.getLogger("network").setLevel(logging.CRITICAL)

_port_counter = itertools.count(44818)


def next_port() -> int:
    return next(_port_counter)
