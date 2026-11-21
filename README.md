# sql-test

Library and local tools for testing SQL transformations: mock upstream tables, run the real SQL, compare the output.

Design and vocabulary live in [docs/HELPER.md](docs/HELPER.md). Planned work is in [docs/ROADMAP.md](docs/ROADMAP.md).

## Setup

```bash
uv sync
```

Requires Python 3.14+.

## Configure a repository

A consuming repository says where its files live in a `[tool.sql-test]` table in its `pyproject.toml`. Paths are relative to the repository root, and all four are required:

```toml
[tool.sql-test]
sqls = "admin/sqls"                                 # SQL files the mapping points at
mapping = "admin/config/lookup_sql_table_mapping.csv"  # SQL file -> table it writes
schemas = "admin/sqls"                              # CREATE TABLE DDL
cases = "tests/cases"                               # case folders
```

## CLI

The CLI starts the authoring app. pytest remains the test runner.

```bash
sql-test app [repository] [--port 8765]
```

- `repository` — path to the consuming repository (default `.`)
- `--port` — localhost port (default `8765`)

The server binds to localhost only. Open the printed URL in a browser.

```bash
uv run sql-test app lakehouse-data-customer
uv run sql-test app tests/fixtures/repos/lineage-demo --port 9000
```

## Authoring app (so far)

- Browse models, sources, and cases
- Open a target or an existing case in the workbench
- Lineage graph with mock / will-execute / source states (pruned nodes hidden)
- Click a node to mock or unmock; mocks keep a frontier
- Schema-aware mock grids (add/delete rows; Apply loads types through the engine)
- Run and show output with row counts; expected and actual side by side
- Load an existing case's mocks and rows into the workbench

Still to come: accept actual as expected, save cases, coverage in the UI. Details in HELPER and the ROADMAP.

## Sample repository

`lakehouse-data-customer/` is a temporary sample consuming repository. The tool must not assume it is present; package tests use copies under `tests/fixtures/repos/`.

Its `tests/` show both ways a repository uses the library: `test_sql.py` calls the engine with rows written in Python, and `test_case_folders.py` runs one parametrized test per case folder under `tests/cases/`. Run them with `uv run pytest lakehouse-data-customer/tests`.

## Tests

```bash
uv run pytest
```

Fixture repositories under `tests/fixtures/` are skipped by the default pytest run. Run a fixture's own tests by path in a separate session.
