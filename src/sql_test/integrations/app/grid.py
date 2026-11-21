from pathlib import Path

from sql_test.engine.executor import Given
from sql_test.executors.duckdb import DuckDBExecutor
from sql_test.integrations.app.engine_access import catalog


def apply_grid_action(
    action: str,
    mocks: tuple[str, ...],
    rows: dict[str, list[dict[str, str]]],
) -> dict[str, list[dict[str, str]]]:
    editable = frozenset(mocks) | {"expected"}
    updated = {
        name: [dict(row) for row in table_rows] for name, table_rows in rows.items()
    }
    for name in editable:
        updated.setdefault(name, [{}])
    if action.startswith("add:"):
        table = action.removeprefix("add:")
        if table in editable:
            updated.setdefault(table, []).append({})
    elif action.startswith("delete:"):
        _, table, index_text = action.split(":", 2)
        if table in editable:
            index = int(index_text)
            table_rows = updated.get(table, [])
            if 0 <= index < len(table_rows):
                del table_rows[index]
            if not table_rows:
                table_rows.append({})
            updated[table] = table_rows
    return updated


def type_grid_rows(
    repository: Path, rows: dict[str, list[dict[str, str]]]
) -> tuple[dict[str, list[dict[str, str]]], dict[str, dict[str, str]]]:
    repo_catalog = catalog(repository)
    typed_rows: dict[str, list[dict[str, str]]] = {}
    engine_types: dict[str, dict[str, str]] = {}
    for name, table_rows in rows.items():
        relation = repo_catalog.resolve(name)
        schema = repo_catalog.schema(relation)
        if schema is None:
            typed_rows[name] = table_rows
            continue
        non_empty = [
            {column.name: row.get(column.name, "") for column in schema}
            for row in table_rows
            if any(str(row.get(column.name, "")).strip() for column in schema)
        ]
        if not non_empty:
            typed_rows[name] = table_rows or [{}]
            continue
        written = DuckDBExecutor().run({relation: Given(schema, non_empty)}, [])
        loaded = [
            tuple(row[column.name] for column in schema) for row in written[relation]
        ]
        display: list[dict[str, str]] = []
        types: dict[str, str] = {}
        for values in loaded:
            display.append(
                {
                    column.name: "" if value is None else str(value)
                    for column, value in zip(schema, values, strict=True)
                }
            )
            for column, value in zip(schema, values, strict=True):
                types[column.name] = type(value).__name__
        typed_rows[name] = display or [{}]
        engine_types[name] = types
    return typed_rows, engine_types
