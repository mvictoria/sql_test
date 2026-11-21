from typing import Any

from sql_test.engine import Row, Schema
from sql_test.integrations.app.case_load import display_row
from sql_test.integrations.app.compare_view import typed_row
from sql_test.integrations.app.grid import Cell

type ExpectedRows = list[dict[str, Cell]]


def accept_all(schema: Schema, actual: list[Row]) -> ExpectedRows:
    """Expected rows that are exactly the actual result; `[]` expects no rows."""
    return [display_row(row, _columns(schema)) for row in actual]


def accept_row(
    rows: ExpectedRows, schema: Schema, actual: Row, *, replacing: Row | None = None
) -> ExpectedRows:
    """Take an actual row as expected, in place of `replacing` or as a new row."""
    accepted = display_row(actual, _columns(schema))
    if replacing is not None:
        index = _index(rows, schema, replacing)
        return [*rows[:index], accepted, *rows[index + 1 :]]
    return [*_without_blanks(rows), accepted]


def accept_cell(
    rows: ExpectedRows, schema: Schema, expected: Row, column: str, value: Any
) -> ExpectedRows:
    """Take one actual cell as the value of `column` in the expected row."""
    index = _index(rows, schema, expected)
    (cell,) = display_row({column: value}, (column,)).values()
    return [*rows[:index], {**rows[index], column: cell}, *rows[index + 1 :]]


def remove_row(rows: ExpectedRows, schema: Schema, expected: Row) -> ExpectedRows:
    """Drop an expected row the actual result no longer has."""
    index = _index(rows, schema, expected)
    return [*rows[:index], *rows[index + 1 :]]


def _index(rows: ExpectedRows, schema: Schema, expected: Row) -> int:
    for index, row in enumerate(rows):
        if any(_filled(value) for value in row.values()) and (
            typed_row(schema, row) == expected
        ):
            return index
    raise LookupError(f"no expected row is {expected}")


def _without_blanks(rows: ExpectedRows) -> ExpectedRows:
    return [row for row in rows if any(_filled(value) for value in row.values())]


def _filled(value: Cell) -> bool:
    return value is not None and value.strip() != ""


def _columns(schema: Schema) -> tuple[str, ...]:
    return tuple(column.name for column in schema)
