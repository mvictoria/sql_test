"""Scale shapes: chain, fan-out, funnel, and wide joins — not critical-path only."""

from pathlib import Path

import pytest

from sql_test.engine import Engine
from sql_test.engine.catalog.adapters import mapped_sql_folder
from sql_test.executors.duckdb import DuckDBExecutor
from sql_test.testing.run import run_case

SIZES = (10, 100, 1000)
# Real SQL rarely joins more than ~20 tables; 50 is a stretch ceiling.
JOIN_SIZES = (10, 20, 50)


def _engine(sqls: Path, mapping: Path) -> Engine:
    return Engine(
        catalog=mapped_sql_folder(sqls=sqls, mapping=mapping),
        executor=DuckDBExecutor(),
    )


def _write_mapping(path: Path, models: list[str]) -> None:
    path.write_text(
        "table_ref,sql_ref\n" + "".join(f"{name},{name}.sql\n" for name in models)
    )


def _case(
    root: Path,
    tip: str,
    name: str,
    mocks: dict[str, str],
    expected: str,
) -> Path:
    folder = root / "cases" / tip / name
    folder.mkdir(parents=True)
    for file_name, text in mocks.items():
        (folder / file_name).write_text(text)
    (folder / "expected.csv").write_text(expected)
    return folder


def _chain(root: Path, n: int) -> tuple[Path, Path, str]:
    """raw → t_1 → … → t_n."""
    sqls = root / "sqls"
    sqls.mkdir()
    models = [f"t_{i}" for i in range(1, n + 1)]
    tip = models[-1]

    (sqls / "ddl.sql").write_text(
        "create table raw (id int, name varchar);\n"
        + "".join(f"create table {m} (id int, name varchar);\n" for m in models)
    )
    (sqls / "t_1.sql").write_text("select id, name from raw")
    for i in range(2, n + 1):
        (sqls / f"t_{i}.sql").write_text(f"select id, name from t_{i - 1}")

    mapping = root / "mapping.csv"
    _write_mapping(mapping, models)
    return sqls, mapping, tip


def _fan_out(root: Path, n: int) -> tuple[Path, Path, str]:
    """raw → hub → branch_1 … branch_n; target is one leaf so siblings stay out of the plan."""
    sqls = root / "sqls"
    sqls.mkdir()
    branches = [f"branch_{i}" for i in range(1, n + 1)]
    tip = branches[-1]
    models = ["hub", *branches]

    (sqls / "ddl.sql").write_text(
        "create table raw (id int, name varchar);\n"
        "create table hub (id int, name varchar);\n"
        + "".join(f"create table {b} (id int, name varchar);\n" for b in branches)
    )
    (sqls / "hub.sql").write_text("select id, name from raw")
    for branch in branches:
        (sqls / f"{branch}.sql").write_text("select id, name from hub")

    mapping = root / "mapping.csv"
    _write_mapping(mapping, models)
    return sqls, mapping, tip


def _funnel(root: Path, n: int) -> tuple[Path, Path, str]:
    """src_1 … src_n (sources) → tip that joins them all on id."""
    sqls = root / "sqls"
    sqls.mkdir()
    sources = [f"src_{i}" for i in range(1, n + 1)]
    tip = "tip"

    (sqls / "ddl.sql").write_text(
        "".join(f"create table {s} (id int, name varchar);\n" for s in sources)
        + "create table tip (id int, name varchar);\n"
    )
    first, *rest = sources
    joins = "\n".join(f"inner join {s} on {first}.id = {s}.id" for s in rest)
    (sqls / "tip.sql").write_text(
        f"select {first}.id, {first}.name\nfrom {first}\n{joins}\n"
    )

    mapping = root / "mapping.csv"
    _write_mapping(mapping, [tip])
    return sqls, mapping, tip


def _bush(root: Path, n: int) -> tuple[Path, Path, str]:
    """raw → leaf_1 … leaf_n → tip joining every leaf (fan-out then funnel)."""
    sqls = root / "sqls"
    sqls.mkdir()
    leaves = [f"leaf_{i}" for i in range(1, n + 1)]
    tip = "tip"
    models = [*leaves, tip]

    (sqls / "ddl.sql").write_text(
        "create table raw (id int, name varchar);\n"
        + "".join(f"create table {leaf} (id int, name varchar);\n" for leaf in leaves)
        + "create table tip (id int, name varchar);\n"
    )
    for leaf in leaves:
        (sqls / f"{leaf}.sql").write_text("select id, name from raw")
    first, *rest = leaves
    joins = "\n".join(f"inner join {leaf} on {first}.id = {leaf}.id" for leaf in rest)
    (sqls / "tip.sql").write_text(
        f"select {first}.id, {first}.name\nfrom {first}\n{joins}\n"
    )

    mapping = root / "mapping.csv"
    _write_mapping(mapping, models)
    return sqls, mapping, tip


@pytest.mark.parametrize("n", SIZES, ids=lambda n: f"{n}_tables")
def test_chain_runs_end_to_end(tmp_path: Path, n: int):
    sqls, mapping, tip = _chain(tmp_path, n)
    engine = _engine(sqls, mapping)
    folder = _case(
        tmp_path,
        tip,
        "through_chain",
        mocks={"raw.csv": "id,name\n1,Ada\n"},
        expected="id,name\n1,Ada\n",
    )

    plan = engine.plan(tip, {"raw": [{"id": 1, "name": "Ada"}]})
    assert len(plan.operations) == n

    result = run_case(folder, engine)
    assert result.passed, result.report()
    assert result.actual == [{"id": 1, "name": "Ada"}]


@pytest.mark.parametrize("n", SIZES, ids=lambda n: f"{n}_branches")
def test_fan_out_plan_only_walks_the_target_branch(tmp_path: Path, n: int):
    sqls, mapping, tip = _fan_out(tmp_path, n)
    engine = _engine(sqls, mapping)
    folder = _case(
        tmp_path,
        tip,
        "one_branch",
        mocks={"raw.csv": "id,name\n1,Ada\n"},
        expected="id,name\n1,Ada\n",
    )

    plan = engine.plan(tip, {"raw": [{"id": 1, "name": "Ada"}]})
    # hub + the one targeted branch; siblings are not in this tip's lineage
    assert [op.sql_file.name for op in plan.operations] == ["hub.sql", f"{tip}.sql"]

    result = run_case(folder, engine)
    assert result.passed, result.report()
    assert result.actual == [{"id": 1, "name": "Ada"}]


@pytest.mark.parametrize("n", JOIN_SIZES, ids=lambda n: f"{n}_sources")
def test_funnel_joins_n_sources_in_one_sql(tmp_path: Path, n: int):
    sqls, mapping, tip = _funnel(tmp_path, n)
    engine = _engine(sqls, mapping)
    mocks = {f"src_{i}.csv": "id,name\n1,Ada\n" for i in range(1, n + 1)}
    folder = _case(
        tmp_path,
        tip,
        "all_sources",
        mocks=mocks,
        expected="id,name\n1,Ada\n",
    )

    plan = engine.plan(
        tip, {f"src_{i}": [{"id": 1, "name": "Ada"}] for i in range(1, n + 1)}
    )
    assert len(plan.operations) == 1
    assert plan.needs_rows == set()

    result = run_case(folder, engine)
    assert result.passed, result.report()
    assert result.actual == [{"id": 1, "name": "Ada"}]


@pytest.mark.parametrize("n", JOIN_SIZES, ids=lambda n: f"{n}_leaves")
def test_bush_fans_out_then_funnels_with_n_way_join(tmp_path: Path, n: int):
    sqls, mapping, tip = _bush(tmp_path, n)
    engine = _engine(sqls, mapping)
    folder = _case(
        tmp_path,
        tip,
        "through_bush",
        mocks={"raw.csv": "id,name\n1,Ada\n"},
        expected="id,name\n1,Ada\n",
    )

    plan = engine.plan(tip, {"raw": [{"id": 1, "name": "Ada"}]})
    assert len(plan.operations) == n + 1  # every leaf + tip

    result = run_case(folder, engine)
    assert result.passed, result.report()
    assert result.actual == [{"id": 1, "name": "Ada"}]
