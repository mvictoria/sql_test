from sql_test.engine.lineage.references import tables_read
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
