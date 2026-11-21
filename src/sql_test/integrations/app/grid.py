import html
import re
from pathlib import Path

from sql_test.engine.executor import Given
from sql_test.engine.schema import Schema
from sql_test.executors.duckdb import DuckDBExecutor
from sql_test.integrations.app.engine_access import catalog

_CELL = re.compile(r"^([^.]+)\.(\d+)\.(.+)$")


def mock_editor(
    repository: Path,
    mocks: tuple[str, ...],
    base_query: dict[str, str],
    view: str,
    rows: dict[str, list[dict[str, str]]],
    engine_types: dict[str, dict[str, str]],
    expected_section: str = "",
    case_name: str | None = None,
) -> str:
    if not mocks and not expected_section:
        return ""
    repo_catalog = catalog(repository)
    hidden = "".join(
        f'<input type="hidden" name="{html.escape(key)}" value="{html.escape(value)}">'
        for key, value in base_query.items()
    )
    hidden += f'<input type="hidden" name="view" value="{html.escape(view)}">'
    hidden += "".join(
        f'<input type="hidden" name="mock" value="{html.escape(name)}">'
        for name in mocks
    )
    sections: list[str] = []
    for name in mocks:
        schema = repo_catalog.schema(repo_catalog.resolve(name))
        if schema is None:
            sections.append(
                f"<h3><code>{html.escape(name)}</code></h3>"
                "<p class='empty'>No schema</p>"
            )
            continue
        table_rows = rows.get(name) or [{}]
        sections.append(grid(name, schema, table_rows, engine_types.get(name, {})))
    mocks_heading = "<h2>Mock editor</h2>" if mocks else ""
    readonly = " readonly" if case_name else ""
    name_field = (
        '<p class="case-name"><label>Case name '
        f'<input name="case_name" value="{html.escape(case_name or "")}"'
        f"{readonly}></label></p>"
    )
    return (
        '<form method="post" action="/workbench">'
        f"{hidden}{name_field}{mocks_heading}{''.join(sections)}{expected_section}"
        '<p class="grid-actions">'
        '<button type="submit" name="action" value="apply">Apply to engine</button>'
        '<button type="submit" name="action" value="run">Run</button>'
        '<button type="submit" name="action" value="save">Save case</button>'
        "</p>"
        "</form>"
    )


def grid(
    name: str,
    schema: Schema,
    rows: list[dict[str, str]],
    column_types: dict[str, str],
) -> str:
    headers = "".join(f"<th>{html.escape(column.name)}</th>" for column in schema)
    headers += "<th></th>"
    body_rows: list[str] = []
    for index, row in enumerate(rows):
        cells = []
        for column in schema:
            engine_type = column_types.get(column.name)
            type_attr = (
                f' data-engine-type="{html.escape(engine_type)}"' if engine_type else ""
            )
            cells.append(
                f"<td{type_attr}><input "
                f'name="{html.escape(name)}.{index}.{html.escape(column.name)}" '
                f'value="{html.escape(str(row.get(column.name, "")))}"></td>'
            )
        cells.append(
            "<td>"
            f'<button type="submit" name="action" value="delete:{html.escape(name)}:{index}">'
            "Delete</button></td>"
        )
        body_rows.append(f"<tr>{''.join(cells)}</tr>")
    return (
        f"<h3><code>{html.escape(name)}</code></h3>"
        f'<table class="grid" data-table="{html.escape(name)}">'
        f"<thead><tr>{headers}</tr></thead>"
        f"<tbody>{''.join(body_rows)}</tbody>"
        "</table>"
        '<p class="grid-actions">'
        f'<button type="submit" name="action" value="add:{html.escape(name)}">Add row</button>'
        "</p>"
    )


def parse_grid_rows(query: dict[str, list[str]]) -> dict[str, list[dict[str, str]]]:
    buckets: dict[str, dict[int, dict[str, str]]] = {}
    for key, values in query.items():
        match = _CELL.match(key)
        if not match:
            continue
        table, index_text, column = match.groups()
        buckets.setdefault(table, {}).setdefault(int(index_text), {})[column] = values[
            0
        ]
    return {
        table: [rows[index] for index in sorted(rows)]
        for table, rows in buckets.items()
    }


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
