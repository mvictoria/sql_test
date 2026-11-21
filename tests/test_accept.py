from sql_test.engine import Column
from sql_test.integrations.app.accept import (
    ExpectedRows,
    accept_all,
    accept_cell,
    accept_row,
    remove_row,
)
from sql_test.integrations.app.grid import Cell

SCHEMA = (
    Column(name="member_id", type="INT"),
    Column(name="member_name", type="VARCHAR(30)"),
    Column(name="lob", type="VARCHAR(2)"),
)

ADA: dict[str, Cell] = {"member_id": "1", "member_name": "Ada", "lob": "30"}
BEA: dict[str, Cell] = {"member_id": "2", "member_name": "Bea", "lob": "10"}


def _typed(row: dict) -> dict:
    return {**row, "member_id": int(row["member_id"])}


def test_accepting_all_makes_expected_the_actual_rows():
    actual = [_typed(ADA), {"member_id": 2, "member_name": None, "lob": "10"}]

    assert accept_all(SCHEMA, actual) == [
        ADA,
        {"member_id": "2", "member_name": None, "lob": "10"},
    ]


def test_accepting_all_of_no_rows_leaves_one_blank_row():
    assert accept_all(SCHEMA, []) == [{}]


def test_accepting_a_changed_row_replaces_the_expected_row():
    expected: ExpectedRows = [ADA, {**BEA, "member_name": "Beatrice"}]

    rows = accept_row(
        expected,
        SCHEMA,
        _typed(BEA),
        replacing=_typed({**BEA, "member_name": "Beatrice"}),
    )

    assert rows == [ADA, BEA]


def test_accepting_an_unexpected_row_appends_it():
    assert accept_row([dict(ADA)], SCHEMA, _typed(BEA)) == [ADA, BEA]


def test_accepting_into_a_blank_grid_fills_its_blank_row():
    assert accept_row([{}], SCHEMA, _typed(ADA)) == [ADA]


def test_accepting_a_cell_changes_only_that_cell():
    expected: ExpectedRows = [ADA, {**BEA, "member_name": "Beatrice", "lob": "99"}]
    old = _typed({**BEA, "member_name": "Beatrice", "lob": "99"})

    rows = accept_cell(expected, SCHEMA, old, "member_name", "Bea")

    assert rows == [ADA, {**BEA, "lob": "99"}]


def test_removing_a_missing_row_deletes_it():
    assert remove_row([ADA, BEA], SCHEMA, _typed(BEA)) == [ADA]


def test_removing_the_last_row_leaves_one_blank_row():
    assert remove_row([ADA], SCHEMA, _typed(ADA)) == [{}]


def test_a_row_is_found_whatever_its_cells_are_written_as():
    expected: ExpectedRows = [
        {"member_id": " 1", "member_name": "Ada", "lob": "30"},
        BEA,
    ]

    assert remove_row(expected, SCHEMA, _typed(ADA)) == [BEA]


def test_the_input_rows_are_not_changed():
    expected: ExpectedRows = [ADA, BEA]

    remove_row(expected, SCHEMA, _typed(BEA))
    accept_cell(expected, SCHEMA, _typed(ADA), "lob", "10")

    assert expected == [ADA, BEA]
