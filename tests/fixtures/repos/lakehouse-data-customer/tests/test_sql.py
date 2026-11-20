from pathlib import Path

import duckdb
import pytest

from sql_test.engine import Engine


@pytest.fixture(scope="function")
def db():
    con = duckdb.connect()
    yield con
    con.close()


@pytest.fixture(scope="function")
def engine():
    admin = Path(__file__).parent.parent / "admin"
    return Engine(
        sqls=admin / "sqls",
        mapping=admin / "config" / "lookup_sql_table_mapping.csv",
    )


def insert_test_data(rows, table_name, db):
    columns = list(rows[0])
    values = ", ".join("(" + ", ".join(["?"] * len(columns)) + ")" for _ in rows)
    params = [row[column] for row in rows for column in columns]
    db.execute(
        f"create table {table_name} as select * from (values {values}) t({', '.join(columns)})",
        params,
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
    assert ("1", "Ada") in selected
    assert ("2", "Bea") not in selected


@pytest.mark.parametrize(
    ("rows", "table_name"),
    [
        (
            [{"member_id": 1, "member_name": "a" * 30, "lob": "30"}],
            "members",
        )
    ],
)
def test_medicaid_members_types(rows, table_name, db):
    insert_test_data(rows, table_name, db)
    member_id, member_name, lob = db.execute(f"select * from {table_name}").fetchone()
    assert type(member_id) is int
    assert type(member_name) is str and len(member_name) == 30
    assert type(lob) is str and len(lob) == 2


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
