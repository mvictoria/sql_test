from sql_test.engine import Catalog, Column, Schema

type Cell = str | None
type GridRows = dict[str, list[dict[str, Cell]]]


def cell_error(column: Column, value: Cell) -> str | None:
    """Why `value` is not this column, or None when it is fine (including blank/NULL)."""
    if value is None or value == "":
        return None
    try:
        column.cast(value)
    except TypeError, ValueError:
        return f"not {column.type}"
    return None


def validate_grid(schemas: dict[str, Schema], rows: GridRows) -> dict[str, str]:
    """Map `table.index.column` → error text for every invalid filled cell."""
    errors: dict[str, str] = {}
    for table, schema in schemas.items():
        for index, row in enumerate(rows.get(table, [])):
            for column in schema:
                message = cell_error(column, row.get(column.name))
                if message:
                    errors[f"{table}.{index}.{column.name}"] = message
    return errors


def apply_grid_action(
    action: str,
    mocks: tuple[str, ...],
    rows: GridRows,
) -> GridRows:
    editable = frozenset(mocks) | {"expected"}
    updated: GridRows = {
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
    elif action.startswith("duplicate:"):
        _, table, index_text = action.split(":", 2)
        if table in editable:
            index = int(index_text)
            table_rows = updated.setdefault(table, [{}])
            if 0 <= index < len(table_rows):
                table_rows.insert(index + 1, dict(table_rows[index]))
    return updated


def type_grid_rows(
    repo_catalog: Catalog, rows: GridRows
) -> tuple[GridRows, dict[str, dict[str, str]]]:
    typed_rows: GridRows = {}
    engine_types: dict[str, dict[str, str]] = {}
    for name, table_rows in rows.items():
        relation = repo_catalog.resolve(name)
        schema = repo_catalog.schema(relation)
        if schema is None:
            typed_rows[name] = table_rows
            continue
        non_empty = [
            {column.name: row.get(column.name) for column in schema}
            for row in table_rows
            if any(_filled(row.get(column.name)) for column in schema)
        ]
        if not non_empty:
            typed_rows[name] = table_rows or [{}]
            continue
        display: list[dict[str, Cell]] = []
        types: dict[str, str] = {}
        for row in non_empty:
            typed: dict[str, Cell] = {}
            for column in schema:
                raw = row[column.name]
                if raw is None or raw == "":
                    typed[column.name] = None
                    continue
                value = column.cast(raw)
                typed[column.name] = str(value)
                types[column.name] = type(value).__name__
            display.append(typed)
        typed_rows[name] = display or [{}]
        engine_types[name] = types
    return typed_rows, engine_types


def _filled(value: Cell) -> bool:
    if value is None:
        return False
    return value.strip() != ""
