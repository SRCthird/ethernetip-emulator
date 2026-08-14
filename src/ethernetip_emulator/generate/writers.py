from pathlib import Path

import jinja2
import pystache


TEMPLATE_DIR = Path(__file__).parent / "templates"

_jinja_env = jinja2.Environment(
    loader=jinja2.FileSystemLoader(TEMPLATE_DIR),
    autoescape=False,
    keep_trailing_newline=True,
    trim_blocks=True,
    lstrip_blocks=True,
)


def render_template(
    template_name: str,
    *,
    package: str,
    module: str = "",
) -> str:
    template_path = TEMPLATE_DIR / template_name
    template = template_path.read_text(encoding="utf-8")

    package_path = f"{package}/{module}" if module else package

    context = {
        "package": package,
        "module": module,
        "package_path": package_path,
    }

    return pystache.render(template, context)


def write_template(
    path: Path,
    template_name: str,
    *,
    package: str,
    module: str = "",
) -> None:
    content = render_template(
        template_name,
        package=package,
        module=module,
    )

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    print(f"  created  {path}")


def write_init(path: Path, *, package: str) -> None:
    write_template(
        path,
        "__init__.py.mustache",
        package=package,
    )


def write_main(path: Path, *, package: str) -> None:
    write_template(
        path,
        "__main__.py.mustache",
        package=package,
    )


def write_actions_file(
    path: Path,
    *,
    module: str,
    package: str,
) -> None:
    write_template(
        path,
        "actions.py.mustache",
        package=package,
        module=module,
    )


def write_datatypes_file(
    path: Path,
    *,
    module: str,
    package: str,
) -> None:
    write_template(
        path,
        "datatypes.py.mustache",
        package=package,
        module=module,
    )


def write_tags_file(
    path: Path,
    *,
    module: str,
    package: str,
) -> None:
    write_template(
        path,
        "tags.py.mustache",
        package=package,
        module=module,
    )


def write_module_file(
    path: Path,
    *,
    module: str,
    package: str,
) -> None:
    write_template(
        path,
        "module.py.mustache",
        package=package,
        module=module,
    )


def write_module_package(
    folder: Path,
    *,
    module: str,
    package: str,
) -> None:
    write_template(
        folder / "__init__.py",
        "module_package_init.py.mustache",
        package=package,
        module=module,
    )


def write_datatype_file(
    path: Path,
    *,
    package: str,
    class_name: str,
    tags: list[dict],
) -> None:
    template = _jinja_env.get_template("datatype_class.py.jinja")

    content = template.render(
        package=package,
        class_name=class_name,
        class_name_upper=class_name.upper(),
        module_file=class_name.lower(),
        tags=tags,
    )

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    print(f"  created  {path}")
