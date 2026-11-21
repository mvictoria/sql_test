from collections.abc import Sequence

from sql_test.engine import Catalog, Column, Schema

type Cell = str | None
type GridRows = dict[str, list[dict[str, Cell]]]
type GridCell = tuple[int, str]


def next_grid_cell(
    columns: Sequence[str], row: int, column: str, row_count: int
) -> GridCell | None:
    """The next data cell left-to-right, then the next row; None past the last cell."""
    try:
        index = list(columns).index(column)
    except ValueError:
        return None
    if index + 1 < len(columns):
        return row, columns[index + 1]
    if row + 1 < row_count:
        return row + 1, columns[0]
    return None


def previous_grid_cell(
    columns: Sequence[str], row: int, column: str
) -> GridCell | None:
    """The previous data cell right-to-left, then the prior row; None before the first."""
    try:
        index = list(columns).index(column)
    except ValueError:
        return None
    if index > 0:
        return row, columns[index - 1]
    if row > 0:
        return row - 1, columns[-1]
    return None


def cell_error(column: Column, value: Cell) -> str | None:
    """Why `value` is not this column, or None when it is fine (including blank/NULL)."""
    if value is None or value == "":
        return None
    try:
        column.cast(value)
    except (TypeError, ValueError):
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


def paste_into_grid(
    rows: list[dict[str, Cell]],
    columns: Sequence[str],
    *,
    start_row: int,
    start_column: str,
    clipboard: str,
) -> list[dict[str, Cell]]:
    """Fill cells from spreadsheet TSV starting at ``(start_row, start_column)``.

    Empty clipboard cells become NULL (``None``). Extra paste rows extend the grid.
    """
    try:
        start_col = list(columns).index(start_column)
    except ValueError:
        return [dict(row) for row in rows]
    parsed = _parse_tsv(clipboard)
    if not parsed:
        return [dict(row) for row in rows]
    updated = [dict(row) for row in rows]
    while len(updated) < start_row + len(parsed):
        updated.append({})
    for row_offset, cells in enumerate(parsed):
        row = updated[start_row + row_offset]
        for col_offset, value in enumerate(cells):
            index = start_col + col_offset
            if index >= len(columns):
                break
            row[columns[index]] = value
    return updated


def _parse_tsv(clipboard: str) -> list[list[Cell]]:
    text = clipboard.replace("\r\n", "\n").replace("\r", "\n")
    text = text.removesuffix("\n")
    if not text:
        return []
    rows: list[list[Cell]] = []
    for line in text.split("\n"):
        cells: list[Cell] = []
        for cell in line.split("\t"):
            if cell == "":
                cells.append(None)
            elif cell == '""':
                cells.append("")
            else:
                cells.append(cell)
        rows.append(cells)
    return rows


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
