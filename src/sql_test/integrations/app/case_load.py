from pathlib import Path

from sql_test.engine.executor import Row
from sql_test.integrations.config import RepositoryConfig
from sql_test.testing.cases import Case, read_case


def load_case(repository: Path, target: str, name: str) -> Case:
    config = RepositoryConfig.load(repository)
    folder = config.cases / target / name
    return read_case(folder, config.catalog())


def case_grid_rows(case: Case) -> dict[str, list[dict[str, str | None]]]:
    rows: dict[str, list[dict[str, str | None]]] = {}
    for relation, table in case.mocks.items():
        rows[str(relation)] = [
            _display_row(row, table.columns) for row in table.rows
        ] or [{}]
    if case.expected is not None:
        rows["expected"] = [
            _display_row(row, case.expected.columns) for row in case.expected.rows
        ] or [{}]
    return rows


def _display_row(row: Row, columns: tuple[str, ...]) -> dict[str, str | None]:
    return {name: None if row.get(name) is None else str(row[name]) for name in columns}
