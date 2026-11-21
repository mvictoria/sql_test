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
