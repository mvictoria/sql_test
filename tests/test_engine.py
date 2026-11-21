from graphlib import CycleError
from pathlib import Path

import pytest

from sql_test.engine import Engine
from sql_test.engine.catalog.adapters import mapped_sql_folder
from sql_test.engine.relation import AmbiguousRelation
from sql_test.executors.duckdb import DuckDBExecutor

REPOSITORY = Path(__file__).parent / "fixtures" / "repos" / "lakehouse-data-customer"


def test_runs_a_tables_sql_over_given_rows():
    engine = Engine(
        catalog=mapped_sql_folder(
            sqls=REPOSITORY / "admin" / "sqls",
            mapping=REPOSITORY / "admin" / "config" / "lookup_sql_table_mapping.csv",
        ),
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
        catalog=mapped_sql_folder(
            sqls=REPOSITORY / "admin" / "sqls",
            mapping=REPOSITORY / "admin" / "config" / "lookup_sql_table_mapping.csv",
        ),
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


def test_run_result_includes_row_counts_for_each_relation():
    engine = Engine(
        catalog=mapped_sql_folder(
            sqls=REPOSITORY / "admin" / "sqls",
            mapping=REPOSITORY / "admin" / "config" / "lookup_sql_table_mapping.csv",
        ),
        executor=DuckDBExecutor,
    )

    result = engine.run_result(
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

    assert result.rows == [{"member_id": 1, "member_name": "Alice"}]
    assert {str(relation): count for relation, count in result.counts.items()} == {
        "members": 3,
        "lob": 2,
        "medicaid_members": 2,
        "medicaid_members_named_alice": 1,
    }


def test_reports_a_cycle(tmp_path):
    (tmp_path / "ddl.sql").write_text(
        "create table a (id int);\ncreate table b (id int);\n"
    )
    (tmp_path / "a.sql").write_text("select * from b")
    (tmp_path / "b.sql").write_text("select * from a")
    mapping = tmp_path / "mapping.csv"
    mapping.write_text(
        "load_type,table_ref,sql_ref\nhistoric,a,a.sql\nhistoric,b,b.sql\n"
    )

    with pytest.raises(CycleError):
        Engine(
            catalog=mapped_sql_folder(sqls=tmp_path, mapping=mapping),
            executor=DuckDBExecutor,
        ).run("a", rows={})


def test_reports_an_ambiguous_table():
    engine = Engine(
        catalog=mapped_sql_folder(
            sqls=REPOSITORY / "admin" / "sqls",
            mapping=REPOSITORY / "admin" / "config" / "lookup_sql_table_mapping.csv",
        ),
        executor=DuckDBExecutor,
    )

    with pytest.raises(AmbiguousRelation, match="billing.members.*claims.members"):
        engine.run(
            "members",
            rows={
                "claims.members": [{"member_id": 1}],
                "billing.members": [{"member_id": 2}],
            },
        )


def test_given_rows_load_with_their_schema_types():
    engine = Engine(
        catalog=mapped_sql_folder(
            sqls=REPOSITORY / "admin" / "sqls",
            mapping=REPOSITORY / "admin" / "config" / "lookup_sql_table_mapping.csv",
        ),
        executor=DuckDBExecutor,
    )

    rows = engine.run(
        "members",
        rows={"members": [{"member_id": "1", "member_name": "Ada", "lob": "30"}]},
    )

    assert rows == [(1, "Ada", "30")]
    assert type(rows[0][0]) is int


def test_columns_missing_from_given_rows_are_null():
    engine = Engine(
        catalog=mapped_sql_folder(
            sqls=REPOSITORY / "admin" / "sqls",
            mapping=REPOSITORY / "admin" / "config" / "lookup_sql_table_mapping.csv",
        ),
        executor=DuckDBExecutor,
    )

    rows = engine.run("members", rows={"members": [{"member_id": "1"}]})

    assert rows == [(1, None, None)]
