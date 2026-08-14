from pathlib import Path


_PIPE = "│   "
_TEE = "├───"
_LAST = "└───"
_BLANK = "    "


def _tree_lines(path: Path, prefix: str = "") -> list[str]:
    entries = sorted(path.iterdir(), key=lambda p: (p.is_file(), p.name))
    lines: list[str] = []
    for i, entry in enumerate(entries):
        connector = _LAST if i == len(entries) - 1 else _TEE
        lines.append(f"{prefix}{connector}{entry.name}")
        if entry.is_dir():
            extension = _BLANK if i == len(entries) - 1 else _PIPE
            lines.extend(_tree_lines(entry, prefix + extension))
    return lines


def print_tree(root: Path, expand: list[str]) -> None:
    print()
    print(f"  {root}/")
    for line in _tree_lines(root):
        print(f"  {line}")
    print()


def print_success(root: Path) -> None:
    print(f"    Project '{root}' generated successfully.")
    print(f"    Run it with:  python -m {root}")
    print()
