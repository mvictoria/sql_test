from pathlib import Path

from sql_test.engine.catalog.adapters import mapped_sql_folder
from sql_test.engine.lineage.graph import upstream_lineage
from sql_test.engine.relation import Relation

REPOSITORY = Path(__file__).parent / "fixtures" / "repos" / "lakehouse-data-customer"


def test_the_alice_lineage_runs_from_sources_through_operations():
    sqls = REPOSITORY / "admin" / "sqls"
    catalog = mapped_sql_folder(
        sqls=sqls,
        mapping=REPOSITORY / "admin" / "config" / "lookup_sql_table_mapping.csv",
    )
    members, lob = Relation(name="members"), Relation(name="lob")
    medicaid = Relation(name="medicaid_members")
    alice = Relation(name="medicaid_members_named_alice")

    lineage = upstream_lineage(alice, catalog)

    assert lineage.sources == {members, lob}
    assert lineage.models == {medicaid, alice}
    assert {
        operation.sql_file.name: (reads, operation.writes)
        for operation, reads in lineage.reads.items()
    } == {
        "medicaid_members.sql": ({members, lob}, medicaid),
        "medicaid_members_named_alice.sql": ({medicaid}, alice),
    }
    assert lineage.projection() == {
        alice: {medicaid},
        medicaid: {members, lob},
        members: set(),
        lob: set(),
    }


def test_a_target_with_no_producer_is_its_own_source(tmp_path: Path):
    mapping = tmp_path / "mapping.csv"
    mapping.write_text("table_ref,sql_ref,load_type\n")
    members = Relation(name="members")

    lineage = upstream_lineage(
        members, mapped_sql_folder(sqls=tmp_path, mapping=mapping)
    )

    assert lineage.sources == {members}
    assert lineage.projection() == {members: set()}
