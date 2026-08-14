import re
import sys
from pathlib import Path


TAG_PATTERN = re.compile(
    r"^(?P<suffix>\.[\w.]+)\s*=\s*\((?P<type>\w+)\)(?P<default>.*)$"
)

_STRING_TYPES = {"STRING"}
_BOOL_TYPES = {"BOOL"}
_FLOAT_TYPES = {"REAL", "LREAL"}

_HINTS = {
    "STRING": "str",
    "BOOL": "bool",
    "REAL": "float",
    "LREAL": "float",
}


def find_project_root(start: Path | None = None) -> Path | None:
    current = (start or Path.cwd()).resolve()

    for candidate in [current, *current.parents]:
        has_init = (candidate / "__init__.py").is_file()
        has_main = (candidate / "__main__.py").is_file()
        has_datatypes = (candidate / "datatypes.py").is_file() or (
            candidate / "datatypes" / "__init__.py"
        ).is_file()

        if has_init and (has_main or has_datatypes):
            return candidate

    return None


def _strip_quotes(raw: str) -> str:
    raw = raw.strip()
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in "\"'":
        return raw[1:-1]
    return raw


def _parse_default(type_name: str, raw: str) -> tuple[object, str]:
    tname = type_name.upper()
    raw = raw.strip()

    if tname in _STRING_TYPES:
        value = _strip_quotes(raw)
        return value, f'"{value}"'

    if tname in _BOOL_TYPES:
        cleaned = _strip_quotes(raw).strip().lower()
        value = cleaned in {"1", "true"}
        return value, "True" if value else "False"

    if tname in _FLOAT_TYPES:
        value = float(raw) if raw else 0.0
        return value, repr(value)

    value = int(raw) if raw else 0
    return value, str(value)


def _method_name(suffix: str) -> str:
    return re.sub(r"\W+", "_", suffix.lstrip(".").lower()).strip("_")


def parse_tag_line(line: str) -> dict | None:
    match = TAG_PATTERN.match(line.strip())
    if not match:
        return None

    suffix = match.group("suffix")
    type_name = match.group("type").upper()
    _, default_code = _parse_default(type_name, match.group("default"))

    return {
        "suffix": suffix,
        "type_upper": type_name,
        "type_lower": type_name.lower(),
        "default_code": default_code,
        "method_name": _method_name(suffix),
        "python_hint": _HINTS.get(type_name, "int"),
    }


def prompt_datatype() -> tuple[str, list[dict]]:
    name = input("name: ").strip()
    if not name:
        print("[error] name is required.", file=sys.stderr)
        sys.exit(1)

    tags: list[dict] = []
    index = 1

    while True:
        line = input(f"tag {index:02d}: ")
        if not line.strip():
            break

        parsed = parse_tag_line(line)
        if parsed is None:
            print(
                f"[warn] could not parse '{line}'. "
                f"Expected format: .SUFFIX=(TYPE)default",
                file=sys.stderr,
            )
            continue

        tags.append(parsed)
        index += 1

    if not tags:
        print("[error] at least one tag is required.", file=sys.stderr)
        sys.exit(1)

    return name, tags
