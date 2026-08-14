from .display import print_tree, print_success
from .generate import build_parser, generate


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)

    root = generate(name=args.name, expand=args.expand)
    print_tree(root, expand=args.expand)
    print_success(root)


if __name__ == "__main__":
    main()
