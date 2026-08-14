import argparse
import sys
from pathlib import Path

from .writers import (
    write_actions_file,
    write_datatypes_file,
    write_init,
    write_main,
    write_module_package,
    write_tags_file,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m ethernetip-emulator.generate",
        description="Generate a Python project scaffold.",
    )
    parser.add_argument(
        "name",
        nargs="?",
        default="new_project",
        help="Root folder name (default: new_project)",
    )
    parser.add_argument(
        "--expand",
        action="append",
        choices=["datatypes", "actions"],
        default=[],
        metavar="MODULE",
        help="Expand MODULE into a sub-package (can be used multiple times).",
    )
    return parser


def generate(name: str, expand: list[str]) -> Path:
    root = Path(name)

    if root.exists():
        print(f"[error] '{root}' already exists. Aborting.", file=sys.stderr)
        sys.exit(1)

    root.mkdir(parents=True)

    package = root.name

    write_init(root / "__init__.py", package=package)
    write_main(root / "__main__.py", package=package)

    if "datatypes" in expand:
        datatypes_package = root / "datatypes"
        write_module_package(
            datatypes_package,
            module="datatypes",
            package=package,
        )
        write_datatypes_file(
            datatypes_package / "datatypes.py",
            module="datatypes",
            package=package,
        )
    else:
        write_datatypes_file(
            root / "datatypes.py",
            module="datatypes",
            package=package,
        )

    if "actions" in expand:
        actions_package = root / "actions"
        write_module_package(
            actions_package,
            module="actions",
            package=package,
        )
        write_actions_file(
            actions_package / "actions.py",
            module="actions",
            package=package,
        )
    else:
        write_actions_file(
            root / "actions.py",
            module="actions",
            package=package,
        )

    write_tags_file(
        root / "tags.py",
        module="tags",
        package=package,
    )

    return root
