# sql-test

Library and local tools for testing SQL transformations: mock upstream tables, run the real SQL, compare the output.

Design and vocabulary live in [docs/HELPER.md](docs/HELPER.md). Planned work is in [docs/ROADMAP.md](docs/ROADMAP.md).

## Setup

```bash
uv sync
```

Requires Python 3.14+.

## CLI

```bash
sql-test discover [repository]
sql-test app [repository] [--port 8765]
```

`discover` lists models, sources, and case folders. `app` starts a localhost-only authoring UI against a repository (default `.`).

Example against the sample repo kept in this tree:

```bash
uv run sql-test app lakehouse-data-customer
```

Or the deeper lineage fixture:

```bash
uv run sql-test app tests/fixtures/repos/lineage-demo
```

Open http://127.0.0.1:8765/

## Authoring app (so far)

- Browse models, sources, and cases
- Open a target in the workbench
- Lineage graph with mock / will-execute / source states (pruned nodes hidden)
- Click a node to mock or unmock; mocks keep a frontier
- Schema-aware mock grids (add/delete rows; Apply loads types through the engine)

Still to come: run and compare, save/load cases, coverage in the UI. Details in HELPER and the ROADMAP.

## Sample repository

`lakehouse-data-customer/` is a temporary sample consuming repository. The tool must not assume it is present; package tests use copies under `tests/fixtures/repos/`.

Its early v0-style tests still load DuckDB by hand in places. Case folders and the shared engine are replacing that path.

## Tests

```bash
uv run pytest
```

Fixture repositories under `tests/fixtures/` are skipped by the default pytest run. Run a fixture's own tests by path in a separate session.
