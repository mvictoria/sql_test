from pathlib import Path

from sql_test.engine.catalog import Evidence
from sql_test.engine.catalog.adapters import mapped_sql_folder
from sql_test.engine.catalog.mapping import read_operations
from sql_test.engine.operation import Kind, Operation
from sql_test.engine.relation import Relation

REPOSITORY = Path(__file__).parent / "fixtures" / "repos" / "lakehouse-data-customer"


def test_mapped_sql_files_are_full_load_operations():
    sqls = REPOSITORY / "admin" / "sqls"

    operations = read_operations(
        mapping=REPOSITORY / "admin" / "config" / "lookup_sql_table_mapping.csv",
        sqls=sqls,
    )

    assert sorted(operations, key=lambda operation: operation.writes.name) == [
        Operation(
            sql_file=sqls / "medicaid_members.sql",
            writes=Relation(name="medicaid_members"),
            kind=Kind.FULL_LOAD,
            load_type="historic",
        ),
        Operation(
            sql_file=sqls / "medicaid_members_named_alice.sql",
            writes=Relation(name="medicaid_members_named_alice"),
            kind=Kind.FULL_LOAD,
            load_type="historic",
        ),
    ]


def test_a_relation_mapped_to_two_files_has_two_operations(tmp_path):
    (tmp_path / "first.sql").write_text("select 1 as id")
    (tmp_path / "second.sql").write_text("select 2 as id")
    mapping = tmp_path / "mapping.csv"
    mapping.write_text(
        "load_type,table_ref,sql_ref\n"
        "historic,claims.ids,first.sql\n"
        "historic,claims.ids,second.sql\n"
    )

    operations = read_operations(mapping=mapping, sqls=tmp_path)

    assert [operation.sql_file.name for operation in operations] == [
        "first.sql",
        "second.sql",
    ]
    assert {operation.writes for operation in operations} == {
        Relation(schema="claims", name="ids")
    }


def test_every_relation_in_the_sample_repository_is_declared():
    catalog = mapped_sql_folder(
        sqls=REPOSITORY / "admin" / "sqls",
        mapping=REPOSITORY / "admin" / "config" / "lookup_sql_table_mapping.csv",
    )

    assert catalog.relations() == {
        Relation(name="members"): Evidence.DECLARED,
        Relation(name="lob"): Evidence.DECLARED,
        Relation(name="medicaid_members"): Evidence.DECLARED,
        Relation(name="medicaid_members_named_alice"): Evidence.DECLARED,
    }


def test_a_relation_only_read_by_sql_is_inferred(tmp_path):
    (tmp_path / "a.sql").write_text("select * from claims.memebrs")
    mapping = tmp_path / "mapping.csv"
    mapping.write_text("load_type,table_ref,sql_ref\nhistoric,a,a.sql\n")

    catalog = mapped_sql_folder(sqls=tmp_path, mapping=mapping)

    assert catalog.relations() == {
        Relation(name="a"): Evidence.DECLARED,
        Relation(schema="claims", name="memebrs"): Evidence.INFERRED,
    }


def test_a_bare_reference_resolves_to_a_declared_relation(tmp_path):
    (tmp_path / "ddl.sql").write_text("create table claims.members (id integer)")
    (tmp_path / "a.sql").write_text("select * from members")
    mapping = tmp_path / "mapping.csv"
    mapping.write_text("load_type,table_ref,sql_ref\nhistoric,a,a.sql\n")

    catalog = mapped_sql_folder(sqls=tmp_path, mapping=mapping)

    assert catalog.relations() == {
        Relation(name="a"): Evidence.DECLARED,
        Relation(schema="claims", name="members"): Evidence.DECLARED,
    }
