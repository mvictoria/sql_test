from pathlib import Path

from sql_test.engine import Catalog, Engine, Executor, Plan, Row, RunResult
from sql_test.integrations.config import RepositoryConfig

_executor: Executor | None = None


def bind_executor(executor: Executor) -> None:
    """Hand the app the one executor it keeps for the process."""
    global _executor
    _executor = executor


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


def _engine(repo_catalog: Catalog) -> Engine:
    if _executor is None:
        raise RuntimeError("app executor is not bound; call bind_executor first")
    return Engine(catalog=repo_catalog, executor=_executor)


def plan(
    repo_catalog: Catalog,
    target: str,
    mocks: tuple[str, ...],
    grid_rows: dict[str, list[dict[str, str | None]]],
) -> Plan:
    return _engine(repo_catalog).plan(target, rows=filled_rows(mocks, grid_rows))


def run(
    repo_catalog: Catalog,
    target: str,
    mocks: tuple[str, ...],
    grid_rows: dict[str, list[dict[str, str | None]]],
) -> RunResult:
    return _engine(repo_catalog).run(target, rows=filled_rows(mocks, grid_rows))
