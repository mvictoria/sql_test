from pathlib import Path

from sql_test.engine.lineage.references import ends_in_order_by, tables_read
from sql_test.engine.relation import Relation


def test_table_references_keep_their_qualification():
    sql = """
        select *
        from lakehouse.claims.members
        inner join billing.members on true
        inner join lob on true
    """

    assert tables_read(sql) == {
        Relation(catalog="lakehouse", schema="claims", name="members"),
        Relation(schema="billing", name="members"),
        Relation(name="lob"),
    }


def test_a_cte_is_not_a_table():
    sql = """
        with recent as (select * from claims.members)
        select * from recent inner join lob on true
    """

    assert tables_read(sql) == {
        Relation(schema="claims", name="members"),
        Relation(name="lob"),
    }


def test_the_sample_queries_read_their_upstream_tables():
    sqls = (
        Path(__file__).parent
        / "fixtures"
        / "repos"
        / "lakehouse-data-customer"
        / "admin"
        / "sqls"
    )

    assert tables_read((sqls / "medicaid_members.sql").read_text()) == {
        Relation(name="members"),
        Relation(name="lob"),
    }
    assert tables_read((sqls / "medicaid_members_named_alice.sql").read_text()) == {
        Relation(name="medicaid_members")
    }


def test_only_a_top_level_order_by_orders_the_result():
    assert ends_in_order_by("select * from members order by member_id")
    assert not ends_in_order_by(
        "select * from (select * from members order by member_id) as m"
    )
