from pathlib import Path

import pytest

from sql_test.engine import Engine
from sql_test.engine.catalog.adapters import mapped_sql_folder
from sql_test.executors.duckdb import DuckDBExecutor


@pytest.fixture(scope="function")
def engine():
    admin = Path(__file__).parent.parent / "admin"
    return Engine(
        catalog=mapped_sql_folder(
            sqls=admin / "sqls",
            mapping=admin / "config" / "lookup_sql_table_mapping.csv",
        ),
        executor=DuckDBExecutor,
    )


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
    selected = engine.run("medicaid_members", rows=tables)
    assert (1, "Ada") in selected
    assert (2, "Bea") not in selected


def test_medicaid_members_types(engine):
    rows = engine.run(
        "members",
        rows={"members": [{"member_id": "1", "member_name": "Ada", "lob": "30"}]},
    )
    member_id, member_name, lob = rows[0]
    assert type(member_id) is int
    assert type(member_name) is str
    assert type(lob) is str


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
    selected = engine.run("medicaid_members_named_alice", rows=tables)
    assert (1, "Alice") in selected
    assert (2, "Alice") not in selected
    assert (3, "Bea") not in selected
