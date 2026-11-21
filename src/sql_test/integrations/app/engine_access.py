from pathlib import Path

from sql_test.engine import Catalog, Engine, RunResult
from sql_test.engine.executor import Row
from sql_test.engine.planner.plan import Plan
from sql_test.executors.duckdb import DuckDBExecutor
from sql_test.integrations.config import RepositoryConfig


def catalog(repository: Path) -> Catalog:
    return RepositoryConfig.load(repository).catalog()


def _filled(value: str | None) -> bool:
    if value is None:
        return False
    return value.strip() != ""


def filled_rows(
    mocks: tuple[str, ...],
    grid_rows: dict[str, list[dict[str, str | None]]],
) -> dict[str, list[Row]]:
    rows: dict[str, list[Row]] = {}
    for name in mocks:
        table_rows = grid_rows.get(name, [])
        filled = [
            row for row in table_rows if any(_filled(value) for value in row.values())
        ]
        rows[name] = filled
    return rows


def plan(
    repository: Path,
    target: str,
    mocks: tuple[str, ...],
    grid_rows: dict[str, list[dict[str, str | None]]],
) -> Plan:
    engine = Engine(catalog=catalog(repository), executor=DuckDBExecutor())
    return engine.plan(target, rows=filled_rows(mocks, grid_rows))


def run(
    repository: Path,
    target: str,
    mocks: tuple[str, ...],
    grid_rows: dict[str, list[dict[str, str | None]]],
) -> RunResult:
    engine = Engine(catalog=catalog(repository), executor=DuckDBExecutor())
    return engine.run(target, rows=filled_rows(mocks, grid_rows))
