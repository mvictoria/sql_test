import duckdb
import pytest
from pathlib import Path


@pytest.fixture(scope="function")
def db():
    con = duckdb.connect()
    yield con
    con.close()


def insert_test_data(rows, table_name, db):
    columns = list(rows[0])
    values = ", ".join("(" + ", ".join(["?"] * len(columns)) + ")" for _ in rows)
    params = [row[column] for row in rows for column in columns]
    db.execute(
        f"create table {table_name} as select * from (values {values}) t({', '.join(columns)})",
        params,
    )


@pytest.mark.parametrize(
    ("rows", "table_name"),
    [
        (
            [
                {"member_id": "1", "member_name": "Ada", "lob": "30"},
                {"member_id": "2", "member_name": "Bea", "lob": "10"},
            ],
            "members",
        )
    ],
)
def test_medicaid_members(rows, table_name, db):
    insert_test_data(rows, table_name, db)
    sql = (Path(__file__).parent.parent / "admin" / "sqls" / "medicaid_members.sql").read_text()
    selected = db.execute(sql).fetchall()
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
    ("rows", "table_name"),
    [
        (
            [
                {"member_id": 1, "member_name": "Alice", "lob": "30"},
                {"member_id": 2, "member_name": "Alice", "lob": "10"},
                {"member_id": 3, "member_name": "Bea", "lob": "30"},
            ],
            "members",
        )
    ],
)
def test_medicaid_members_named_alice(rows, table_name, db):
    insert_test_data(rows, table_name, db)
    medicaid_members = (
        Path(__file__).parent.parent / "admin" / "sqls" / "medicaid_members.sql"
    ).read_text()
    db.execute(f"create table medicaid_members as {medicaid_members}")
    sql = (
        Path(__file__).parent.parent / "admin" / "sqls" / "medicaid_members_named_alice.sql"
    ).read_text()
    selected = db.execute(sql).fetchall()
    assert (1, "Alice") in selected
    assert (2, "Alice") not in selected
    assert (3, "Bea") not in selected
