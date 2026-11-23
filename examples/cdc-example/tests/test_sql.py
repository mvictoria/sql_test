import pytest


@pytest.mark.parametrize(
    "tables",
    [
        {
            "members": [
                {"member_id": "1", "member_name": "Ada", "lob": "30"},
                {"member_id": "2", "member_name": "Bea", "lob": "10"},
            ],
            "lob": [
                {"lob": "30", "lob_name": "Medicaid"},
                {"lob": "10", "lob_name": "Commercial"},
            ],
        }
    ],
)
def test_medicaid_members(tables, engine):
    selected = engine.run("medicaid_members", rows=tables).rows
    assert {"member_id": 1, "member_name": "Ada"} in selected
    assert {"member_id": 2, "member_name": "Bea"} not in selected


def test_medicaid_members_types(engine):
    member = engine.run(
        "members",
        rows={"members": [{"member_id": "1", "member_name": "Ada", "lob": "30"}]},
    ).rows[0]
    assert type(member["member_id"]) is int
    assert type(member["member_name"]) is str
    assert type(member["lob"]) is str


@pytest.mark.parametrize(
    "tables",
    [
        {
            "members": [
                {"member_id": 1, "member_name": "Alice", "lob": "30"},
                {"member_id": 2, "member_name": "Alice", "lob": "10"},
                {"member_id": 3, "member_name": "Bea", "lob": "30"},
            ],
            "lob": [
                {"lob": "30", "lob_name": "Medicaid"},
                {"lob": "10", "lob_name": "Commercial"},
            ],
        }
    ],
)
def test_medicaid_members_named_alice(tables, engine):
    selected = engine.run("medicaid_members_named_alice", rows=tables).rows
    assert {"member_id": 1, "member_name": "Alice"} in selected
    assert {"member_id": 2, "member_name": "Alice"} not in selected
    assert {"member_id": 3, "member_name": "Bea"} not in selected
