# Copyright 2026 Merck KGaA, Darmstadt, Germany and/or its affiliates.
# All rights reserved

# src/ethernetip_emulator/__version__.py
from importlib.metadata import version, PackageNotFoundError

if __name__ == "__main__":
    try:
        print(version("ethernetip_emulator"))
    except PackageNotFoundError:
        print("0.0.0-unknown")
