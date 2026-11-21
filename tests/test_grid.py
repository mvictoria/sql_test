from sql_test.engine import Column
from sql_test.integrations.app.grid import (
    apply_grid_action,
    cell_error,
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
