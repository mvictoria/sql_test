"""TEST-1: plan properties on small synthetic chains."""

import tempfile
from pathlib import Path

from hypothesis import given
from hypothesis import strategies as st

from sql_test.engine.catalog.adapters import mapped_sql_folder
from sql_test.engine.planner.plan import State, plan_run
from sql_test.engine.relation import Relation


def _chain_catalog(root: Path, length: int):
    """raw → t_1 → … → t_length."""
    sqls = root / "sqls"
    sqls.mkdir()
    models = [f"t_{i}" for i in range(1, length + 1)]
    (sqls / "ddl.sql").write_text(
        "create table raw (id int);\n"
        + "".join(f"create table {m} (id int);\n" for m in models)
    )
    (sqls / "t_1.sql").write_text("select id from raw")
    for i in range(2, length + 1):
        (sqls / f"t_{i}.sql").write_text(f"select id from t_{i - 1}")
    mapping = root / "mapping.csv"
    mapping.write_text(
        "table_ref,sql_ref\n" + "".join(f"{m},{m}.sql\n" for m in models)
    )
    return mapped_sql_folder(sqls=sqls, mapping=mapping), models


@given(
    st.integers(min_value=2, max_value=5),
    st.integers(min_value=0, max_value=5),
    st.integers(min_value=0, max_value=3),
)
def test_plan_invariants_on_a_chain(length: int, cut: int, rows: int):
    cut = min(cut, length)
    with tempfile.TemporaryDirectory() as tmp:
        catalog, models = _chain_catalog(Path(tmp), length)
        tip = Relation(name=models[-1])
        given_name = "raw" if cut == 0 else models[cut - 1]
        given_rel = Relation(name=given_name)
        given = {given_rel: rows}

        plan = plan_run(tip, catalog, given=given)

        assert plan.unused <= set(given)
        executed = {op.writes for op in plan.operations}
        assert executed == {
            rel for rel, state in plan.states.items() if state is State.EXECUTED
        }
        for rel, state in plan.states.items():
            if state is State.PRUNED:
                assert rel not in executed
        assert plan.needs_rows == {
            rel
            for rel, state in plan.states.items()
            if state is State.SOURCE or (state is State.GIVEN and given[rel] == 0)
        }
        if (
            rows > 0
            and given_rel in plan.states
            and plan.states[given_rel] is State.GIVEN
            and cut > 0
        ):
            assert plan.states[Relation(name="raw")] is State.PRUNED
            for i in range(1, cut):
                assert plan.states[Relation(name=models[i - 1])] is State.PRUNED
