from dataclasses import dataclass

from sql_test.engine import Catalog, Row, Schema
from sql_test.testing import CaseTable, Comparison, compare


@dataclass(frozen=True)
class DiffPanel:
    columns: tuple[str, ...]
    has_expected: bool
    comparison: Comparison | None

    @property
    def passed(self) -> bool:
        return (
            self.has_expected and self.comparison is not None and self.comparison.passed
        )


def compare_section(
    repo_catalog: Catalog,
    target: str,
    expected_rows: list[dict[str, str | None]],
    actual: list[Row],
    *,
    ordered: bool = False,
) -> DiffPanel:
    schema = target_schema(repo_catalog, target)
    filled = [
        row for row in expected_rows if any(_filled(value) for value in row.values())
    ]
    has_expected = bool(filled) or expected_rows == []
    if schema is None:
        return DiffPanel(columns=(), has_expected=has_expected, comparison=None)
    columns = tuple(column.name for column in schema)
    aligned = [
        {
            column.name: (
                None if row.get(column.name) is None else str(row.get(column.name, ""))
            )
            for column in schema
        }
        for row in filled
    ]
    if not has_expected and not actual:
        return DiffPanel(columns=columns, has_expected=False, comparison=None)
    typed_rows = [typed_row(schema, row) for row in aligned]
    expected = CaseTable(columns=columns, rows=typed_rows)
    comparison = compare(expected, actual, ordered=ordered)
    return DiffPanel(
        columns=columns,
        has_expected=has_expected,
        comparison=comparison,
    )


def typed_row(schema: Schema, row: dict[str, str | None]) -> Row:
    return {
        column.name: (
            None
            if row.get(column.name) is None or row.get(column.name) == ""
            else column.cast(row.get(column.name))
        )
        for column in schema
    }


def target_schema(repo_catalog: Catalog, target: str) -> Schema | None:
    return repo_catalog.schema(repo_catalog.resolve(target))


def _filled(value: str | None) -> bool:
    if value is None:
        return False
    return value.strip() != ""
