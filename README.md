# sql-test

Library and local tools for testing SQL transformations: mock upstream tables, run the real SQL, compare the output.

## Setup

Requires Python 3.13+. Prefer `sql-test init` for a new data repo. To hand-build, copy [examples/minimal-consumer/](examples/minimal-consumer/) or paste the files below — that example is a standalone consumer that installs `sql-test` itself.

Scaffold:

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

**`pyproject.toml`** — a consumer needs a full `[project]` table (and usually `[tool.uv] package = false`). Paths under `[tool.sql-test]` are required and relative to the repository root:

```toml
[project]
name = "minimal-consumer"
version = "0.0.0"
requires-python = ">=3.13"
dependencies = [
    "sql-test @ git+https://github.com/mvictoria/sql_test.git@v0",
    "pytest>=9",
]

[tool.uv]
package = false

[tool.sql-test]
sqls = "admin/sqls"                                 # SQL files the mapping points at
mapping = "admin/config/lookup_sql_table_mapping.csv"  # SQL file -> table it writes
schemas = "admin/sqls"                              # CREATE TABLE DDL
cases = "tests/cases"                               # case folders
```

**Install** from the floating major tag (same pin CI uses), if you are not using `init`:

```bash
uv add "sql-test @ git+https://github.com/mvictoria/sql_test.git@v0"
```

Use `@main` only as a bleeding-edge fallback while developing against unreleased commits — do not pin consumer CI to `main`.

**Mapping CSV** — header row must include `table_ref,sql_ref` (table the SQL writes, then the SQL file under `sqls`). Optional `load_type`: `merge` marks an incremental merge model; other values (and a missing column) are full load:

```csv
table_ref,sql_ref
example,example.sql
```

**Run cases** with a parametrized pytest test (full wiring in [examples/minimal-consumer/tests/](examples/minimal-consumer/tests/)):

```python
@pytest.mark.parametrize("case", case_folders(CASES), ids=case_id)
def test_case(case, engine):
    result = run_case(case, engine)
    assert result.passed, result.report()
```

**CI** — `sql-test init` writes `.github/workflows/data-tests.yml` pinned to the floating major tag (`@v0`), never `main`. For a hand-built repo, copy [examples/minimal-consumer/.github/workflows/data-tests.yml](examples/minimal-consumer/.github/workflows/data-tests.yml) (same pin):

```yaml
jobs:
  data-tests:
    uses: mvictoria/sql_test/.github/workflows/data-tests.yml@v0
```

The workflow installs `sql-test` from the same git commit as that pin and runs pytest in the calling repository.

## Authoring app

Local workbench. Server binds to localhost only — open the printed URL in a browser:

```bash
uv run sql-test app examples/cdc-example
uv run sql-test app . --port 9000
```

- Browse models, sources, and cases (tests and in-pipeline counts; untested first)
- Open a target or an existing case in the workbench
- Lineage graph with mock / will-execute / source states (pruned nodes hidden)
- Click a node to mock or unmock; mocks keep a frontier
- Schema-aware mock grids (add/delete rows, Tab between cells, paste from a spreadsheet)
- Run types the mocks and shows output with row counts; expected and actual side by side
- Accept actual as expected: a whole result, one row, or one cell, including "expect no rows"
- Load and save case mocks and expected rows
- Picks up SQL files added, edited, or deleted while the app is open

## CLI

pytest remains the test runner. The CLI also discovers tables/cases, prints coverage, and starts the authoring app.

```bash
sql-test init [directory]
sql-test discover [repository]
sql-test coverage [repository]
sql-test app [repository] [--port 8765]
```

- `init` — write a minimal consuming-repository skeleton (SQL, mapping, one case, pytest wiring, and a `@v0` data-tests workflow); adds `[tool.sql-test]` to an existing `pyproject.toml`, refuses if that table is already present
- `repository` / `directory` — path (default `.`)
- `--port` — localhost port for `app` (default `8765`)

`coverage` prints tests and in-pipeline counts per table, untested first (same `coverage_report` the app home uses). **In pipelines** means cases that execute the table without targeting it (its SQL runs as part of another case's pipeline).

```bash
uv run sql-test coverage examples/cdc-example
```

```text
table   tests   in pipelines
lob     0       0
members 0       0
medicaid_members        1       1
medicaid_members_named_alice    2       0
```

## Sample repositories

- [`examples/minimal-consumer/`](examples/minimal-consumer/) — smallest adopt sample (one model, one case, workflow caller).
- [`examples/cdc-example/`](examples/cdc-example/) — chained models, CDC merge case (`seen`), both `test_sql.py` and case folders.

```bash
uv run pytest examples/cdc-example/tests
```

Developing this package: [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md). Design and vocabulary live in [docs/HELPER.md](docs/HELPER.md). Product direction is in [docs/ROADMAP.md](docs/ROADMAP.md); work items are [GitHub issues](https://github.com/mvictoria/sql_test/issues).
