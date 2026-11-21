from concurrent.futures import ThreadPoolExecutor

import pytest

from sql_test.engine.executor import Given
from sql_test.engine.operation import Kind, Operation
from sql_test.engine.relation import Relation
from sql_test.engine.schema import Column
from sql_test.executors.duckdb import DuckDBExecutor

MEMBERS = Relation(name="members")
MEDICAID = Relation(name="medicaid_members")

MEMBERS_SCHEMA = (
    Column(name="member_id", type="INT"),
    Column(name="member_name", type="VARCHAR(30)"),
    Column(name="lob", type="VARCHAR(2)"),
)

GIVEN_MEMBERS = Given(
    schema=MEMBERS_SCHEMA,
    rows=[
        {"member_id": "1", "member_name": "Ada", "lob": "30"},
        {"member_id": "2", "member_name": "Bea", "lob": "10"},
    ],
)


def _medicaid(tmp_path) -> Operation:
    sql_file = tmp_path / "medicaid_members.sql"
    sql_file.write_text("select member_id, member_name from members where lob = '30'")
    return Operation(sql_file=sql_file, writes=MEDICAID, kind=Kind.FULL_LOAD)


def test_loads_given_rows_with_their_schema_types():
    written = DuckDBExecutor().run({MEMBERS: GIVEN_MEMBERS}, [])

    assert written == {
        MEMBERS: [
            {"member_id": 1, "member_name": "Ada", "lob": "30"},
            {"member_id": 2, "member_name": "Bea", "lob": "10"},
        ]
    }


def test_executes_operations_and_returns_what_they_write(tmp_path):
    written = DuckDBExecutor().run({MEMBERS: GIVEN_MEMBERS}, [_medicaid(tmp_path)])

    assert written[MEDICAID] == [{"member_id": 1, "member_name": "Ada"}]


def test_two_runs_do_not_share_relations(tmp_path):
    executor = DuckDBExecutor()
    executor.run({MEMBERS: GIVEN_MEMBERS}, [])

    with pytest.raises(Exception, match="(?i)members|Catalog Error|does not exist"):
        executor.run({}, [_medicaid(tmp_path)])


def test_concurrent_runs_each_see_only_their_own_rows():
    executor = DuckDBExecutor()

    def run(member_id: int) -> list:
        rows = [{"member_id": member_id, "member_name": "x", "lob": "30"}]
        given = {MEMBERS: Given(schema=MEMBERS_SCHEMA, rows=rows)}
        return executor.run(given, [])[MEMBERS]

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(run, range(32)))

    assert [rows[0]["member_id"] for rows in results] == list(range(32))
    assert all(len(rows) == 1 for rows in results)


def test_a_failed_run_leaves_nothing_behind(tmp_path):
    executor = DuckDBExecutor()
    broken = tmp_path / "broken.sql"
    broken.write_text("select * from nowhere")
    with pytest.raises(Exception, match="nowhere"):
        executor.run(
            {MEMBERS: GIVEN_MEMBERS},
            [Operation(sql_file=broken, writes=MEDICAID, kind=Kind.FULL_LOAD)],
        )

    with pytest.raises(Exception, match="(?i)members|Catalog Error|does not exist"):
        executor.run({}, [_medicaid(tmp_path)])


LAKEHOUSE_MEMBERS = Relation(catalog="lakehouse", schema="claims", name="members")
LAKEHOUSE_OUT = Relation(catalog="lakehouse", schema="claims", name="out")
ID_SCHEMA = (Column(name="id", type="INT"),)


def _lakehouse_out(tmp_path) -> Operation:
    sql_file = tmp_path / "out.sql"
    sql_file.write_text("select id from lakehouse.claims.members where id > 1")
    return Operation(sql_file=sql_file, writes=LAKEHOUSE_OUT, kind=Kind.FULL_LOAD)


def test_a_three_level_mock_loads_and_reads_back():
    given = {LAKEHOUSE_MEMBERS: Given(schema=ID_SCHEMA, rows=[{"id": 1}])}

    assert DuckDBExecutor().run(given, []) == {LAKEHOUSE_MEMBERS: [{"id": 1}]}


def test_sql_reads_and_writes_three_level_names(tmp_path):
    given = {LAKEHOUSE_MEMBERS: Given(schema=ID_SCHEMA, rows=[{"id": 1}, {"id": 2}])}

    written = DuckDBExecutor().run(given, [_lakehouse_out(tmp_path)])

    assert written[LAKEHOUSE_OUT] == [{"id": 2}]


def test_concurrent_three_level_runs_each_see_only_their_own_rows():
    executor = DuckDBExecutor()

    def run(member_id: int) -> list:
        given = {LAKEHOUSE_MEMBERS: Given(schema=ID_SCHEMA, rows=[{"id": member_id}])}
        return executor.run(given, [])[LAKEHOUSE_MEMBERS]

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(run, range(32)))

    assert results == [[{"id": member_id}] for member_id in range(32)]


@pytest.mark.parametrize("catalog", ["memory", "system", "temp", "Memory"])
def test_a_relation_in_a_duckdb_database_name_is_an_error(catalog):
    relation = Relation(catalog=catalog, schema="claims", name="members")

    with pytest.raises(ValueError, match=f"{catalog}.claims.members"):
        DuckDBExecutor().run({relation: Given(schema=ID_SCHEMA, rows=[])}, [])
