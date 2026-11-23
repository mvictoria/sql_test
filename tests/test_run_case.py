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
    """Counts plan/execute calls so run_case cannot hide a second plan or phase."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.plan_calls = 0
        self.execute_calls = 0

    def plan(
        self, table: str, rows: dict[str, list[Row]], *, with_pruned: bool = False
    ) -> Plan:
        self.plan_calls += 1
        return super().plan(table, rows, with_pruned=with_pruned)

    def execute(self, plan: Plan, rows: dict[str, list[Row]]):
        self.execute_calls += 1
        return super().execute(plan, rows)


def _case(root: Path, files: dict[str, str]) -> Path:
    folder = root / "cases" / "medicaid_members" / "ada"
    folder.mkdir(parents=True)
    for name, text in files.items():
        (folder / name).write_text(text)
    return folder


def _cdc_case(
    root: Path,
    *,
    history: dict[str, str],
    deltas: dict[str, str],
    expected: str,
) -> Path:
    folder = root / "cases" / "seen" / "batch"
    folder.mkdir(parents=True)
    for name, text in history.items():
        (folder / name).write_text(text)
    delta_folder = folder / "delta"
    delta_folder.mkdir()
    for name, text in deltas.items():
        (delta_folder / name).write_text(text)
    (folder / "expected.csv").write_text(expected)
    return folder


CDC_HISTORY = {"events.csv": "id,source\n1,seed\n"}
CDC_DELTAS = {"events.csv": "id,source\n2,batch\n3,batch\n"}
CDC_EXPECTED = "id,source\n1,seed\n2,batch\n3,batch\n"


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


def test_unknown_mock_columns_fail_naming_the_relation(tmp_path: Path):
    folder = _case(
        tmp_path,
        {
            "members.csv": "member_idd,member_name,lob\n1,Ada,30\n",
            "lob.csv": MOCKS["lob.csv"],
            "expected.csv": "member_id,member_name\n1,Ada\n",
        },
    )

    result = run_case(folder, _engine())

    assert not result.passed
    assert result.comparison is None
    assert result.problem == "unknown columns on members: member_idd"
    assert "missing" not in result.report()


def test_unknown_expected_columns_fail_naming_the_relation(tmp_path: Path):
    folder = _case(
        tmp_path,
        MOCKS | {"expected.csv": "member_idd,member_name\n1,Ada\n"},
    )

    result = run_case(folder, _engine())

    assert not result.passed
    assert result.comparison is None
    assert result.problem == "unknown columns on medicaid_members: member_idd"
    assert "missing" not in result.report()


def test_a_passing_cdc_case(tmp_path: Path):
    folder = _cdc_case(
        tmp_path, history=CDC_HISTORY, deltas=CDC_DELTAS, expected=CDC_EXPECTED
    )

    result = run_case(folder, _engine())

    assert result.passed
    assert sorted(result.actual, key=lambda row: row["id"]) == [
        {"id": 1, "source": "seed"},
        {"id": 2, "source": "batch"},
        {"id": 3, "source": "batch"},
    ]


def test_a_failing_cdc_case(tmp_path: Path):
    """Wrong expected fails the CDC case with a comparison, not a problem."""
    folder = _cdc_case(
        tmp_path,
        history=CDC_HISTORY,
        deltas=CDC_DELTAS,
        expected="id,source\n1,seed\n2,batch\n",
    )

    result = run_case(folder, _engine())

    assert not result.passed
    assert result.problem is None
    assert result.comparison is not None
    assert result.comparison.unexpected == [{"id": 3, "source": "batch"}]
    assert "unexpected" in result.report()


def test_a_cdc_case_runs_historic_then_merge(tmp_path: Path):
    """Two-phase CDC: one plan, historic execute then merge execute."""
    folder = _cdc_case(
        tmp_path, history=CDC_HISTORY, deltas=CDC_DELTAS, expected=CDC_EXPECTED
    )
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
    assert engine.execute_calls == 2
