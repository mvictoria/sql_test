from pathlib import Path

import pytest
import sqlglot

from sql_test.engine import Engine
from sql_test.engine.catalog.adapters import mapped_sql_folder
from sql_test.engine.catalog.mapping import read_operations
from sql_test.engine.operation import Kind, Operation
from sql_test.engine.relation import AmbiguousRelation, Relation
from sql_test.executors import DuckDBExecutor

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
        ),
        Operation(
            sql_file=sqls / "medicaid_members_named_alice.sql",
            writes=Relation(name="medicaid_members_named_alice"),
            kind=Kind.FULL_LOAD,
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
        Relation(name="members"),
        Relation(name="lob"),
        Relation(name="medicaid_members"),
        Relation(name="medicaid_members_named_alice"),
    }


def test_a_relation_only_read_by_sql_is_in_the_catalog(tmp_path):
    (tmp_path / "a.sql").write_text("select * from claims.memebrs")
    mapping = tmp_path / "mapping.csv"
    mapping.write_text("load_type,table_ref,sql_ref\nhistoric,a,a.sql\n")

    catalog = mapped_sql_folder(sqls=tmp_path, mapping=mapping)

    assert catalog.relations() == {
        Relation(name="a"),
        Relation(schema="claims", name="memebrs"),
    }


def test_a_bare_reference_resolves_to_a_declared_relation(tmp_path):
    (tmp_path / "ddl.sql").write_text("create table claims.members (id integer)")
    (tmp_path / "a.sql").write_text("select * from members")
    mapping = tmp_path / "mapping.csv"
    mapping.write_text("load_type,table_ref,sql_ref\nhistoric,a,a.sql\n")

    catalog = mapped_sql_folder(sqls=tmp_path, mapping=mapping)

    assert catalog.relations() == {
        Relation(name="a"),
        Relation(schema="claims", name="members"),
    }


def _sample():
    return mapped_sql_folder(
        sqls=REPOSITORY / "admin" / "sqls",
        mapping=REPOSITORY / "admin" / "config" / "lookup_sql_table_mapping.csv",
    )


def test_resolve_finds_the_relation_a_name_refers_to(tmp_path):
    (tmp_path / "ddl.sql").write_text("create table claims.members (id integer)")
    (tmp_path / "a.sql").write_text("select * from members")
    mapping = tmp_path / "mapping.csv"
    mapping.write_text("table_ref,sql_ref\na,a.sql\n")
    catalog = mapped_sql_folder(sqls=tmp_path, mapping=mapping)

    assert catalog.resolve("members") == Relation(schema="claims", name="members")
    assert catalog.resolve("unknown") == Relation(name="unknown")


def test_resolve_reports_an_ambiguous_name(tmp_path):
    (tmp_path / "ddl.sql").write_text(
        "create table claims.members (id integer);\n"
        "create table billing.members (id integer);\n"
    )
    mapping = tmp_path / "mapping.csv"
    mapping.write_text("table_ref,sql_ref\n")
    catalog = mapped_sql_folder(sqls=tmp_path, mapping=mapping)

    with pytest.raises(AmbiguousRelation):
        catalog.resolve("members")


def test_schema_is_the_relations_columns_or_none():
    catalog = _sample()

    schema = catalog.schema(Relation(name="members"))
    assert schema is not None
    assert [column.name for column in schema] == ["member_id", "member_name", "lob"]
    assert catalog.schema(Relation(name="unknown")) is None


def test_producers_are_the_operations_that_write_a_relation():
    catalog = _sample()

    assert [
        operation.sql_file.name
        for operation in catalog.producers(Relation(name="medicaid_members"))
    ] == ["medicaid_members.sql"]
    assert catalog.producers(Relation(name="members")) == ()


def _counting_parses(monkeypatch, marker):
    parsed = []
    parse_one = sqlglot.parse_one

    def counting(sql, *args, **kwargs):
        if marker in sql:
            parsed.append(sql)
        return parse_one(sql, *args, **kwargs)

    monkeypatch.setattr(sqlglot, "parse_one", counting)
    return parsed


def _models(folder, marker):
    sqls = folder / "sqls"
    sqls.mkdir()
    (sqls / "a.sql").write_text(f"-- {marker}\nselect * from members")
    (sqls / "b.sql").write_text(f"-- {marker}\nselect * from a join lob using (id)")
    (sqls / "broken.sql").write_text(f"-- {marker}\nselect from (")
    ddl = folder / "ddl"
    ddl.mkdir()
    (ddl / "members.sql").write_text(
        f"-- {marker}\ncreate table claims.members (id integer)"
    )
    mapping = folder / "mapping.csv"
    mapping.write_text("table_ref,sql_ref\na,a.sql\nb,b.sql\nc,broken.sql\n")
    return lambda: mapped_sql_folder(sqls=sqls, mapping=mapping, schemas=ddl)


def test_resolving_several_names_parses_each_sql_once(tmp_path, monkeypatch):
    catalog = _models(tmp_path, tmp_path.name)()
    parsed = _counting_parses(monkeypatch, tmp_path.name)

    for name in ["members", "a", "b", "lob", "members"]:
        catalog.resolve(name)

    assert len(parsed) == 3


def test_a_new_catalog_over_unchanged_files_parses_nothing(tmp_path, monkeypatch):
    build = _models(tmp_path, tmp_path.name)
    build().resolve("members")
    parsed = _counting_parses(monkeypatch, tmp_path.name)

    build().resolve("members")

    assert parsed == []


def test_a_catalog_built_after_an_edit_sees_the_new_sql(tmp_path):
    build = _models(tmp_path, tmp_path.name)
    assert Relation(name="claims") not in build().relations()

    (tmp_path / "sqls" / "a.sql").write_text("select * from claims")

    assert Relation(name="claims") in build().relations()


def _chain(folder, length):
    (folder / "ddl.sql").write_text(
        "".join(f"create table t{i} (id integer);\n" for i in range(length + 1))
    )
    rows = ["table_ref,sql_ref"]
    for i in range(1, length + 1):
        (folder / f"t{i}.sql").write_text(f"select id from t{i - 1}")
        rows.append(f"t{i},t{i}.sql")
    (folder / "mapping.csv").write_text("\n".join(rows) + "\n")
    return mapped_sql_folder(sqls=folder, mapping=folder / "mapping.csv")


def _counting(monkeypatch, owner, method):
    calls = []
    original = getattr(owner, method)

    def counting(*args, **kwargs):
        calls.append(args)
        return original(*args, **kwargs)

    monkeypatch.setattr(owner, method, counting)
    return calls


def test_resolving_a_name_checks_only_relations_with_that_name(tmp_path, monkeypatch):
    catalog = _chain(tmp_path, 50)
    catalog.relations()
    matched = _counting(monkeypatch, Relation, "matches")

    assert catalog.resolve("t7") == Relation(name="t7")
    assert len(matched) == 1


def test_planning_a_chain_grows_linearly_with_its_length(tmp_path, monkeypatch):
    catalog = _chain(tmp_path, 50)
    matched = _counting(monkeypatch, Relation, "matches")
    compared = _counting(monkeypatch, Relation, "__eq__")

    Engine(catalog, DuckDBExecutor()).plan("t50", {"t0": [{"id": 1}]})

    assert len(matched) < 5 * 50
    assert len(compared) < 5 * 50


def test_parsing_a_name_twice_parses_it_once(monkeypatch):
    parsed = _counting(monkeypatch, sqlglot.exp, "to_table")

    Relation.parse("claims.memoized_once")
    Relation.parse("claims.memoized_once")

    assert len(parsed) == 1
