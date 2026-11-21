import pytest

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


def test_creates_a_relation_from_a_schema_and_rows():
    executor = DuckDBExecutor()
    executor.setup()
    try:
        executor.create_relation(
            MEMBERS,
            MEMBERS_SCHEMA,
            [
                {"member_id": 1, "member_name": "Ada", "lob": "30"},
                {"member_id": 2, "member_name": "Bea", "lob": "10"},
            ],
        )

        assert executor.read_relation(MEMBERS) == [
            (1, "Ada", "30"),
            (2, "Bea", "10"),
        ]
    finally:
        executor.teardown()


def test_executes_a_full_load_operation(tmp_path):
    sql_file = tmp_path / "medicaid_members.sql"
    sql_file.write_text("select member_id, member_name from members where lob = '30'")
    operation = Operation(
        sql_file=sql_file,
        writes=MEDICAID,
        kind=Kind.FULL_LOAD,
    )

    executor = DuckDBExecutor()
    executor.setup()
    try:
        executor.create_relation(
            MEMBERS,
            MEMBERS_SCHEMA,
            [
                {"member_id": 1, "member_name": "Ada", "lob": "30"},
                {"member_id": 2, "member_name": "Bea", "lob": "10"},
            ],
        )
        executor.execute(operation)

        assert executor.read_relation(MEDICAID) == [(1, "Ada")]
    finally:
        executor.teardown()


def test_two_runs_do_not_share_relations():
    first = DuckDBExecutor()
    first.setup()
    first.create_relation(
        MEMBERS,
        MEMBERS_SCHEMA,
        [{"member_id": 1, "member_name": "Ada", "lob": "30"}],
    )

    second = DuckDBExecutor()
    second.setup()
    try:
        with pytest.raises(Exception, match="(?i)members|Catalog Error|does not exist"):
            second.read_relation(MEMBERS)
    finally:
        first.teardown()
        second.teardown()
