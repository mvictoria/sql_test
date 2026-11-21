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
    has_expected = bool(filled)
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
    if not aligned and not actual:
        return DiffPanel(columns=columns, has_expected=False, comparison=None)
    typed_rows = _typed_rows(schema, aligned)
    expected = CaseTable(columns=columns, rows=typed_rows)
    comparison = compare(expected, actual, ordered=ordered)
    return DiffPanel(
        columns=columns,
        has_expected=has_expected,
        comparison=comparison,
    )


def _typed_rows(
    schema: Schema,
    rows: list[dict[str, str | None]],
) -> list[Row]:
    typed: list[Row] = []
    for row in rows:
        typed.append(
            {
                column.name: (
                    None
                    if row.get(column.name) is None or row.get(column.name) == ""
                    else column.cast(row.get(column.name))
                )
                for column in schema
            }
        )
    return typed


def target_schema(repo_catalog: Catalog, target: str) -> Schema | None:
    return repo_catalog.schema(repo_catalog.resolve(target))


def _filled(value: str | None) -> bool:
    if value is None:
        return False
    return value.strip() != ""
