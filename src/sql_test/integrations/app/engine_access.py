from pathlib import Path

from sql_test.engine import Engine, RunResult
from sql_test.engine.catalog.adapters import mapped_sql_folder
from sql_test.engine.executor import Row
from sql_test.engine.planner.plan import Plan
from sql_test.executors.duckdb import DuckDBExecutor
from sql_test.integrations.discover import MAPPING, SQLS


def catalog(repository: Path):
    return mapped_sql_folder(repository / SQLS, repository / MAPPING)


def filled_rows(
    mocks: tuple[str, ...],
    grid_rows: dict[str, list[dict[str, str]]],
) -> dict[str, list[Row]]:
    rows: dict[str, list[Row]] = {}
    for name in mocks:
        table_rows = grid_rows.get(name, [])
        filled = [
            row
            for row in table_rows
            if any(str(value).strip() for value in row.values())
        ]
        rows[name] = filled
    return rows


def plan(
    repository: Path,
    target: str,
    mocks: tuple[str, ...],
    grid_rows: dict[str, list[dict[str, str]]],
) -> Plan:
    engine = Engine(catalog=catalog(repository), executor=DuckDBExecutor)
    return engine.plan(target, rows=filled_rows(mocks, grid_rows))


def run(
    repository: Path,
    target: str,
    mocks: tuple[str, ...],
    grid_rows: dict[str, list[dict[str, str]]],
) -> RunResult:
    engine = Engine(catalog=catalog(repository), executor=DuckDBExecutor)
    return engine.run_result(target, rows=filled_rows(mocks, grid_rows))
