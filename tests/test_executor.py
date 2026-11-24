from concurrent.futures import ThreadPoolExecutor

import pytest

from sql_test.engine.executor import Given
from sql_test.engine.operation import Kind, Operation
from sql_test.engine.relation import Relation
from sql_test.engine.schema import Column
from sql_test.executors import duckdb as duckdb_executor
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


@pytest.fixture(params=["duckdb", "spark"])
def executor(request):
    if request.param == "duckdb":
        return DuckDBExecutor()
    pytest.importorskip("pyspark")
    from sql_test.executors.spark import SparkExecutor

    return SparkExecutor()


def test_loads_given_rows_with_their_schema_types(executor):
    written = executor.run({MEMBERS: GIVEN_MEMBERS}, [])

    assert written == {
        MEMBERS: [
            {"member_id": 1, "member_name": "Ada", "lob": "30"},
            {"member_id": 2, "member_name": "Bea", "lob": "10"},
        ]
    }


class _Recording:
    def __init__(self, connection, statements):
        self._connection = connection
        self._statements = statements

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return self._connection.__exit__(*exc)

    def cursor(self):
        return _Recording(self._connection.cursor(), self._statements)

    def execute(self, sql, *args):
        self._statements.append(sql)
        return self._connection.execute(sql, *args)

    def executemany(self, sql, rows):
        self._statements.extend(sql for _ in rows)
        return self._connection.executemany(sql, rows)


def test_a_mock_of_many_rows_loads_in_one_insert(monkeypatch):
    statements = []
    connect = duckdb_executor.duckdb.connect
    monkeypatch.setattr(
        duckdb_executor.duckdb,
        "connect",
        lambda: _Recording(connect(), statements),
    )
    rows = [
        {"member_id": str(i), "member_name": f"m{i}", "lob": "30"} for i in range(1_000)
    ]

    written = DuckDBExecutor().run(
        {MEMBERS: Given(schema=MEMBERS_SCHEMA, rows=rows)}, []
    )

    assert len(written[MEMBERS]) == 1_000
    assert written[MEMBERS][999] == {
        "member_id": 999,
        "member_name": "m999",
        "lob": "30",
    }
    assert sum(s.lstrip().lower().startswith("insert") for s in statements) == 1


def test_executes_operations_and_returns_what_they_write(executor, tmp_path):
    written = executor.run({MEMBERS: GIVEN_MEMBERS}, [_medicaid(tmp_path)])

    assert written[MEDICAID] == [{"member_id": 1, "member_name": "Ada"}]


def test_two_runs_do_not_share_relations(executor, tmp_path):
    executor.run({MEMBERS: GIVEN_MEMBERS}, [])

    with pytest.raises(
        Exception, match="(?i)members|TABLE_OR_VIEW_NOT_FOUND|does not exist"
    ):
        executor.run({}, [_medicaid(tmp_path)])


def test_concurrent_runs_each_see_only_their_own_rows(executor):
    def run(member_id: int) -> list:
        rows = [{"member_id": member_id, "member_name": "x", "lob": "30"}]
        given = {MEMBERS: Given(schema=MEMBERS_SCHEMA, rows=rows)}
        return executor.run(given, [])[MEMBERS]

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(run, range(32)))

    assert [rows[0]["member_id"] for rows in results] == list(range(32))
    assert all(len(rows) == 1 for rows in results)


def test_a_failed_run_leaves_nothing_behind(executor, tmp_path):
    broken = tmp_path / "broken.sql"
    broken.write_text("select * from nowhere")
    with pytest.raises(Exception, match="nowhere"):
        executor.run(
            {MEMBERS: GIVEN_MEMBERS},
            [Operation(sql_file=broken, writes=MEDICAID, kind=Kind.FULL_LOAD)],
        )

    with pytest.raises(
        Exception, match="(?i)members|TABLE_OR_VIEW_NOT_FOUND|does not exist"
    ):
        executor.run({}, [_medicaid(tmp_path)])


LAKEHOUSE_MEMBERS = Relation(catalog="lakehouse", schema="claims", name="members")
LAKEHOUSE_OUT = Relation(catalog="lakehouse", schema="claims", name="out")
ID_SCHEMA = (Column(name="id", type="INT"),)


def _lakehouse_out(tmp_path) -> Operation:
    sql_file = tmp_path / "out.sql"
    sql_file.write_text("select id from lakehouse.claims.members where id > 1")
    return Operation(sql_file=sql_file, writes=LAKEHOUSE_OUT, kind=Kind.FULL_LOAD)


def test_a_three_level_mock_loads_and_reads_back(executor):
    given = {LAKEHOUSE_MEMBERS: Given(schema=ID_SCHEMA, rows=[{"id": 1}])}

    assert executor.run(given, []) == {LAKEHOUSE_MEMBERS: [{"id": 1}]}


def test_sql_reads_and_writes_three_level_names(executor, tmp_path):
    given = {LAKEHOUSE_MEMBERS: Given(schema=ID_SCHEMA, rows=[{"id": 1}, {"id": 2}])}

    written = executor.run(given, [_lakehouse_out(tmp_path)])

    assert written[LAKEHOUSE_OUT] == [{"id": 2}]


def test_concurrent_three_level_runs_each_see_only_their_own_rows(executor):
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
