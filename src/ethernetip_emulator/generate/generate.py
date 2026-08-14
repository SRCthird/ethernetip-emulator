import argparse
import sys
from pathlib import Path

from .datatype_prompt import find_project_root, prompt_datatype
from .writers import (
    write_actions_file,
    write_datatype_file,
    write_datatypes_file,
    write_init,
    write_main,
    write_module_file,
    write_module_package,
    write_tags_file,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m ethernetip_emulator.generate",
        description="Generate a Python project scaffold, or add a datatype.",
    )
    parser.add_argument(
        "name",
        nargs="?",
        default="new_project",
        help="Root folder name (default: new_project), or 'datatype' to "
        "interactively add a new datatype to the current project.",
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


def generate_datatype() -> Path:
    project_root = find_project_root()

    if project_root is None:
        print(
            "[error] not inside a generated project. "
            "Run this from within a project's root directory.",
            file=sys.stderr,
        )
        sys.exit(1)

    package = project_root.name
    class_name, tags = prompt_datatype()

    datatypes_dir = project_root / "datatypes"
    output_path = datatypes_dir / f"{class_name.lower()}.py"

    if output_path.exists():
        print(
            f"[error] '{output_path}' already exists. Aborting.",
            file=sys.stderr,
        )
        sys.exit(1)

    write_datatype_file(
        output_path,
        package=package,
        class_name=class_name,
        tags=tags,
    )

    return output_path
