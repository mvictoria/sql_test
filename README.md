# sql-test

Library and local tools for testing SQL transformations: mock upstream tables, run the real SQL, compare the output.

Design and vocabulary live in [docs/HELPER.md](docs/HELPER.md). Product direction is in [docs/ROADMAP.md](docs/ROADMAP.md); work items are [GitHub issues](https://github.com/mvictoria/sql_test/issues).

## Setup (this repository)

```bash
uv sync
```

Requires Python 3.13+.

## Adopt in a consuming repository

Scaffold a new repo (config, stub SQL + mapping, one case, pytest wiring):

```bash
uvx --from "sql-test @ git+https://github.com/mvictoria/sql_test.git@v0" sql-test init my-data
cd my-data && uv sync && uv run pytest && uv run sql-test discover .
```

Or hand-build the same footprint:

```text
customer-data/
├── admin/sqls/                         # SQL + DDL (paths are yours to choose)
├── admin/config/lookup_sql_table_mapping.csv
├── tests/
│   ├── cases/<table>/<case>/           # mocks + expected.csv
│   ├── conftest.py                     # builds Engine from RepositoryConfig
│   └── test_case_folders.py            # parametrize case_folders(...)
├── pyproject.toml                      # [project] + [tool.uv] + [tool.sql-test]
└── .github/workflows/data-tests.yml    # calls the reusable workflow
```

**Install locally** from the floating major tag (same pin CI uses), if you are not using `init`:

```bash
uv add "sql-test @ git+https://github.com/mvictoria/sql_test.git@v0"
```

Use `@main` only as a bleeding-edge fallback while developing against unreleased commits.

**Configure** paths in `pyproject.toml` (all four required, relative to the repository root):

```toml
[tool.sql-test]
sqls = "admin/sqls"                                 # SQL files the mapping points at
mapping = "admin/config/lookup_sql_table_mapping.csv"  # SQL file -> table it writes
schemas = "admin/sqls"                              # CREATE TABLE DDL
cases = "tests/cases"                               # case folders
```

**Run cases** with a parametrized pytest test (see `lakehouse-data-customer/tests/` for a full example):

```python
@pytest.mark.parametrize("case", case_folders(CASES), ids=case_id)
def test_case(case, engine):
    result = run_case(case, engine)
    assert result.passed, result.report()
```

**CI** — pin the reusable workflow to the floating major tag, never `main`:

```yaml
jobs:
  data-tests:
    uses: mvictoria/sql_test/.github/workflows/data-tests.yml@v0
```

Copy [lakehouse-data-customer/.github/workflows/data-tests.yml](lakehouse-data-customer/.github/workflows/data-tests.yml). The workflow installs `sql-test` from the same git commit as that pin and runs pytest in the calling repository.

**Releases** — the git tag is the version (`dynamic` via hatchling / `uv-dynamic-versioning`).

1. Start the **PR title** with `(major)`, `(minor)`, or `(patch)` as the first word when that PR should release (case-insensitive; example: `(patch) CI-2: versioned releases`). Later mentions are ignored. Skip the token if it should not release.
2. Merge with linear history (rebase). CD runs on `main`, finds the merged PR, and tags **`main`'s new tip** — not the old branch commits.
3. CD tags **`main`'s tip**, builds the wheel/sdist, creates/updates the GitHub Release, and moves floating `vX` (for example `v0`) in that same run — a bot tag push alone does not start a second workflow.

Manual tag push (`git tag vX.Y.Z && git push origin vX.Y.Z`) still runs the release job.

## CLI

pytest remains the test runner. The CLI also discovers tables/cases, prints coverage, and starts the authoring app.

```bash
sql-test init [directory]
sql-test discover [repository]
sql-test coverage [repository]
sql-test app [repository] [--port 8765]
```

- `init` — write a minimal consuming-repository skeleton; adds `[tool.sql-test]` to an existing `pyproject.toml`, refuses if that table is already present
- `repository` / `directory` — path (default `.`)
- `--port` — localhost port for `app` (default `8765`)

`coverage` prints tests and in-pipeline counts per table, untested first (same `coverage_report` the app home uses):

```bash
uv run sql-test coverage tests/fixtures/repos/lakehouse-data-customer
```

```text
table   tests   in pipelines
lob     0       0
members 0       0
medicaid_members        1       1
medicaid_members_named_alice    2       0
```

The app server binds to localhost only. Open the printed URL in a browser.

```bash
uv run sql-test app lakehouse-data-customer
uv run sql-test app tests/fixtures/repos/lineage-demo --port 9000
```

## Authoring app (so far)

Built with [NiceGUI](https://nicegui.io); its tests use NiceGUI's `User` fixture (`tests/test_app.py`).

- Browse models, sources, and cases (tests and in-pipeline counts; untested first)
- Open a target or an existing case in the workbench
- Lineage graph with mock / will-execute / source states (pruned nodes hidden)
- Click a node to mock or unmock; mocks keep a frontier
- Schema-aware mock grids (add/delete rows, Tab between cells, paste from a spreadsheet)
- Run types the mocks and shows output with row counts; expected and actual side by side
- Accept actual as expected: a whole result, one row, or one cell, including "expect no rows"
- Load and save case mocks and expected rows
- Picks up SQL files added, edited, or deleted while the app is open

Details in HELPER and the product ROADMAP.

## Sample repository

`lakehouse-data-customer/` is a temporary sample consuming repository. The tool must not assume it is present; package tests use copies under `tests/fixtures/repos/`.

Its `tests/` show both ways a repository uses the library: `test_sql.py` calls the engine with rows written in Python, and `test_case_folders.py` runs one parametrized test per case folder under `tests/cases/`. Run them with `uv run pytest lakehouse-data-customer/tests`.

## Tests

```bash
uv run pytest
```

Fixture repositories under `tests/fixtures/` are skipped by the default pytest run. Run a fixture's own tests by path in a separate session.
