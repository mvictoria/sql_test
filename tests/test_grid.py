from sql_test.engine import Column
from sql_test.integrations.app.grid import (
    apply_grid_action,
    cell_error,
    next_grid_cell,
    previous_grid_cell,
    validate_grid,
)


def test_cell_error_flags_a_non_integer_member_id():
    column = Column(name="member_id", type="INTEGER")

    assert cell_error(column, "abc") == "not INTEGER"
    assert cell_error(column, "1") is None
    assert cell_error(column, None) is None
    assert cell_error(column, "") is None


def test_validate_grid_reports_the_bad_cell():
    schema = (Column(name="member_id", type="INTEGER"),)
    rows: dict[str, list[dict[str, str | None]]] = {"members": [{"member_id": "abc"}]}

    errors = validate_grid({"members": schema}, rows)

    assert errors["members.0.member_id"] == "not INTEGER"


def test_duplicate_row_copies_values_after_the_source():
    rows = apply_grid_action(
        "duplicate:members:0",
        ("members",),
        {"members": [{"member_id": "1", "member_name": "Ada"}]},
    )

    assert rows["members"] == [
        {"member_id": "1", "member_name": "Ada"},
        {"member_id": "1", "member_name": "Ada"},
    ]


def test_next_grid_cell_wraps_to_the_next_row_then_ends():
    columns = ("member_id", "member_name", "lob")

    assert next_grid_cell(columns, 0, "lob", row_count=2) == (1, "member_id")
    assert next_grid_cell(columns, 1, "lob", row_count=2) is None


def test_previous_grid_cell_wraps_to_the_prior_row_then_ends():
    columns = ("member_id", "member_name", "lob")

    assert previous_grid_cell(columns, 1, "member_id") == (0, "lob")
    assert previous_grid_cell(columns, 0, "member_id") is None
