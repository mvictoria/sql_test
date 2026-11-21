"""Engine-only scale: 1000 models × 100 cases each — no DuckDB.

Stresses catalog build, case_counts, and pipeline_counts (plan_run per case).
Cases are in-memory CaseSummaries so we do not write 100k folders.
"""

from __future__ import annotations

import time
from pathlib import Path

from sql_test.engine.catalog.adapters import mapped_sql_folder
from sql_test.testing.cases import CaseSummary
from sql_test.testing.coverage import case_counts, pipeline_counts

MODELS = 1000
CASES_PER_MODEL = 100


def _repo_of_independent_models(root: Path, n: int) -> tuple[Path, Path, list[str]]:
    """raw source → t_1 … t_n, each a one-hop full load (minimal lineage)."""
    sqls = root / "sqls"
    sqls.mkdir()
    models = [f"t_{i}" for i in range(1, n + 1)]
    (sqls / "ddl.sql").write_text(
        "create table raw (id int);\n"
        + "".join(f"create table {m} (id int);\n" for m in models)
    )
    for name in models:
        (sqls / f"{name}.sql").write_text("select id from raw")
    mapping = root / "mapping.csv"
    mapping.write_text(
        "table_ref,sql_ref\n" + "".join(f"{m},{m}.sql\n" for m in models)
    )
    return sqls, mapping, models


def _cases_for_models(models: list[str], per_model: int) -> list[CaseSummary]:
    return [
        CaseSummary(
            target=name,
            name=f"case_{j}",
            mocks=("raw",),
            has_expected=True,
        )
        for name in models
        for j in range(per_model)
    ]


def test_engine_handles_1000_models_with_100_cases_each(tmp_path: Path):
    t0 = time.perf_counter()
    sqls, mapping, models = _repo_of_independent_models(tmp_path, MODELS)
    t_files = time.perf_counter() - t0

    t0 = time.perf_counter()
    catalog = mapped_sql_folder(sqls=sqls, mapping=mapping)
    t_catalog = time.perf_counter() - t0
    assert len(catalog.operations) == MODELS

    t0 = time.perf_counter()
    cases = _cases_for_models(models, CASES_PER_MODEL)
    t_cases = time.perf_counter() - t0
    assert len(cases) == MODELS * CASES_PER_MODEL

    tables = ("raw", *models)

    t0 = time.perf_counter()
    tests = case_counts(tables, cases)
    t_counts = time.perf_counter() - t0
    assert tests["raw"] == 0
    assert tests["t_1"] == CASES_PER_MODEL
    assert tests["t_1000"] == CASES_PER_MODEL
    assert sum(tests.values()) == MODELS * CASES_PER_MODEL

    t0 = time.perf_counter()
    pipelines = pipeline_counts(tables, cases, catalog)
    t_pipelines = time.perf_counter() - t0
    # Independent models: each plan is target + mocked raw; pipeline_counts
    # skips the target, so every model stays at zero in-pipeline.
    assert pipelines["raw"] == 0
    assert all(pipelines[name] == 0 for name in models)

    total = t_files + t_catalog + t_cases + t_counts + t_pipelines
    # Measured ~7.5s locally; budget leaves headroom for CI noise.
    assert t_catalog < 5.0, f"catalog build too slow: {t_catalog:.2f}s"
    assert t_pipelines < 30.0, f"pipeline_counts too slow: {t_pipelines:.2f}s"
    assert total < 60.0, f"engine 1000×100 too slow: {total:.2f}s"

    print(
        f"\n1000×100 engine perf: "
        f"files={t_files:.2f}s catalog={t_catalog:.2f}s "
        f"cases={t_cases:.2f}s case_counts={t_counts:.2f}s "
        f"pipeline_counts={t_pipelines:.2f}s total={total:.2f}s"
    )
