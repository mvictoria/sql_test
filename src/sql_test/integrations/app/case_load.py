from pathlib import Path

from sql_test.engine import Catalog, Row
from sql_test.integrations.config import RepositoryConfig
from sql_test.testing import Case, read_case


def load_case(repository: Path, target: str, name: str, repo_catalog: Catalog) -> Case:
    folder = RepositoryConfig.load(repository).cases / target / name
    return read_case(folder, repo_catalog)


def case_grid_rows(case: Case) -> dict[str, list[dict[str, str | None]]]:
    rows: dict[str, list[dict[str, str | None]]] = {}
    for relation, table in case.mocks.items():
        rows[str(relation)] = [
            display_row(row, table.columns) for row in table.rows
        ] or [{}]
    if case.expected is not None:
        rows["expected"] = [
            display_row(row, case.expected.columns) for row in case.expected.rows
        ]
    return rows


def display_row(row: Row, columns: tuple[str, ...]) -> dict[str, str | None]:
    return {name: None if row.get(name) is None else str(row[name]) for name in columns}
