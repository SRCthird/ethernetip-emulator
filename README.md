# Ethernet/IP Emulator (Python)

A small Python-based Ethernet/IP emulation template built on top of `cpppo` that exposes a set of tags (as attributes) and supports simple side-effect behaviors (like mirroring tags, background incrementing).

## Features

- **Tag specification utilities**
  - Define tags in a simple list form (`TAG_SPECS`)
  - Generate argv-style definitions (`TAG_ARGV`) for the server

- **Device layer**
  - `AttributeDevice` extends `cpppo.server.enip.device.Attribute`
  - Applies per-tag defaults
  - Triggers hook logic on writes through `AttributeActions`

- **Action layer**
  - `AttributeActions` handles side effects such as:
    - `on_set` dispatching (e.g., `I_TEXT` mirrors to `O_TEXT`)
    - background increment workers (`start_increment`, `run_increment_worker`)
  - Designed to be testable via dependency injection (`sleep_fn`, `thread_factory`, `logger`)

## Project Structure

See [Software Engineering at Merck](https://engineering.merckgroup.com/docs/dev/structure/) for more details.

```
src/
  client/          # not implemented
  server/
    actions.py     # side effects, increment worker, event handlers
    device.py      # AttributeDevice + defaults/argv helpers
    tag_specs.py   # TAG_SPECS + argv builder
tests/
  test_actions.py
  test_device.py
  test_tag_specs.py
```

## Requirements

- Python 3.10+
- `cpppo` (for Ethernet/IP attribute/device behavior)
- `black` (for code formatting)
- `coverage` (for coverage reporting)

Example install:

```bash
pip install -r requirements.txt 
```

## Running Tests

### With `unittest`
```bash
python -m unittest discover -s tests -p "test_*.py"
```

## Coverage

Run coverage (line + missing lines):

```bash
coverage run -m unittest discover
coverage report -m
```

## How Defaults Work

`src/server/device.py` provided helpers:

- `build_defaults(TAG_SPECS)` → `{name: default}` for defaults that are not `None`
- `AttributeDevice` applies defaults during initialization:
  - If `kwargs["default"]` is a non-empty list, it replaces the first element
  - Otherwise it sets `kwargs["default"]` directly

## How Actions Work

### Write hook
`AttributeDevice.__setitem__` calls:

```python
self._actions.on_set(self, key, value)
```

`AttributeActions.on_set` dispatches by attribute name. Example implemented:

- Writing `"I_TEXT"` mirrors the value to `"O_TEXT"` (if present in the registry)

### Increment worker
`AttributeActions.start_increment(...)` spawns a background worker thread that runs:

- `run_increment_worker(...)` which:
  - sleeps an initial delay
  - increments the target tag periodically
  - supports `wrap` modulus behavior

For tests, the actions class allows injection of:
- `sleep_fn` to avoid real waiting
- `thread_factory` to avoid real threads
- `logger` to capture log messages

## Usage In The Field

- This program uses a basic Ethernet/IP protocol, so connecting to it with higher-end or more complex drivers might result in errors.
- Drivers like the Allen-Bradley Micro800 Ethernet are the most compatible, but others may be available.
- Connection can be made through the default Ethernet/IP port of 44818.

## License

See [[LICENSE]]
Copyright 2022 Merck KGaA, Darmstadt, Germany and/or its affiliates.
All rights reserved.
