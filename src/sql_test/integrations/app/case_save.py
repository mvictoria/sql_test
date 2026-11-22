import shutil
from pathlib import Path

from sql_test.engine import Catalog, Relation, Schema
from sql_test.integrations.config import RepositoryConfig
from sql_test.testing import Case, CaseTable, write_case


class SaveError(Exception):
    pass


def case_folder(
    repository: Path, target: str, name: str, repo_catalog: Catalog
) -> Path:
    """On-disk folder for `target`/`name` under the repository's cases root."""
    if not name or "/" in name or name in {".", ".."}:
        raise SaveError("case name is required and must not contain '/'")
    cases = RepositoryConfig.load(repository).cases
    return cases / str(repo_catalog.resolve(target)) / name


def case_exists(
    repository: Path, target: str, name: str, repo_catalog: Catalog
) -> bool:
    """True when the case folder already has CSV files (a silent overwrite risk)."""
    folder = case_folder(repository, target, name, repo_catalog)
    return folder.is_dir() and any(folder.glob("*.csv"))


def save_case(
    repository: Path,
    target: str,
    name: str,
    mocks: tuple[str, ...],
    grid_rows: dict[str, list[dict[str, str | None]]],
    repo_catalog: Catalog,
    *,
    previous_name: str | None = None,
) -> Path:
    folder = case_folder(repository, target, name, repo_catalog)
    target_relation = repo_catalog.resolve(target)
    mock_tables: dict[Relation, CaseTable] = {}
    for mock_name in mocks:
        relation = repo_catalog.resolve(mock_name)
        schema = repo_catalog.schema(relation)
        if schema is None:
            raise SaveError(f"no schema for mock {mock_name}")
        mock_tables[relation] = _table_from_grid(schema, grid_rows.get(mock_name, []))
    expected_schema = repo_catalog.schema(target_relation)
    expected = None
    if expected_schema is not None:
        expected_rows = grid_rows.get("expected", [{}])
        if expected_rows == [] or any(
            any(str(value).strip() for value in row.values()) for row in expected_rows
        ):
            expected = _table_from_grid(expected_schema, expected_rows)
    folder.mkdir(parents=True, exist_ok=True)
    for path in folder.glob("*.csv"):
        path.unlink()
    write_case(
        folder,
        Case(
            target=target_relation,
            name=name,
            mocks=mock_tables,
            expected=expected,
        ),
    )
    if previous_name and previous_name != name:
        old = case_folder(repository, target, previous_name, repo_catalog)
        if old != folder and old.is_dir():
            shutil.rmtree(old)
    return folder


def _table_from_grid(schema: Schema, rows: list[dict[str, str | None]]) -> CaseTable:
    columns = tuple(column.name for column in schema)
    by_name = {column.name: column for column in schema}
    typed = []
    for row in rows:
        if not any(_filled(value) for value in row.values()):
            continue
        typed.append({name: by_name[name].cast(row.get(name)) for name in columns})
    return CaseTable(columns=columns, rows=typed)


def _filled(value: str | None) -> bool:
    if value is None:
        return False
    return value.strip() != ""
