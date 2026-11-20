# AGENTS.md

A library for testing SQL transformations: mock upstream tables, run the real SQL, compare the output. Tests are case folders of CSVs that pytest runs through one shared engine.

## Docs

- **Design decisions** (case format, lineage, mocking, coverage, architecture): [docs/HELPER.md](docs/HELPER.md). Read it before changing engine behaviour or the case format.
- **Work items**: [docs/ROADMAP.md](docs/ROADMAP.md). Each story has an ID such as `ENG-2`, a done-when, and its dependencies. Find the story before starting work, and update the roadmap when scope changes.

## Way of working

- **TDD.** Each story starts with a failing test for its done-when. Write the code that makes it pass, then refactor, one behaviour per red/green cycle.
- **DDD.** Code uses the domain's words: table under test, case, mock, source, boundary, producer, lineage, plan. Name modules, types, and functions after them. A new term is defined in [docs/HELPER.md](docs/HELPER.md) before it appears in code.
- **Ship on a PR.** Push the branch and open (or update) a pull request; do not leave finished work only local. The PR body is for humans: succinct — what changed, why, and which roadmap story it serves.

## Conventions

- One story per commit, message prefixed with its ID: `ENG-1: package skeleton`.
- Layers import in one direction, as laid out in [docs/HELPER.md](docs/HELPER.md): `engine` (catalog, lineage, planner) imports no other layer; `executors` import only the engine's executor interface; `testing` imports the engine; `integrations` wire them together. `tests/test_layers.py` enforces this.
- The engine is handed an executor and never imports one. Executors know SQL and rows, not lineage or case folders.
- SQL-engine-specific behaviour stays inside an executor. DuckDB is the tentative executor; Spark replaces it later behind the same interface.
- The engine is always given a repository path. `lakehouse-data-customer/` is a temporary sample consuming repository; the tool's own tests use the copies under `tests/fixtures/repos/`.

## Gotchas

- Fixture repositories are data. pytest skips `tests/fixtures/`; run a fixture's own tests by path in a separate pytest run, because two `test_sql.py` files collide in one session.
- `prek run` fixes files and can still print `Passed`. Check `git status` after running it.
- Fixtures with deliberately unparseable SQL need excluding from the sqlfluff hook in `prek.toml`.
