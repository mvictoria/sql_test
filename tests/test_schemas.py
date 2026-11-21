from pathlib import Path

from sql_test.engine.catalog.ddl import read_ddl_schemas
from sql_test.engine.relation import Relation
from sql_test.engine.schema import Column

REPOSITORY = Path(__file__).parent / "fixtures" / "repos" / "lakehouse-data-customer"


def test_reads_every_table_defined_in_the_sql_folder():
    discovered = read_ddl_schemas(REPOSITORY / "admin" / "sqls")

    assert set(discovered.schemas) == {
        Relation(name="members"),
        Relation(name="lob"),
        Relation(name="medicaid_members"),
        Relation(name="medicaid_members_named_alice"),
    }
    assert discovered.schemas[Relation(name="members")] == (
        Column(name="member_id", type="INT"),
        Column(name="member_name", type="VARCHAR(30)"),
        Column(name="lob", type="VARCHAR(2)"),
    )
    assert discovered.problems == []


def test_a_type_written_as_text_matches_the_same_type_in_ddl(tmp_path):
    (tmp_path / "ddl.sql").write_text("create table t (a integer, b varchar(30))")

    from_ddl = read_ddl_schemas(tmp_path).schemas[Relation(name="t")]

    assert from_ddl == (Column.parse("a", "INT"), Column.parse("b", "varchar(30)"))


def test_an_unparseable_statement_is_reported_and_the_rest_still_read(tmp_path):
    ddl = tmp_path / "ddl.sql"
    ddl.write_text(
        "create table a (id integer);\n"
        "create table (id integer);\n"
        "create table b (id integer);\n"
    )

    discovered = read_ddl_schemas(tmp_path)

    assert set(discovered.schemas) == {Relation(name="a"), Relation(name="b")}
    assert [problem.file for problem in discovered.problems] == [ddl]


def test_a_relation_defined_twice_is_reported_and_the_first_kept(tmp_path):
    (tmp_path / "a.sql").write_text("create table claims.t (id integer);;")
    (tmp_path / "b.sql").write_text("create table Claims.T (id varchar(10))")

    discovered = read_ddl_schemas(tmp_path)

    assert discovered.schemas == {
        Relation(schema="claims", name="t"): (Column(name="id", type="INT"),)
    }
    assert [problem.file.name for problem in discovered.problems] == ["b.sql"]
    assert "claims.t" in discovered.problems[0].reason
