# Roadmap

Product direction by version: what each release is *for*, not the work items to build it. Design decisions live in [HELPER.md](HELPER.md). Architecture in [foss-architecture-thoughts.md](foss-architecture-thoughts.md).

**Work items** (tasks, done-when, dependencies, status) live in [GitHub issues](https://github.com/mvictoria/sql_test/issues).

Nothing assumes where a repository lives. The engine is given SQL and a mapping; the test layer is given a repository. Adopt sample: `examples/minimal-consumer/`. Package tests use fixtures under `tests/fixtures/repos/`.

---

## Shipped

### Engine and case tests

Headless engine over DuckDB: discover models and schemas, lineage, plan a run with mocks, execute, compare expected vs actual. Case folders as durable CSV artifacts. A consuming repository runs those folders through its own pytest. Adoption failures name paths, mapping, DDL, and unsupported producers instead of opaque planner or CSV symptoms.

### Authoring app

Local NiceGUI workbench: pick a target, mock from lineage, edit grids, run, compare, accept actual, save/load/rename cases. Repository config and app flags editable in-app (session Apply vs durable Save). Catalog refreshes when SQL changes. Cases sit with their table; sources are not selectable as tables under test. Workbench splits setup and outcome; grids default collapsed; sheet-style cells; SQL peek from lineage without leaving the graph; calm read-only SQL view.

### Coverage and discovery CLI

`sql-test discover` and `sql-test coverage`; home page shows test counts and in-pipeline cases (with a short gloss).

### CI / CD for adopters

Reusable data-tests workflow, floating major tags (`@v0`), PR-title releases, Python 3.13–3.15. Tool CI on pull requests (skips Markdown-only changes).

### Adoption bootstrap

`sql-test init` scaffolds a consumer repository (deps, mapping, one case, pytest wiring, `@v0` workflow). Documented install pins the floating major tag. Copy-pasteable sample: `examples/minimal-consumer/`.

---

## Next product versions

### Spark execution

Run the same cases on Spark behind the existing executor interface. Measure fidelity and latency vs DuckDB; decide what the app and CI use by default.

### Incremental models

Recognize self-referencing / incremental SQL, store target-before state in cases, run and author those cases without inventing a second product.

### Richer lineage and coverage

Multi-producer drill-down, ordered sequential writes, structural coverage from plans, inspect intermediate results after a run.

---

## Later — not yet planned

- Switch repository in one app process (no second `sql-test app`); multi-repository lineage still later.
- Multiple `sqls` / `mapping` / `schemas` roots in one repository config (not multiple `cases` roots until a consumer asks).
- CDC / change-propagation views.
- Optional YAML/JSON config readers alongside `pyproject.toml`.
- Extra CLI commands (`run`, `validate`, static case checks) if a hook or other consumer needs them.
- Synthetic / Faker fill on mocks if design says hand entry and paste are not enough.
- Packaging the app/CLI separately from the test library (tabled).
