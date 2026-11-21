from pathlib import Path

from sql_test.engine.relation import Relation
from sql_test.engine.schema import Schema
from sql_test.integrations.config import RepositoryConfig
from sql_test.testing.cases import Case, CaseTable, write_case


class SaveError(Exception):
    pass


def save_case(
    repository: Path,
    target: str,
    name: str,
    mocks: tuple[str, ...],
    grid_rows: dict[str, list[dict[str, str]]],
) -> Path:
    if not name or "/" in name or name in {".", ".."}:
        raise SaveError("case name is required and must not contain '/'")
    config = RepositoryConfig.load(repository)
    schemas = config.catalog().schemas
    known = schemas.keys()
    target_relation = Relation.parse(target).resolve(known)
    mock_tables: dict[Relation, CaseTable] = {}
    for mock_name in mocks:
        relation = Relation.parse(mock_name).resolve(known)
        schema = schemas.get(relation)
        if schema is None:
            raise SaveError(f"no schema for mock {mock_name}")
        mock_tables[relation] = _table_from_grid(schema, grid_rows.get(mock_name, []))
    expected_schema = schemas.get(target_relation)
    expected = None
    if expected_schema is not None:
        expected_rows = grid_rows.get("expected", [])
        if any(
            any(str(value).strip() for value in row.values()) for row in expected_rows
        ):
            expected = _table_from_grid(expected_schema, expected_rows)
    folder = config.cases / str(target_relation) / name
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
    return folder


def _table_from_grid(schema: Schema, rows: list[dict[str, str]]) -> CaseTable:
    columns = tuple(column.name for column in schema)
    by_name = {column.name: column for column in schema}
    typed = []
    for row in rows:
        if not any(str(value).strip() for value in row.values()):
            continue
        typed.append(
            {
                name: by_name[name].cast(
                    None if row.get(name, "") == "" else row.get(name)
                )
                for name in columns
            }
        )
    return CaseTable(columns=columns, rows=typed)
