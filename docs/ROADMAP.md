# Roadmap

Product direction by version: what each release is *for*, not the work items to build it. Design decisions live in [HELPER.md](HELPER.md). Architecture in [foss-architecture-thoughts.md](foss-architecture-thoughts.md).

**Work items** (tasks, done-when, dependencies, status) live in [GitHub issues](https://github.com/mvictoria/sql_test/issues).

Nothing assumes where a repository lives. The engine is given SQL and a mapping; the test layer is given a repository. `lakehouse-data-customer/` is a sample consuming repository; the tool's own tests use fixtures under `tests/fixtures/repos/`.

---

## Shipped

### Engine and case tests

Headless engine over DuckDB: discover models and schemas, lineage, plan a run with mocks, execute, compare expected vs actual. Case folders as durable CSV artifacts. A consuming repository runs those folders through its own pytest.

### Authoring app

Local NiceGUI workbench: pick a target, mock from lineage, edit grids, run, compare, accept actual, save/load cases. Repository config editable in-app. Catalog refreshes when SQL changes.

### Coverage and discovery CLI

`sql-test discover` and `sql-test coverage`; home page shows test counts and in-pipeline cases.

### CI / CD for adopters

Reusable data-tests workflow, floating major tags (`@v0`), PR-title releases, Python 3.13–3.15. Tool CI on pull requests (skips Markdown-only changes).

### Adoption bootstrap

`sql-test init` scaffolds a consumer repository. Documented install pins the floating major tag.

---

## Before the next release

Themes from [UAT.md](UAT.md) — make a stranger's first green case easy — plus finishing workbench clarity. Prefer these over Spark, incremental, or richer lineage until after that release.

- **Consumer packaging and docs** — copy-pasteable `pyproject`, mapping CSV documented in the adopt path, standalone sample story.
- **Clearer failures** — path / DDL / mapping / INSERT diagnoses instead of opaque planner or CSV symptoms.
- **First-run authoring polish** — blank workbench guidance, generic compliance copy, port-in-use honesty, accept-actual in the UI where it still feels incomplete.
- **Workbench navigation** — cases belong to their table; denser grid; SQL peek from lineage without leaving the graph.

Open issues for these themes: [is:open](https://github.com/mvictoria/sql_test/issues?q=is%3Aissue+is%3Aopen).

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

- Multi-repository workspaces and cross-repo lineage.
- CDC / change-propagation views.
- Optional YAML/JSON config readers alongside `pyproject.toml`.
- Extra CLI commands (`run`, `validate`, static case checks) if a hook or other consumer needs them.
- Synthetic / Faker fill on mocks if UAT and design say hand entry and paste are not enough.
