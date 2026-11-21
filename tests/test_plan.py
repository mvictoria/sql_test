from pathlib import Path

import pytest

from sql_test.engine import Engine
from sql_test.engine.catalog.adapters import mapped_sql_folder
from sql_test.engine.planner.plan import MissingRows, State, plan_run
from sql_test.engine.relation import Relation
from sql_test.executors.duckdb import DuckDBExecutor

REPOSITORY = Path(__file__).parent / "fixtures" / "repos" / "lakehouse-data-customer"


def test_giving_an_upstream_model_prunes_what_is_behind_it():
    catalog = mapped_sql_folder(
        sqls=REPOSITORY / "admin" / "sqls",
        mapping=REPOSITORY / "admin" / "config" / "lookup_sql_table_mapping.csv",
    )
    medicaid = Relation(name="medicaid_members")
    alice = Relation(name="medicaid_members_named_alice")

    plan = plan_run(alice, catalog, given={medicaid: 1})

    assert plan.states == {
        alice: State.EXECUTED,
        medicaid: State.GIVEN,
        Relation(name="members"): State.PRUNED,
        Relation(name="lob"): State.PRUNED,
    }
    assert [operation.sql_file.name for operation in plan.operations] == [
        "medicaid_members_named_alice.sql"
    ]
    assert plan.needs_rows == set()


def test_a_diamond_keeps_what_another_path_still_needs(tmp_path: Path):
    (tmp_path / "ddl.sql").write_text(
        "".join(
            f"create table {name} (id int);\n"
            for name in ("base", "left_side", "right_side", "top")
        )
    )
    (tmp_path / "base.sql").write_text("select * from raw")
    (tmp_path / "left_side.sql").write_text("select * from base")
    (tmp_path / "right_side.sql").write_text("select * from base")
    (tmp_path / "top.sql").write_text("select * from left_side, right_side")
    mapping = tmp_path / "mapping.csv"
    mapping.write_text(
        "table_ref,sql_ref\n"
        "base,base.sql\nleft_side,left_side.sql\n"
        "right_side,right_side.sql\ntop,top.sql\n"
    )
    catalog = mapped_sql_folder(sqls=tmp_path, mapping=mapping)

    plan = plan_run(
        Relation(name="top"), catalog, given={Relation(name="left_side"): 1}
    )

    assert plan.states == {
        Relation(name="top"): State.EXECUTED,
        Relation(name="left_side"): State.GIVEN,
        Relation(name="right_side"): State.EXECUTED,
        Relation(name="base"): State.EXECUTED,
        Relation(name="raw"): State.SOURCE,
    }
    assert [operation.sql_file.name for operation in plan.operations] == [
        "base.sql",
        "right_side.sql",
        "top.sql",
    ]


def test_a_source_behind_a_mock_stays_pruned_even_if_also_given():
    catalog = mapped_sql_folder(
        sqls=REPOSITORY / "admin" / "sqls",
        mapping=REPOSITORY / "admin" / "config" / "lookup_sql_table_mapping.csv",
    )
    medicaid = Relation(name="medicaid_members")
    members = Relation(name="members")
    alice = Relation(name="medicaid_members_named_alice")

    plan = plan_run(alice, catalog, given={medicaid: 1, members: 1})

    # Mocking medicaid prunes members; a given on a pruned leaf is unused.
    assert plan.states[members] is State.PRUNED
    assert plan.states[Relation(name="lob")] is State.PRUNED
    assert plan.needs_rows == set()


def test_a_given_relation_upstream_of_another_given_is_unused():
    catalog = mapped_sql_folder(
        sqls=REPOSITORY / "admin" / "sqls",
        mapping=REPOSITORY / "admin" / "config" / "lookup_sql_table_mapping.csv",
    )
    medicaid = Relation(name="medicaid_members")
    members = Relation(name="members")
    alice = Relation(name="medicaid_members_named_alice")

    plan = plan_run(alice, catalog, given={medicaid: 1, members: 1})

    assert plan.unused == {members}


def test_a_given_relation_outside_the_lineage_is_unused():
    catalog = mapped_sql_folder(
        sqls=REPOSITORY / "admin" / "sqls",
        mapping=REPOSITORY / "admin" / "config" / "lookup_sql_table_mapping.csv",
    )
    unrelated = Relation(name="unrelated")

    plan = plan_run(
        Relation(name="medicaid_members"),
        catalog,
        given={Relation(name="members"): 1, Relation(name="lob"): 1, unrelated: 1},
    )

    assert plan.unused == {unrelated}


def test_a_given_relation_another_path_still_reads_is_used(tmp_path: Path):
    (tmp_path / "ddl.sql").write_text(
        "".join(
            f"create table {name} (id int);\n" for name in ("base", "middle", "top")
        )
    )
    (tmp_path / "middle.sql").write_text("select * from base")
    (tmp_path / "top.sql").write_text("select * from middle, base")
    mapping = tmp_path / "mapping.csv"
    mapping.write_text("table_ref,sql_ref\nmiddle,middle.sql\ntop,top.sql\n")
    catalog = mapped_sql_folder(sqls=tmp_path, mapping=mapping)

    plan = plan_run(
        Relation(name="top"),
        catalog,
        given={Relation(name="middle"): 1, Relation(name="base"): 1},
    )

    assert plan.unused == set()


def test_reports_the_relations_that_still_need_rows():
    catalog = mapped_sql_folder(
        sqls=REPOSITORY / "admin" / "sqls",
        mapping=REPOSITORY / "admin" / "config" / "lookup_sql_table_mapping.csv",
    )
    members, lob = Relation(name="members"), Relation(name="lob")
    alice = Relation(name="medicaid_members_named_alice")

    assert plan_run(alice, catalog, given={}).needs_rows == {members, lob}
    assert plan_run(alice, catalog, given={members: 0, lob: 2}).needs_rows == {members}


def test_running_without_the_rows_it_needs_names_them():
    engine = Engine(
        catalog=mapped_sql_folder(
            sqls=REPOSITORY / "admin" / "sqls",
            mapping=REPOSITORY / "admin" / "config" / "lookup_sql_table_mapping.csv",
        ),
        executor=DuckDBExecutor(),
    )

    with pytest.raises(MissingRows, match="lob, members"):
        engine.run("medicaid_members_named_alice", rows={})
