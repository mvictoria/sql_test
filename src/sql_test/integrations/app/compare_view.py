import html
from pathlib import Path

from sql_test.engine.executor import Row
from sql_test.engine.relation import Relation
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
    return _render_comparison(comparison, columns)


def _load_typed_rows(
    repository: Path,
    target: str,
    schema: Schema,
    rows: list[dict[str, str]],
) -> list[Row]:
    if not rows:
        return []
    repo_catalog = catalog(repository)
    relation = Relation.parse(target).resolve(repo_catalog.relations().keys())
    executor = DuckDBExecutor()
    executor.setup()
    try:
        executor.create_relation(relation, schema, rows)
        return executor.read_rows(relation)
    finally:
        executor.teardown()


def _target_schema(repository: Path, target: str) -> Schema | None:
    repo_catalog = catalog(repository)
    relation = Relation.parse(target).resolve(repo_catalog.relations().keys())
    return repo_catalog.schemas.get(relation)


def _render_comparison(comparison: Comparison, columns: tuple[str, ...]) -> str:
    parts = [
        "<h2>Expected vs actual</h2>",
        (
            '<p class="legend">'
            "<span>matching</span> <span>changed</span> "
            "<span>missing</span> <span>unexpected</span>"
            " — expected is editable above; actual is read-only"
            "</p>"
        ),
        _outcome_table(
            "matching",
            columns,
            [
                (_cells(row, columns), _cells(row, columns, actual=True))
                for row in comparison.matched
            ],
        ),
        _outcome_table(
            "changed",
            columns,
            [
                (
                    _cells(
                        change.expected, columns, differing=change.differing_columns
                    ),
                    _cells(
                        change.actual,
                        columns,
                        differing=change.differing_columns,
                        actual=True,
                    ),
                )
                for change in comparison.changed
            ],
        ),
        _outcome_table(
            "missing",
            columns,
            [
                (_cells(row, columns), _empty_cells(columns, actual=True))
                for row in comparison.missing
            ],
        ),
        _outcome_table(
            "unexpected",
            columns,
            [
                (_empty_cells(columns), _cells(row, columns, actual=True))
                for row in comparison.unexpected
            ],
        ),
    ]
    return "".join(parts)


def _outcome_table(
    outcome: str,
    columns: tuple[str, ...],
    pairs: list[tuple[str, str]],
) -> str:
    if not pairs:
        return (
            f'<section class="compare-outcome" data-outcome="{html.escape(outcome)}">'
            f"<h3>{html.escape(outcome)}</h3>"
            '<p class="empty">None</p>'
            "</section>"
        )
    header = (
        "<tr><th></th>"
        + "".join(f"<th>{html.escape(name)}</th>" for name in columns)
        + "</tr>"
    )
    rows = []
    for expected_cells, actual_cells in pairs:
        rows.append(
            f'<tr class="expected"><th scope="row">expected</th>{expected_cells}</tr>'
        )
        rows.append(
            f'<tr class="actual" data-side="actual">'
            f'<th scope="row">actual</th>{actual_cells}</tr>'
        )
    return (
        f'<section class="compare-outcome" data-outcome="{html.escape(outcome)}">'
        f"<h3>{html.escape(outcome)}</h3>"
        f'<table class="compare">{header}{"".join(rows)}</table>'
        "</section>"
    )


def _cells(
    row: Row,
    columns: tuple[str, ...],
    *,
    differing: tuple[str, ...] = (),
    actual: bool = False,
) -> str:
    cells = []
    for name in columns:
        value = row.get(name)
        text = html.escape("" if value is None else str(value))
        classes = []
        if name in differing:
            classes.append("differing")
        if actual:
            classes.append("readonly")
        cls = f' class="{" ".join(classes)}"' if classes else ""
        if actual:
            cells.append(
                f'<td{cls} data-side="actual"><input readonly value="{text}"></td>'
            )
        else:
            cells.append(f"<td{cls}>{text}</td>")
    return "".join(cells)


def _empty_cells(columns: tuple[str, ...], *, actual: bool = False) -> str:
    side = ' data-side="actual"' if actual else ""
    cls = ' class="empty readonly"' if actual else ' class="empty"'
    return "".join(f"<td{cls}{side}>—</td>" for _ in columns)
