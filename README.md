# EtherNet/IP Emulator (Python)

ethernetip-emulator is a high level binary communications framework built around [`cpppo`](https://github.com/pjkundert/cpppo) (pronounced ‘c’3*’p’‘o’ in Python) that exposes a set of tags and allows for the programatic execution .

## Architecture

```
.
├───example
│   ├───basic_datatypes
│   │   └─── *.py
│   ├───mfg_line
│   │   └─── *.py
│   ├───orange_pi
│   │   └─── *.py
│   └───raspberry_pi
│       └─── *.py
├───src
│   └───ethernetip_emulator
│       ├───client
│       ├───server
│       │   ├───datatypes
│       │   │   ├───templates
│       │   │   │   └─── *.py
│       │   │   └─── *.py
│       │   └─── *.py
│       └─── *.py
└───tests
    └───server
        ├───datatypes
        │   ├───mock
        │   │   └─── test_*.py
        │   ├───templates
        │   │   └─── test_*.py
        │   └─── test_*.py
        └─── test_*.py
        
```

## Requirements

- Python 3.10+
- `cpppo` (for Ethernet/IP attribute/device behavior)
- `black` | Development Dependency (for code formatting)
- `coverage` | Developer Dependency (for coverage reporting)
- `RPi.GPIO` or `OPi.GPIO` | Optional Dependency (for gpio i/o)

## Getting Started

```bash
pip install ethernetip-emulator
```

A minimal project needs three files:

| File | Purpose |
|---|---|
| `tags.py` | Declare tags with `@tag_registry.register` |
| `actions.py` | React to tag changes with `@actions.<type>.on_change` |
| `__main__.py` | Start the server with `device_controller` |

```python
# __main__.py
from ethernetip_emulator.server.device import AttributeDevice, apidict, device_controller
from ethernetip_emulator.server.tag_specs import tag_registry
import tags    # registers all tags (can also just be imported in __init__.py)
import actions # registers all listeners (can also just be imported in __init__.py)

if __name__ == "__main__":
    server_control = apidict(timeout=1.0)
    AttributeDevice.set_server_control(server_control)

    with AttributeDevice._actions.bind(AttributeDevice):
        device_controller(
            argv=tag_registry.build_argv(base_args=["--print"]),
            attribute_class=AttributeDevice,
            server={"control": server_control},
        )
```

## Guides

### Core

| Guide | Description |
|---|---|
| [Tag Registry](https://github.com/SRCthird/ethernetip-emulator/wiki/Defining-Tags-with-tag_registry.register) | Define tags with `@tag_registry.register`, use namespaced prefixes, and organise tags across files |
| [Actions](https://github.com/SRCthird/ethernetip-emulator/wiki/Working-with-Actions) | Read and write tags at runtime, register `on_change` listeners, and understand `key` and `defer` |
| [Device](https://github.com/SRCthird/ethernetip-emulator/wiki/The-Device-Module) | Start and stop the server, understand how tag writes are intercepted, and apply startup defaults |

### Datatypes

| Guide | Description |
|---|---|
| [Datatypes Overview](https://github.com/SRCthird/ethernetip-emulator/wiki/datatypes) | All built-in types at a glance, and a step-by-step guide to creating custom datatypes |
| [Basic Datatypes](https://github.com/SRCthird/ethernetip-emulator/wiki/basic-datatypes) | Scalar types: `BOOL`, integers, floats, and strings — shared `get_val` / `set_val` / `on_change` API |
| [Bool Array](https://github.com/SRCthird/ethernetip-emulator/wiki/bool-array-datatype) | `BOOLARRAY` — bit-level access, list operations, bulk mutations |
| [Numeric Arrays](https://github.com/SRCthird/ethernetip-emulator/wiki/numeric-array-datatypes) | `SINTARRAY` · `USINTARRAY` · `INTARRAY` · `UINTARRAY` · `DINTARRAY` · `UDINTARRAY` · `LINTARRAY` · `ULINTARRAY` |
| [Real Arrays](https://github.com/SRCthird/ethernetip-emulator/wiki/real-array-datatypes) | `REALARRAY` · `LREALARRAY` — same API as numeric arrays with floating-point zero tolerance (`1e-9`) |
| [String Array](https://github.com/SRCthird/ethernetip-emulator/wiki/string-array-datatype) | `SSTRINGARRAY` — list operations using `""` as the empty slot sentinel |
| [GPIO](https://github.com/SRCthird/ethernetip-emulator/wiki/gpio-datatype) | `GPIO` — maps EtherNet/IP tags to physical hardware pins on a Raspberry Pi or Orange Pi |
| [Counter](https://github.com/SRCthird/ethernetip-emulator/wiki/gpio-datatype) | `COUNTER` — composite datatype that models a up/down counter with control tags |
| [Timer](https://github.com/SRCthird/ethernetip-emulator/wiki/gpio-datatype) | `TIMER` — composite datatype that models a timer with control tags |

## Typical Workflow 

```
┌─────────────────────────────────────────────────────┐
│                    Your Project                     │
│                                                     │
│  tags.py ──────► tag_registry                       │
│                      │                              │
│                       ▼                             │
│  datatypes.py ─► actions.datatype                   │
│                      │                              │
│                       ▼                             │
│  __main__.py ──► device_controller                  │
│                      │                              │
│                       ▼                             │
│              AttributeDevice                        │
│           (intercepts PLC writes)                   │
│                      │                              │
│                       ▼                             │
│  actions.py ──► on_change listeners                 │
│                      │                              │
│                       ▼                             │
│              actions.<type>.set_val / get_val       │
└─────────────────────────────────────────────────────┘
```

1. **Tags** are declared once at import time via `@tag_registry.register`.
2. **Custom Datatypes** can be declared once at import time via `@actions.datatype`. Although this is completely optional if you like the built-in datatypes
2. **`device_controller`** builds the tag list and starts the EtherNet/IP server.
3. **`AttributeDevice`** intercepts every PLC write and fires the matching `on_change` listeners.
4. **Listeners** use `actions.<type>` helpers to read state, write back to tags, or trigger application logic.

## Project Layout Convention

```
your_project/
├── __main__.py          # server entrypoint
├── tags.py              # tag definitions
├── actions.py           # on_change handlers
└── datatypes/           # optional: custom datatype classes
    ├── __init__.py
    └── mytype.py
```

For larger projects, split tags and actions into sub-modules and import them from a top-level `__init__.py` so all registrations are triggered before the server starts.

## Protecting Attributes

`AttributeDevice` can make one or more attributes read-only. Protection is applied by attribute name and prevents writes handled by `AttributeDevice.__setitem__`; blocked writes are ignored and do not trigger on_set actions.
- `AttributeDevice.protect(*tag_names)` marks the specified attributes as protected.
- `AttributeDevice.unprotect(*tag_names)` removes protection from the specified attributes.
- `AttributeDevice.is_protected(tag_name)` returns True when the attribute is currently protected; otherwise, it returns False.

```python
from ethernetip_emulator.server.device import AttributeDevice

# Prevent writes to one or more attributes.
AttributeDevice.protect("Motor.Enabled", "Motor.Speed")

if AttributeDevice.is_protected("Motor.Speed"):
    print("Motor.Speed is read-only")

# Allow writes again when the protected state is no longer needed.
AttributeDevice.unprotect("Motor.Speed", "Motor.Enabled")
```

Protection is maintained on the AttributeDevice class, so use the class methods to manage the protected attribute names. It remains active until the attributes are explicitly passed to unprotect.

## Supporting the Development of EtherNet/IP Emulator
EtherNet/IP Emulator's development depends on your contributions. Right now it is just me working on this, so any contributions are welcome!

## License

Copyright 2026 Merck KGaA, Darmstadt, Germany and/or its affiliates. All rights reserved.

