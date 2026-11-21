from graphlib import CycleError
from pathlib import Path

import pytest

from sql_test.engine import Engine
from sql_test.engine.catalog.adapters import mapped_sql_folder
from sql_test.engine.relation import AmbiguousRelation
from sql_test.executors.duckdb import DuckDBExecutor

REPOSITORY = Path(__file__).parent / "fixtures" / "repos" / "lakehouse-data-customer"


ROWS = {
    "members": [
        {"member_id": 1, "member_name": "Ada", "lob": "30"},
        {"member_id": 2, "member_name": "Bea", "lob": "10"},
    ],
    "lob": [
        {"lob": "30", "lob_name": "Medicaid"},
        {"lob": "10", "lob_name": "Commercial"},
    ],
}


def _engine() -> Engine:
    return Engine(
        catalog=mapped_sql_folder(
            sqls=REPOSITORY / "admin" / "sqls",
            mapping=REPOSITORY / "admin" / "config" / "lookup_sql_table_mapping.csv",
        ),
        executor=DuckDBExecutor(),
    )


def test_runs_a_tables_sql_over_given_rows():
    result = _engine().run("medicaid_members", rows=ROWS)

    assert result.rows == [{"member_id": 1, "member_name": "Ada"}]


def test_execute_runs_an_existing_plan():
    engine = _engine()
    plan = engine.plan("medicaid_members", rows=ROWS)

    result = engine.execute(plan, rows=ROWS)

    assert result.rows == [{"member_id": 1, "member_name": "Ada"}]
    assert result.counts[plan.target] == 1


def test_runs_upstream_sql_before_the_table():
    engine = Engine(
        catalog=mapped_sql_folder(
            sqls=REPOSITORY / "admin" / "sqls",
            mapping=REPOSITORY / "admin" / "config" / "lookup_sql_table_mapping.csv",
        ),
        executor=DuckDBExecutor(),
    )

    result = engine.run(
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


def test_run_counts_rows_for_each_relation():
    engine = Engine(
        catalog=mapped_sql_folder(
            sqls=REPOSITORY / "admin" / "sqls",
            mapping=REPOSITORY / "admin" / "config" / "lookup_sql_table_mapping.csv",
        ),
        executor=DuckDBExecutor(),
    )

    result = engine.run(
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
            executor=DuckDBExecutor(),
        ).run("a", rows={})


def test_reports_an_ambiguous_table():
    engine = Engine(
        catalog=mapped_sql_folder(
            sqls=REPOSITORY / "admin" / "sqls",
            mapping=REPOSITORY / "admin" / "config" / "lookup_sql_table_mapping.csv",
        ),
        executor=DuckDBExecutor(),
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
        executor=DuckDBExecutor(),
    )

    result = engine.run(
        "members",
        rows={"members": [{"member_id": "1", "member_name": "Ada", "lob": "30"}]},
    )

    assert result.rows == [{"member_id": 1, "member_name": "Ada", "lob": "30"}]
    assert type(result.rows[0]["member_id"]) is int


def test_columns_missing_from_given_rows_are_null():
    engine = Engine(
        catalog=mapped_sql_folder(
            sqls=REPOSITORY / "admin" / "sqls",
            mapping=REPOSITORY / "admin" / "config" / "lookup_sql_table_mapping.csv",
        ),
        executor=DuckDBExecutor(),
    )

    result = engine.run("members", rows={"members": [{"member_id": "1"}]})

    assert result.rows == [{"member_id": 1, "member_name": None, "lob": None}]


def test_run_says_whether_the_target_sql_orders_its_rows(tmp_path):
    (tmp_path / "ddl.sql").write_text(
        "create table ordered (id int);\ncreate table unordered (id int);\n"
    )
    (tmp_path / "ordered.sql").write_text("select 1 as id order by id")
    (tmp_path / "unordered.sql").write_text("select 1 as id")
    mapping = tmp_path / "mapping.csv"
    mapping.write_text(
        "load_type,table_ref,sql_ref\n"
        "historic,ordered,ordered.sql\n"
        "historic,unordered,unordered.sql\n"
    )
    engine = Engine(
        catalog=mapped_sql_folder(sqls=tmp_path, mapping=mapping),
        executor=DuckDBExecutor(),
    )

    assert engine.run("ordered", rows={}).ordered
    assert not engine.run("unordered", rows={}).ordered
