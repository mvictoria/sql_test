from pathlib import Path
from typing import Any

from sql_test.engine import Engine
from sql_test.engine.catalog.adapters import mapped_sql_folder
from sql_test.engine.executor import Row
from sql_test.engine.planner.plan import Plan
from sql_test.executors.duckdb import DuckDBExecutor
from sql_test.testing.run import run_case

REPOSITORY = Path(__file__).parent / "fixtures" / "repos" / "lakehouse-data-customer"


def _engine() -> Engine:
    return Engine(
        catalog=mapped_sql_folder(
            sqls=REPOSITORY / "admin" / "sqls",
            mapping=REPOSITORY / "admin" / "config" / "lookup_sql_table_mapping.csv",
        ),
        executor=DuckDBExecutor(),
    )


class _CountingEngine(Engine):
    """Counts plan calls so run_case cannot hide a second plan inside run."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.plan_calls = 0

    def plan(
        self, table: str, rows: dict[str, list[Row]], *, with_pruned: bool = False
    ) -> Plan:
        self.plan_calls += 1
        return super().plan(table, rows, with_pruned=with_pruned)


def _case(root: Path, files: dict[str, str]) -> Path:
    folder = root / "cases" / "medicaid_members" / "ada"
    folder.mkdir(parents=True)
    for name, text in files.items():
        (folder / name).write_text(text)
    return folder


MOCKS = {
    "members.csv": "member_id,member_name,lob\n1,Ada,30\n2,Bea,10\n",
    "lob.csv": "lob,lob_name\n30,Medicaid\n10,Commercial\n",
}


def test_a_passing_case(tmp_path: Path):
    folder = _case(tmp_path, MOCKS | {"expected.csv": "member_id,member_name\n1,Ada\n"})

    result = run_case(folder, _engine())

    assert result.passed
    assert result.actual == [{"member_id": 1, "member_name": "Ada"}]


def test_a_passing_case_plans_only_once(tmp_path: Path):
    folder = _case(tmp_path, MOCKS | {"expected.csv": "member_id,member_name\n1,Ada\n"})
    engine = _CountingEngine(
        catalog=mapped_sql_folder(
            sqls=REPOSITORY / "admin" / "sqls",
            mapping=REPOSITORY / "admin" / "config" / "lookup_sql_table_mapping.csv",
        ),
        executor=DuckDBExecutor(),
    )

    result = run_case(folder, engine)

    assert result.passed
    assert engine.plan_calls == 1


def test_a_failing_case(tmp_path: Path):
    folder = _case(tmp_path, MOCKS | {"expected.csv": "member_id,member_name\n2,Bea\n"})

    result = run_case(folder, _engine())

    assert not result.passed
    assert result.comparison is not None
    assert result.comparison.missing == [{"member_id": 2, "member_name": "Bea"}]
    assert "missing" in result.report()


def test_a_case_without_the_rows_it_needs_fails_naming_them(tmp_path: Path):
    folder = _case(
        tmp_path,
        {"members.csv": MOCKS["members.csv"], "expected.csv": "member_id\n1\n"},
    )

    result = run_case(folder, _engine())

    assert not result.passed
    assert "lob" in result.report()


def test_a_cell_that_cannot_be_cast_fails_the_case(tmp_path: Path):
    folder = _case(tmp_path, MOCKS | {"expected.csv": "member_id\none\n"})

    result = run_case(folder, _engine())

    assert not result.passed
    assert "expected.csv line 2 member_id" in result.report()


def test_a_mock_the_run_never_reads_fails_the_case_naming_it(tmp_path: Path):
    folder = _case(
        tmp_path,
        MOCKS
        | {
            "unrelated.csv": "id\n1\n",
            "expected.csv": "member_id,member_name\n1,Ada\n",
        },
    )

    result = run_case(folder, _engine())

    assert not result.passed
    assert result.problem == "mocks the run never reads: unrelated"


def test_a_missing_sql_ref_names_the_missing_file_not_unused_mocks(tmp_path: Path):
    folder = _case(tmp_path, MOCKS | {"expected.csv": "member_id,member_name\n1,Ada\n"})
    mapping = tmp_path / "mapping.csv"
    mapping.write_text("table_ref,sql_ref\nmedicaid_members,MISSING.sql\n")
    engine = Engine(
        catalog=mapped_sql_folder(
            sqls=REPOSITORY / "admin" / "sqls",
            mapping=mapping,
        ),
        executor=DuckDBExecutor(),
    )

    result = run_case(folder, engine)

    assert not result.passed
    assert "MISSING.sql" in (result.problem or "")
    assert "mocks the run never reads" not in (result.problem or "")


def test_a_missing_target_schema_names_the_relation_not_unused_mocks(tmp_path: Path):
    folder = _case(tmp_path, MOCKS | {"expected.csv": "member_id,member_name\n1,Ada\n"})
    schemas = tmp_path / "schemas"
    schemas.mkdir()
    (schemas / "sources.sql").write_text(
        "create table members (member_id integer, member_name varchar, lob integer);\n"
        "create table lob (lob integer, lob_name varchar);\n"
    )
    engine = Engine(
        catalog=mapped_sql_folder(
            sqls=REPOSITORY / "admin" / "sqls",
            mapping=REPOSITORY / "admin" / "config" / "lookup_sql_table_mapping.csv",
            schemas=schemas,
        ),
        executor=DuckDBExecutor(),
    )

    result = run_case(folder, engine)

    assert not result.passed
    assert "medicaid_members" in (result.problem or "")
    assert "schema" in (result.problem or "")
    assert "mocks the run never reads" not in (result.problem or "")


def test_a_typo_sqls_path_names_the_missing_sql_file_not_unused_mocks(tmp_path: Path):
    folder = _case(tmp_path, MOCKS | {"expected.csv": "member_id,member_name\n1,Ada\n"})
    sqls = tmp_path / "typo_sqls"
    sqls.mkdir()
    engine = Engine(
        catalog=mapped_sql_folder(
            sqls=sqls,
            mapping=REPOSITORY / "admin" / "config" / "lookup_sql_table_mapping.csv",
            schemas=REPOSITORY / "admin" / "sqls",
        ),
        executor=DuckDBExecutor(),
    )

    result = run_case(folder, engine)

    assert not result.passed
    assert "medicaid_members.sql" in (result.problem or "")
    assert "mocks the run never reads" not in (result.problem or "")
