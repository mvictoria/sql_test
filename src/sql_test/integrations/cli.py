import argparse
import sys
from pathlib import Path

from sql_test.integrations.app import serve
from sql_test.integrations.config import ConfigError, RepositoryConfig
from sql_test.integrations.discover import discover


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="sql-test")
    sub = parser.add_subparsers(dest="command", required=True)

    discover_parser = sub.add_parser("discover", help="list models, sources, and cases")
    discover_parser.add_argument("repository", type=Path, nargs="?", default=Path("."))

    app_parser = sub.add_parser(
        "app", help="start the authoring app against a repository"
    )
    app_parser.add_argument(
        "repository",
        type=Path,
        nargs="?",
        default=Path("."),
        help="path to the consuming repository (default: .)",
    )
    app_parser.add_argument(
        "--port",
        type=int,
        default=8765,
        help="localhost port (default: 8765)",
    )

    args = parser.parse_args(argv)
    repository = args.repository.resolve()
    if not repository.is_dir():
        print(f"repository not found: {repository}", file=sys.stderr)
        return 1
    try:
        RepositoryConfig.load(repository)
    except ConfigError as error:
        print(error, file=sys.stderr)
        return 1

    if args.command == "discover":
        result = discover(repository)
        _print_list("models", result.models)
        _print_list("sources", result.sources)
        if result.cases:
            print("cases:")
            for case in result.cases:
                print(f"  {case.target}/{case.name}")
        else:
            print("cases: (none)")
        return 0

    if args.command == "app":
        serve(repository, port=args.port)
        return 0

    return 1


def _print_list(label: str, names: tuple[str, ...]) -> None:
    if names:
        print(f"{label}:")
        for name in names:
            print(f"  {name}")
    else:
        print(f"{label}: (none)")


if __name__ == "__main__":
    raise SystemExit(main())
