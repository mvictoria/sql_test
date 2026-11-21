import argparse
import sys
from pathlib import Path

from sql_test.executors import DuckDBExecutor
from sql_test.integrations.app import serve
from sql_test.integrations.config import ConfigError, RepositoryConfig
from sql_test.integrations.discover import discover
from sql_test.integrations.init import InitError, init_repository
from sql_test.testing import coverage_report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="sql-test")
    sub = parser.add_subparsers(dest="command", required=True)

    discover_parser = sub.add_parser("discover", help="list models, sources, and cases")
    discover_parser.add_argument("repository", type=Path, nargs="?", default=Path("."))

    coverage_parser = sub.add_parser(
        "coverage", help="list test and in-pipeline counts per table"
    )
    coverage_parser.add_argument("repository", type=Path, nargs="?", default=Path("."))

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

    init_parser = sub.add_parser(
        "init", help="write a minimal consuming-repository skeleton"
    )
    init_parser.add_argument(
        "repository",
        type=Path,
        nargs="?",
        default=Path("."),
        help="directory to create or fill (default: .)",
    )

    args = parser.parse_args(argv)

    if args.command == "init":
        try:
            root = init_repository(args.repository)
        except InitError as error:
            print(error, file=sys.stderr)
            return 1
        print(f"Initialized {root}")
        print("Next: uv sync && uv run pytest && uv run sql-test discover .")
        return 0

    repository = args.repository.resolve()
    if not repository.is_dir():
        print(f"repository not found: {repository}", file=sys.stderr)
        return 1

    if args.command == "app":
        # Missing config opens the settings page in the app instead of exiting.
        serve(repository, executor=DuckDBExecutor(), port=args.port)
        return 0

    try:
        config = RepositoryConfig.load(repository)
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

    if args.command == "coverage":
        catalog = config.catalog()
        result = discover(repository, catalog)
        tables = (*result.models, *result.sources)
        report = coverage_report(tables, result.cases, catalog)
        print("table\ttests\tin pipelines")
        for row in report:
            print(f"{row.table}\t{row.tests}\t{row.pipelines}")
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
