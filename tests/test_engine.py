from graphlib import CycleError
from pathlib import Path

import pytest

from sql_test.engine import Engine
from sql_test.executors.duckdb import DuckDBExecutor

REPOSITORY = Path(__file__).parent / "fixtures" / "repos" / "lakehouse-data-customer"


def test_runs_a_tables_sql_over_given_rows():
    engine = Engine(
        sqls=REPOSITORY / "admin" / "sqls",
        mapping=REPOSITORY / "admin" / "config" / "lookup_sql_table_mapping.csv",
        executor=DuckDBExecutor,
    )

    rows = engine.run(
        "medicaid_members",
        rows={
            "members": [
                {"member_id": 1, "member_name": "Ada", "lob": "30"},
                {"member_id": 2, "member_name": "Bea", "lob": "10"},
            ],
            "lob": [
                {"lob": "30", "lob_name": "Medicaid"},
                {"lob": "10", "lob_name": "Commercial"},
            ],
        },
    )

    assert rows == [(1, "Ada")]


def test_runs_upstream_sql_before_the_table():
    engine = Engine(
        sqls=REPOSITORY / "admin" / "sqls",
        mapping=REPOSITORY / "admin" / "config" / "lookup_sql_table_mapping.csv",
        executor=DuckDBExecutor,
    )

    rows = engine.run(
        "medicaid_members_named_alice",
        rows={
            "members": [
                {"member_id": 1, "member_name": "Alice", "lob": "30"},
                {"member_id": 2, "member_name": "Alice", "lob": "10"},
                {"member_id": 3, "member_name": "Bea", "lob": "30"},
            ],
            "lob": [
                {"lob": "30", "lob_name": "Medicaid"},
                {"lob": "10", "lob_name": "Commercial"},
            ],
        },
    )

    assert rows == [(1, "Alice")]


def test_reports_a_cycle(tmp_path):
    (tmp_path / "a.sql").write_text("select * from b")
    (tmp_path / "b.sql").write_text("select * from a")
    mapping = tmp_path / "mapping.csv"
    mapping.write_text(
        "load_type,table_ref,sql_ref\nhistoric,a,a.sql\nhistoric,b,b.sql\n"
    )

    with pytest.raises(CycleError):
        Engine(sqls=tmp_path, mapping=mapping, executor=DuckDBExecutor).run(
            "a", rows={}
        )
