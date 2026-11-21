from dataclasses import dataclass
from pathlib import Path

from sql_test.engine.executor import Given, Row
from sql_test.engine.schema import Schema
from sql_test.executors.duckdb import DuckDBExecutor
from sql_test.integrations.app.engine_access import catalog
from sql_test.testing.cases import CaseTable
from sql_test.testing.comparison import Comparison, compare


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
    repository: Path,
    target: str,
    expected_rows: list[dict[str, str | None]],
    actual: list[Row],
) -> DiffPanel:
    schema = target_schema(repository, target)
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
    typed_rows = _load_typed_rows(repository, target, schema, aligned)
    expected = CaseTable(columns=columns, rows=typed_rows)
    comparison = compare(expected, actual)
    return DiffPanel(
        columns=columns,
        has_expected=has_expected,
        comparison=comparison,
    )


def _load_typed_rows(
    repository: Path,
    target: str,
    schema: Schema,
    rows: list[dict[str, str | None]],
) -> list[Row]:
    if not rows:
        return []
    repo_catalog = catalog(repository)
    relation = repo_catalog.resolve(target)
    return DuckDBExecutor().run({relation: Given(schema, rows)}, [])[relation]


def target_schema(repository: Path, target: str) -> Schema | None:
    repo_catalog = catalog(repository)
    return repo_catalog.schema(repo_catalog.resolve(target))


def _filled(value: str | None) -> bool:
    if value is None:
        return False
    return value.strip() != ""
