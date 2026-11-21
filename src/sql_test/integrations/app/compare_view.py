import html
from pathlib import Path

from sql_test.engine.executor import Given, Row
from sql_test.engine.schema import Schema
from sql_test.executors.duckdb import DuckDBExecutor
from sql_test.integrations.app.engine_access import catalog
from sql_test.testing.cases import CaseTable
from sql_test.testing.comparison import Comparison, compare


def expected_editor(
    repository: Path,
    target: str,
    rows: list[dict[str, str]],
) -> str:
    schema = _target_schema(repository, target)
    if schema is None:
        return (
            "<h2>Expected</h2><p class='empty'>No schema for the table under test</p>"
        )
    table_rows = rows or [{}]
    headers = "".join(f"<th>{html.escape(column.name)}</th>" for column in schema)
    headers += "<th></th>"
    body_rows: list[str] = []
    for index, row in enumerate(table_rows):
        cells = []
        for column in schema:
            cells.append(
                f"<td><input "
                f'name="expected.{index}.{html.escape(column.name)}" '
                f'value="{html.escape(str(row.get(column.name, "")))}"></td>'
            )
        cells.append(
            "<td>"
            f'<button type="submit" name="action" value="delete:expected:{index}">'
            "Delete</button></td>"
        )
        body_rows.append(f"<tr>{''.join(cells)}</tr>")
    return (
        "<h2>Expected</h2>"
        '<table class="grid" data-table="expected">'
        f"<thead><tr>{headers}</tr></thead>"
        f"<tbody>{''.join(body_rows)}</tbody>"
        "</table>"
        '<p class="grid-actions">'
        '<button type="submit" name="action" value="add:expected">Add row</button>'
        "</p>"
    )


def compare_section(
    repository: Path,
    target: str,
    expected_rows: list[dict[str, str]],
    actual: list[Row],
) -> str:
    schema = _target_schema(repository, target)
    if schema is None:
        return ""
    columns = tuple(column.name for column in schema)
    filled = [
        {column.name: row.get(column.name, "") for column in schema}
        for row in expected_rows
        if any(str(value).strip() for value in row.values())
    ]
    if not filled and not actual:
        return ""
    typed_rows = _load_typed_rows(repository, target, schema, filled)
    expected = CaseTable(columns=columns, rows=typed_rows)
    comparison = compare(expected, actual)
    return _render_diff(comparison, columns)


def _load_typed_rows(
    repository: Path,
    target: str,
    schema: Schema,
    rows: list[dict[str, str]],
) -> list[Row]:
    if not rows:
        return []
    repo_catalog = catalog(repository)
    relation = repo_catalog.resolve(target)
    return DuckDBExecutor().run({relation: Given(schema, rows)}, [])[relation]


def _target_schema(repository: Path, target: str) -> Schema | None:
    repo_catalog = catalog(repository)
    return repo_catalog.schema(repo_catalog.resolve(target))


def _render_diff(comparison: Comparison, columns: tuple[str, ...]) -> str:
    if not (comparison.changed or comparison.missing or comparison.unexpected):
        return (
            '<div class="diff" data-diff="clean">'
            "<h2>Diff</h2>"
            '<p class="empty">No differences</p>'
            "</div>"
        )
    header = (
        '<tr class="diff-header"><th class="diff-marker"></th>'
        + "".join(f"<th>{html.escape(name)}</th>" for name in columns)
        + "</tr>"
    )
    rows: list[str] = []
    for change in comparison.changed:
        rows.append(
            f'<tr class="diff-hunk" data-outcome="changed">'
            f'<td class="diff-marker" colspan="{len(columns) + 1}">'
            f"@@ changed @@</td></tr>"
        )
        rows.append(
            _diff_row(
                "-", change.expected, columns, change.differing_columns, "changed"
            )
        )
        rows.append(
            _diff_row("+", change.actual, columns, change.differing_columns, "changed")
        )
    for row in comparison.missing:
        rows.append(_diff_row("-", row, columns, (), "missing"))
    for row in comparison.unexpected:
        rows.append(_diff_row("+", row, columns, (), "added"))
    return (
        '<div class="diff" data-diff="dirty">'
        "<h2>Diff</h2>"
        '<p class="legend">'
        '<span class="diff-removed">− missing / old</span> '
        '<span class="diff-added">+ added / new</span>'
        " — expected is editable in the Expected grid"
        "</p>"
        f'<table class="diff-table">{header}{"".join(rows)}</table>'
        "</div>"
    )


def _diff_row(
    marker: str,
    row: Row,
    columns: tuple[str, ...],
    differing: tuple[str, ...],
    outcome: str,
) -> str:
    side = "removed" if marker == "-" else "added"
    cells = [f'<th class="diff-marker" scope="row">{html.escape(marker)}</th>']
    for name in columns:
        value = row.get(name)
        text = html.escape("" if value is None else str(value))
        cls = ' class="differing"' if name in differing else ""
        cells.append(f"<td{cls}>{text}</td>")
    return (
        f'<tr class="diff-{side}" data-outcome="{html.escape(outcome)}" '
        f'data-side="{"expected" if marker == "-" else "actual"}">'
        f"{''.join(cells)}</tr>"
    )
