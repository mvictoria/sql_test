# Lineage-Aware SQL Test Authoring Tool

## Overview

We are proposing a lightweight local web application that helps QA engineers create and maintain data-product tests without requiring them to manually understand or author the underlying pytest implementation.

The tool sits on top of existing data-product repositories. SQL, schemas, and tests remain owned by those repositories, and pytest remains the canonical test runner.

The tool's primary purpose is **test authoring and exploration**:

1. Select a table under test.
2. Discover and visualize its upstream lineage.
3. Select upstream tables to mock.
4. Enter mock data.
5. Execute the real SQL between the mocked boundaries and the table under test.
6. Compare actual output with expected output.
7. Edit/accept expected results.
8. Save the resulting test case into the repository.

Saved tests are ordinary durable repository artifacts. They can be discovered and edited by the tool, but they do not depend on the tool to execute. CI runs them independently through the existing pytest framework.

The initial implementation will support a single repository. Multi-repository lineage and execution are a planned extension.

---

# Design Principles

## The repository is the source of truth

SQL, schemas, lineage inputs, and test definitions live in Git. The application should derive information from the checked-out repository rather than maintaining a parallel representation.

## One shared engine and test layer own test execution semantics

The UI is not a separate testing framework. One shared engine and the test layer over it own test semantics, and pytest remains the canonical runner (see Architecture).

The same engine and test layer are used by:

- pytest locally
- CI
- the authoring application

A test created through the UI must behave identically when subsequently executed by pytest without the application.

## Tests remain intentionally simple

The primary test definition should consist of:

- table under test
- mocked tables and their data
- existing target data when required for incremental models
- expected target data

Everything that can reliably be derived from the repository should be derived rather than duplicated in the test definition.

## QA works primarily with tables

QA should not normally need to reason about SQL files, execution plans, or pytest fixtures.

The default lineage representation is therefore table-centric.

The execution engine may maintain a more detailed SQL-aware graph internally.

## Progressive disclosure

Implementation details such as multiple SQL producers for a table should not make the default lineage graph difficult to understand.

Tables with additional complexity can expose SQL/producer information through drill-down.

## Git workflow remains outside the application

The tool may write or modify test artifacts in the current working tree, but engineers continue to own branching, committing, pushing, PR creation, merging, and other Git lifecycle activities.

---

# Core Test Model

For a full-load model:

```text
Test Case
├── table under test
├── mocked tables
│   ├── table A → rows
│   └── table B → rows
└── expected target → rows
```

For an incremental model:

```text
Test Case
├── table under test
├── target before → rows
├── mocked tables
│   ├── table A → rows
│   └── table B → rows
└── expected target after → rows
```

Incremental self-reference should conceptually be represented as:

```text
target(before) ──┐
                 ├── incremental SQL ──→ target(after)
mock inputs ─────┘
```

rather than exposing the self-reference as a cycle to QA.

## Saved format

A test case is a folder of CSVs:

```text
cases/
└── <table under test>/
    └── <case name>/
        ├── <mocked table>.csv    one per mocked table
        └── expected.csv
```

Schemas are not stored in the case. Column types come from the schemas discovered in the repository, and CSV values are read with those types.

### Case format, version 1

The case format is a public contract: people and other tools write cases by hand. A change to it gets a new version here.

A **case table** is the columns and typed rows of one CSV in a case — a mock file or `expected.csv`.

- The folder names are the table under test and the case name. A mocked table's file is its relation name as written in the SQL, for example `members.csv` or `claims.members.csv`.
- Each CSV is UTF-8, comma-separated, with a header row of column names and `\n` line endings.
- Cells follow the [comparison defaults](#comparison-defaults): an empty, unquoted cell is NULL and `""` is an empty string. A cell is quoted only when it is empty or contains a comma, quote, or line break.
- Each cell is read as its column's type from the discovered schema. A cell that cannot be read as that type is reported with its file, line, and column. Columns of a relation with no schema stay text.
- Integers and decimals are written as digits, booleans as `true` or `false`, dates and timestamps in ISO 8601.
- A mock file may list only some of its relation's columns; unlisted columns are NULL. `expected.csv` lists only the columns the case checks, and may be absent while a case is being written.

A repository's own pytest test runs its case folders, one parametrized test per case, so a saved case needs no new Python. The repository passes the folder that holds its cases; the library assumes no location.

How target-before state is stored for incremental models is decided with incremental support.

---

# Lineage Model

For the initial single-repository implementation, lineage discovery can follow a simple rule:

```text
Referenced table
      │
      ├── Produced by SQL in this repo?
      │       │
      │       ├── Yes → SQL parses and table has a schema?
      │       │           │
      │       │           ├── Yes → model; continue upstream
      │       │           │
      │       │           └── No  → source; stop
      │       │
      │       └── No → source; stop
      │
      └── Mocked?
              │
              └── Yes → execution boundary; stop upstream traversal
```

QA reasons in **source → target** terms. A **source** is any relation the case must supply rows for because lineage cannot execute through it: it is not produced in this repository, or it is produced but its SQL cannot be parsed or it has no schema. Drill-down shows which. Sources remain mockable.

Lineage goes as far back as the SQL can be parsed. A parse failure or missing schema stops traversal and classifies that relation as a source; it shortens lineage rather than blocking the test.

**Boundary** is not a relation type. An **execution boundary** is where upstream traversal stops — usually because a table is mocked. Keep that phrase for the stop, not for the table.

## Mocking and pruning

Mocking a table establishes an execution boundary.

Given:

```text
raw_claims → staged_claims → member_claims → customer_summary
```

mocking `staged_claims` produces:

```text
raw_claims
   PRUNED

[staged_claims]
    MOCKED
      ↓
member_claims
      ↓
customer_summary
```

Everything upstream of a mocked relation that is no longer required by another executable path is pruned.

Mocks form a **frontier**: if `a → b → c`, you cannot mock both `a` and `b`. Mocking `b` prunes `a`. Unmocking `b` brings `a` back.

The UI shows the live frontier only:

- **Mocked** — supplied by the test
- **Will execute** — real repository SQL will run for this relation (the plan's future). While a run is in progress this becomes *executing*, then *executed*.
- **Source** — must be supplied by the test (not produced here, or produced but unusable for lineage); drill-down shows why

**Pruned** relations are hidden. They reappear when the mock that pruned them is removed.

Every table that will be read but is not produced by executed SQL needs test data (`needs_rows`). Those tables are shown grey until data is added, and colored once they have data. **A case is ready to run only when `needs_rows` is empty** — every leaf that still needs rows is covered. Running otherwise fails naming them. A case with an unused mock also fails, naming it: the run would ignore its rows, and a reader of the case folder would think they matter.

---

# SQL-Aware Lineage

## Relations

A **relation** is a table or view, identified by an optional catalog, an optional schema, and a name, for example `lakehouse.claims.members`. Repositories may use one-, two-, or three-level names. A relation is kept as qualified as it was written; `claims.members` and `billing.members` are different relations.

sqlglot parses names and normalizes their case for the configured dialect. The engine keeps its own small relation type, so other layers do not depend on sqlglot's types.

A name written with fewer levels, such as a bare `members`, resolves to the one known relation whose trailing parts match. If several match, the name is ambiguous, and resolving it is an error that lists the candidates. If none match, the name stays as written, for example a source the repository does not produce.

## Catalog

The **catalog** is what the engine knows about a repository: its operations, its schemas, and every relation either of them mentions. The engine reads a catalog, never files. A **repository adapter** builds the catalog from one repository's conventions, choosing the readers for its mapping and schemas. The first adapter reads a folder of SQL plus a mapping CSV, with schemas from the DDL in that folder.

Each relation in the catalog records how it is known:

- **Declared** — written by an operation, or given a schema. Something in the repository says it exists.
- **Inferred** — only read by SQL. `select * from members` implies `members` exists, so it is in the graph, as a source.

A reference resolves to a declared relation when it matches one; otherwise it is inferred as written. Inferred relations keep lineage complete, including sources owned elsewhere, but a typo such as `memebrs` is also inferred. The tool does not validate that a repository's SQL reads real tables; that belongs to the repository's own linting. It should show inferred relations distinctly, so a typo is not mocked into a case by accident; nothing does yet. A relation is declared when `Catalog.producers` or `Catalog.schema` finds it, so the distinction needs no separate tag. Callers find relations through the catalog: `resolve(name)`, `schema(relation)`, and `producers(relation)`.

A catalog is a **snapshot**: frozen once built, it works out its relations once. A long-running caller, such as the app, sees SQL (and mapping) files that were added, modified, or deleted by building a **new** catalog and dropping the old one. [ENG-26](ROADMAP.md#eng-26) memoizes parse on each file's text so a rebuild re-parses only changed content; unchanged files hit the cache. Catalogs stay immutable — no in-place patch of operations or indexes. Whether that rebuild is cheap enough for interactive use is something to measure on a large repository before inventing incremental catalog updates. Lookups are indexed once per catalog: `resolve` compares a name only with relations of that name, and `producers` reads an index of operations by the relation they write.

## Schemas

A relation's **schema** is its ordered columns, each a name and a type. Repositories store schemas in different ways: SQL DDL, YAML, or JSON. Each format has a reader, and every reader returns the same thing: schemas keyed by relation, plus any problems found. Which reader a repository uses is one of its conventions. The DDL reader comes first; YAML and JSON readers are added when a repository needs them.

Types are parsed and normalized by sqlglot, so `integer` and `INT` are the same type whatever format they were written in. Schemas are read in the dialect they were written in, defaulting to sqlglot's generic dialect, never DuckDB's: sqlglot's DuckDB dialect drops `varchar` lengths, as DuckDB does.

The DDL reader reads every `CREATE TABLE` with a column list, in any file under the SQL folder; one file may define several relations. Other statements, including `CREATE TABLE AS`, are skipped. A statement that cannot be parsed, or a relation defined twice, is reported as a problem and discovery continues. sqlglot is lenient, so some malformed DDL parses without a problem.

## Operations and producers

An **operation** is a SQL statement that writes one relation. It records its SQL file, the relation it writes, and its kind. The relations it reads come from parsing its SQL. A bare `SELECT` is a full load: its result becomes the relation. `CREATE TABLE AS`, `INSERT`, `INSERT OVERWRITE`, and `MERGE` come later.

SQL has a relation, not the other way round. A relation exists without any SQL; a source has none. The operations that write a relation are its **producers**, and a relation may have several.

Some physical tables may be produced by multiple SQL statements.

The internal execution representation therefore needs to distinguish **relations** from **SQL producers**.

Conceptually:

```text
raw_claims ──→ producer A ──┐
                            ├── customer_activity
raw_customer → producer B ──┘
```

The default QA view remains:

```text
raw_claims ────────┐
                   ▼
            customer_activity
               2 producers
                   ▲
                   │
raw_customer ──────┘
```

QA can drill into `customer_activity` to inspect its producers if necessary.

Mocking remains relation-centric. Mocking `customer_activity` bypasses all of its producers.

Producer-level execution semantics will become important for ordered DML, inserts, merges, and other stateful operations and require technical validation.

---

# Planned User Experience

## Repository config

A repository's **config** says where its SQL, SQL-to-table mapping, schemas, and case folders live. It is a `[tool.sql-test]` table in the repository's `pyproject.toml`, because a Python repository already keeps its pytest and lint settings there, and Python reads TOML without a new dependency. Paths are relative to the repository root.

```toml
[tool.sql-test]
sqls = "admin/sqls"
mapping = "admin/config/lookup_sql_table_mapping.csv"
schemas = "admin/sqls"
cases = "tests/cases"
```

Every setting is required. A repository with no `pyproject.toml`, no `[tool.sql-test]` table, or a missing setting is an error that names what is missing; the tool assumes no layout. The CLI and the app read the config; a repository's own pytest tests may read it too, or pass paths directly.

## Upstream lineage

The **upstream lineage** of a target is the graph relation → operation → relation that leads to it. A relation with producers in the catalog is a **model**, and traversal continues through each of its operations; any other relation is a source, and traversal stops. Projected to relation → relation, it is the default lineage view. Lineage says only what depends on what; what runs is the plan's job.

## Plan

A relation is **given** when the caller supplies its rows; the test layer gives a case's mocks. A **plan** is what a run will do, worked out without executing anything. It marks each relation in the target's lineage as given, executed, pruned, or source, and lists the executed operations in the order they run. Given is the engine's word for what the UI shows as mocked. A relation upstream of a given relation is pruned unless another executed path still needs it. A plan is everything a caller needs about a run without the lineage behind it: the target, each relation's state, what each relation is built from, why each source is a source, what still needs rows, and which given relations are unused. A given relation is **unused** when the run never reads it: every path from it to the target passes through another given relation, or it is not in the target's lineage at all. The app's lineage view draws the plan. `Engine.execute(plan, rows)` runs that plan; `Engine.run` is plan then execute. Callers that already have a plan (the test layer, the app) execute it instead of planning again.

The application is initially launched against a single local repository. The repository is always passed in, for example `sql-test app <path>`. The tool never assumes where a consuming repository lives or that it is inside the tool's own directory.

`lakehouse-data-customer/` is a sample consuming repository kept in this directory for now. Nothing in the tool or its own tests may depend on it being there.

It discovers:

- SQL-defined tables
- schemas
- lineage
- existing tests

The application operates against the currently checked-out repository state.

It does not manage branch lifecycle or discover tests from other branches.

## Target discovery

QA can search or browse tables/models.

For each target, the application shows the number of discovered tests, and separately the number of other tests whose pipeline runs it (see Coverage).

Example:

```text
TABLE                         TESTS    IN PIPELINES

customer_summary                8           0
customer_demographics           4           8
member_attribution              0           3
customer_claim_history         12           0
```

## Lineage

Selecting a target displays its upstream table lineage.

QA can select any appropriate upstream table and mark it as mocked.

The lineage updates immediately to show what will execute and what has been pruned.

## Mock editor

Selecting a mocked table opens a schema-aware table editor.

Minimum functionality:

- edit cells
- add rows
- delete rows
- duplicate rows
- represent NULL
- basic type validation
- paste tabular data from spreadsheet applications

Schema information is discovered from the repository rather than persisted separately in the test case.

## Execution

QA can execute the test interactively.

The application materializes mocked relations, executes the required SQL, and returns the table under test.

Execution goes through the same engine used by pytest and CI.

## Expected vs. actual

After execution, QA sees expected and actual results together.

The comparison should identify:

- matching rows/values
- changed values
- expected rows that are missing
- unexpected actual rows

Actual output is read-only.

Expected output is editable.

QA should be able to:

- edit an expected value
- accept an actual value as expected
- accept an actual row as expected
- remove an obsolete expected row
- accept the complete actual result as the expectation

This interaction is central to the product.

### Comparison defaults

These rules are part of the case format; changing one means migrating every case.

- **Row order** is ignored, unless the target's SQL ends in a top-level `ORDER BY`; then expected rows must appear in that order. The executor must return the target's rows in the order its SQL produced them.
- **Duplicates count.** Rows are compared as a multiset: if expected has a row once and actual has it twice, the case fails.
- **NULL** is an empty, unquoted cell. A quoted empty cell (`""`) is an empty string. Spreadsheets do not quote empty cells, so pasted blanks are NULL.
- **Columns:** only the columns listed in `expected.csv` are checked; other output columns are ignored. A listed column the target does not have fails the case.
- **Values** are compared after typing the expected cells with the target's schema, so `1` and `1.0` in an integer column are equal. An expected cell that cannot be cast to its column's type fails the case, naming the cell.
- **Outcomes:** each expected row is matched, changed, or missing, and each actual row left over is unexpected. An expected row and an actual row that differ but agree on at least half of the checked columns (with two or more columns) are reported as one changed row, naming the columns that differ; otherwise they are a missing row and an unexpected row.

## Saving

Saving writes the case folder (see Saved format) into the repository's working tree.

The application does not need to create branches, commits, pushes, or PRs.

The resulting test must be independently discoverable and executable by normal pytest/CI execution.

## Existing tests

Existing committed tests are discovered from the repository.

Opening an existing test loads it into the same workbench used to create new tests.

There should not be separate creation and test-management experiences.

---

# Coverage

Coverage and test discoverability are in scope.

The first coverage implementation should remain deliberately simple.

## Initial target coverage

For each table:

- number of discovered tests
- whether at least one test targets the table
- number of other tests whose pipeline executes the table's SQL

A table that only executes as part of another table's test pipeline is counted separately. It is not tested, because no test checks its output. It is still shown, and selecting the count lists those tests so QA can open one.

The pipeline count is derived from saved cases and lineage with mock boundaries applied. It does not require running the tests.

Example:

```text
customer_summary             8 tests    0 in pipelines
customer_demographics        4 tests    8 in pipelines
member_attribution           0 tests    3 in pipelines
```

This immediately answers:

> Which data products currently have no tests?

and, for a table with no tests, whether any existing test already executes it.

## Future structural coverage

Because the application understands both lineage and mock boundaries, it can eventually determine which models/producers are actually executed by the discovered test suite.

For example:

```text
A       not executed
B       in pipelines
C       not executed
D       in pipelines
TARGET  tested
```

Producer-level coverage can later distinguish partially tested multi-producer tables.

This is more meaningful than test count alone, but it is not required for the initial POC.

Coverage should always be derived from the tests and lineage at the currently loaded repository state rather than persisted separately.

---

# Architecture

## One engine, thin entry points

The tool is a single pip-installable Python project with one shared engine, a test layer over it, and several thin entry points. Entry points depend on the test layer and the engine. The engine depends on none of them and does not know which one called it.

The engine knows SQL, tables, and rows, not tests. It is given a folder of SQL, holding DDL and DML, and a SQL-to-table mapping. Asked for a table and given rows for some tables, it runs the SQL between them and returns that table's rows. It has no notion of a case, a mock, or an expected result.

The test layer owns test semantics. It reads a case, passes the case's mocked tables to the engine as rows, and compares what the engine returns with the expected rows.

```text
 Authoring app     pytest       CLI
       │             │           │
       └─────────────┼───────────┘
                     ▼
               Shared engine
```

CI runs pytest. It does not add CI-specific behavior to the engine.

The engine owns:

- SQL discovery and parsing
- schema discovery
- lineage construction
- pruning tables whose rows are given
- execution planning
- loading given rows
- SQL execution (tentatively DuckDB, swapped for Spark later)
- full-load and incremental semantics
- cleanup

The test layer owns:

- repository discovery
- test-case discovery and loading
- mock-boundary resolution
- expected/actual comparison

Avoid one implementation per entry point. Separate app, pytest, and CI engines would drift, and a case could pass in the app and fail in CI.

## Entry points

**Authoring app.** The local web application QA uses. It contains presentation and interaction logic only and runs against the checked-out repository, for example `sql-test app .`.

`sql-test app <repository-path>` starts a local [NiceGUI](https://nicegui.io) server (`register_app(repository)` registers the pages, `serve` runs them). The browser page talks only to that server, and the page's state (mocks, grid rows, last result) lives in the server process, one state object per open workbench. The server is given the repository path at startup and is the only process that reads or writes the repository. The page does not use the browser's folder-access APIs: the app must share discovery and execution with the CLI and pytest through the same engine, and a page that talked to the filesystem directly would re-implement or bypass that. Presentation stays in the page; all repository I/O stays behind the shared core.

Safeguards for that server:

- Bind to localhost only, never to a public interface.
- Scope every filesystem read and write to the repository path passed on the command line; resolve paths and refuse any that escape the repository root.
- Do not accept an alternate repository path from the browser after start; the path is fixed when the process starts.
- No authentication in v0. Localhost-only is the trust boundary.

**pytest.** A repository's own pytest tests import the package. A test can call the engine with rows written in Python, or run the repository's case folders as one parametrized test per case, passing the folder that holds them. A case saved by the app is a normal repository test, and it runs through pytest without the app installed or running. A plugin that collects case folders with no test file is deferred until the parametrized style has been used for a while.

**CLI.** The process entry for the authoring app:

```bash
sql-test app [repository] [--port 8765]
```

`repository` defaults to `.`; `--port` defaults to `8765`. The server binds to localhost only. pytest remains the canonical test runner; the CLI does not re-run cases. Other commands (`discover`, `validate`, `run`) stay deferred until a demonstrated need (for example a pre-commit hook) appears.

**Reusable GitHub Actions workflow.** It lives in the tool's repository. A consuming repository calls it in a few lines:

```yaml
jobs:
  data-tests:
    uses: mvictoria/sql_test/.github/workflows/data-tests.yml@v0
```

The workflow checks out the calling repository, sets up Python, installs `sql-test` from this repository at the same git commit as the workflow pin (`github.workflow_sha`), and runs pytest. It works from the checked-out repository, not from SQL, schema, or case files passed as parameters. Local installs use the same tags via `uv` and a git URL (see the README adoption section); PyPI is not required.

**Pre-commit, later.** If static case checks earn their keep, a `sql-test validate` command could back a hook. That is not a reason to grow the CLI today; execution stays with pytest and CI.

**Other consumers** such as IDE integrations, coverage reporting, change-impact tooling, and CDC tooling can be added the same way, only when there is a demonstrated use case.

## Ownership

Data-product repositories own their data products and test cases. The tool's repository owns the machinery that authors, validates, discovers, and executes them. No engine code is copied into a consuming repository.

A consuming repository needs very little. The README adoption section is the copy-paste guide; the footprint is SQL, schemas, cases, `[tool.sql-test]` in `pyproject.toml`, a pytest test over case folders, and a workflow caller:

```text
customer-data/
├── sql/
├── schemas/
├── cases/
│   └── <table under test>/<case name>/
├── pyproject.toml                       [tool.sql-test] paths
└── .github/workflows/data-tests.yml     calls the reusable workflow @v0
```

This layout is illustrative. Where SQL, schemas, and cases live, and how SQL files map to tables, can differ per repository. The sample repository keeps SQL in `admin/sqls/` and maps each table to its SQL file in `admin/config/lookup_sql_table_mapping.csv`, with columns `table_ref` and `sql_ref`. Extra columns such as `load_type` are ignored.

## Versioning

The engine, CLI, app, and reusable workflow are released together as one version. Consuming repositories pin a floating major tag such as `@v0` (while the package is 0.x), never `main`, so a change on the tool's `main` branch cannot silently change CI in every consuming repository.

The git tag is the source of truth for the package version (`dynamic = ["version"]` via hatchling and `uv-dynamic-versioning`).

**How a release is cut.** A PR title includes exactly one of `(major)`, `(minor)`, or `(patch)`. After that PR lands on `main` (linear history: rebase, so branch SHAs are rewritten), `.github/workflows/cd.yml` looks up the PR for the new `main` tip, computes the next `vX.Y.Z` from the latest version tag via `scripts/cd_bump.py`, and tags **that `main` commit**. The same workflow then builds the sdist/wheel from the tag, creates or updates the GitHub Release with those artifacts, and force-moves the floating major tag `vX`. A PR title without a bump token does not release. Pushing a `vX.Y.Z` tag by hand still runs the build/release half only.

Local and CI installs both use those git tags (for example `uv add "sql-test @ git+https://github.com/mvictoria/sql_test.git@v0"`).

The case format carries its own format version if compatibility ever requires it. The tool's release version and the case format version are separate.

## Tool repository layout

One repository is enough. The engine, app, and workflow do not need to be split into separate repositories or products.

The package has one subpackage per layer:

```text
sql-test-tool/
├── src/sql_test/
│   ├── engine/                 relations, operations, rows; no test vocabulary
│   │   ├── catalog/            the catalog, its readers, and repository adapters
│   │   ├── lineage/            what depends on what
│   │   ├── planner/            what runs, and in what order
│   │   └── executor.py         the executor interface
│   ├── executors/
│   │   └── duckdb.py           an executor; Spark later
│   ├── testing/                the test layer
│   │   ├── cases/
│   │   └── comparison/
│   └── integrations/
│       ├── cli.py              sql-test discover / app
│       ├── discover.py
│       └── app/                local authoring app (NiceGUI)
│           ├── serve.py        localhost-only bind; register_app, serve
│           ├── home.py         tables, coverage, cases, pipelines page
│           ├── workbench.py    the workbench page: state, actions, deep links
│           ├── state.py        WorkbenchState
│           ├── lineage_view.py, grid_view.py, result_view.py, sql_view.py
│           ├── mocks.py        frontier_mocks, mock toggling
│           └── grid.py, compare_view.py, case_load.py, case_save.py,
│               engine_access.py      the helpers that hold no UI code
├── .github/workflows/data-tests.yml
├── tests/
└── pyproject.toml
```

An **executor** runs operations against rows in one SQL engine, such as DuckDB or Spark. The engine defines the executor interface and is handed an executor; it never imports one. The interface takes relations and operations, not lineage or cases, and is one call: `run(given, operations)` loads each given relation from its schema and rows, executes the operations in order, and returns the rows of every given and written relation. How an operation's kind becomes SQL, for example a full-load `SELECT` becoming a table, and how a run is kept apart from other runs, are decided per executor; DuckDB keeps one instance per executor, and each call attaches its own in-memory database and drops it afterwards, even when the call fails. Opening a new DuckDB database costs more than a small run, so runs share the instance; concurrent calls each get their own cursor and database, so none sees another's relations. A call naming a catalog, as in `lakehouse.claims.members`, gets a throwaway instance with each catalog attached under its own name instead, because attached database names are global to an instance; DuckDB's own databases, `memory`, `system`, and `temp`, cannot be used as catalogs.

Dependencies point one way:

- the engine imports none of the other layers
- executors import only the engine's interface
- the test layer imports the engine
- integrations import the test layer, the engine, and executors

Each layer's package is its **front door**: `sql_test.engine`, `sql_test.executors`, and `sql_test.testing` export what other layers and consuming repositories use, and nothing outside a layer imports its modules directly. Executors import only `sql_test.engine.executor`, the executor interface, which also exports the types an executor handles. The authoring app is handed one `Executor` at `register_app` / `serve` and does not construct one itself.

## Entry point sequence

Entry points are added one at a time, and each stays thin:

1. Engine as a headless spike (Phase 0).
2. Minimal CLI around the engine.
3. Authoring app (Phases 1–5).
4. Durable case format and repository pytest tests (Phase 6). This may overlap with the app, because the app must save cases that pytest can run.
5. Reusable GitHub Actions workflow.
6. Mature discovery and coverage (Phase 8).
7. Additional execution capabilities, such as incremental models (Phase 7) and Spark.
8. Much later, pre-commit validation.

---

# Scope: Initial POC

The POC should prove one complete workflow:

> Select target → understand lineage → choose mocks → enter data → execute real SQL → inspect actual vs. expected → edit expected → save a real pytest test.

The minimum capabilities are:

1. Single local repository.
2. Discover SQL-defined tables.
3. Identify referenced tables.
4. Treat relations not defined in the repo as source tables.
5. Build upstream lineage for a selected target.
6. Select relations to mock.
7. Prune lineage at mock boundaries.
8. Enter/edit mock table data.
9. Execute the remaining SQL.
10. Display target output.
11. Display expected vs. actual differences.
12. Edit expected results.
13. Save the test artifact.
14. Reload an existing test.
15. Execute the saved test independently through pytest.

Basic test counts/target coverage should be included if test discovery is inexpensive once test persistence is implemented.

---

# Explicitly Outside the POC

The following should not be required to validate the initial product:

- multi-repository execution
- cross-repository lineage
- repository/version selection
- Git branch management
- commits
- pushes
- PR integration
- test review workflow
- historical test-run management
- production-data sampling
- relationship/foreign-key integrity modeling
- sophisticated semantic coverage
- automated fixture migration
- centralized service or multi-user server
- CDC/change propagation testing
- SQL editing
- schema editing
- pre-commit validation

Incremental models should follow the initial full-load implementation unless supporting them proves inexpensive enough to include without delaying validation of the core workflow.

---

# Planned Implementation Order

## Phase 0 — Execution feasibility spike

Before building significant UI, prove the underlying mechanics against representative SQL from a real repository.

Build a headless API capable of approximately:

```text
run_test(
    target,
    mocks,
    expected
)
```

It should:

- discover SQL
- derive dependencies
- construct lineage
- identify source tables
- apply mock boundaries
- determine the required execution set
- execute SQL
- return target output
- compare actual and expected

Test this against several representative models, including at least one structurally difficult model.

### Exit criterion

We can deterministically execute representative repository SQL from mocked inputs and obtain the target relation.

---

## Phase 1 — Repository and target discovery

Add:

- local repo loading
- model/table discovery
- target search/selection
- basic schema discovery

### Dependency

Requires stable repository discovery from Phase 0.

---

## Phase 2 — Lineage visualization

Add:

- upstream table graph
- source identification
- mock/unmock interaction
- mocked/executed/pruned states

### Dependency

Requires dependency extraction and execution planning from Phase 0.

---

## Phase 3 — Mock data editor

Add:

- schema-aware grid
- add/delete/duplicate rows
- NULL
- basic type validation
- spreadsheet paste

### Dependency

Requires schema discovery.

---

## Phase 4 — Interactive execution

Connect the workbench to the execution framework.

QA can now:

```text
target → mocks → Run → actual result
```

### Dependency

Requires Phases 0–3.

---

## Phase 5 — Expected/actual diff

Add:

- expected table editor
- actual output
- row/value differences
- accept actual cell/row
- accept complete actual output

At this point the application should support the complete test-authoring loop.

### Dependency

Requires stable interactive execution.

---

## Phase 6 — Test persistence and discovery

Add:

- save test artifact into repo
- discover existing tests
- load existing test
- modify existing test
- target-level test counts
- simple target coverage

Validate that saved tests run independently through normal pytest execution.

### Dependency

Requires the persisted test format and test framework contract to be stable enough to become durable repository artifacts.

---

## Phase 7 — Incremental models

Add:

- recognition of incremental models
- target-before fixture
- self-reference represented as before/after state
- execution of incremental DML
- expected target-after comparison

### Dependency

Requires clear Spark/DML execution semantics.

---

## Phase 8 — Richer lineage and coverage

Potential additions:

- multi-producer table drill-down
- producer-level execution graph
- structural execution coverage
- producer coverage
- intermediate result inspection

These should be driven by demonstrated QA/debugging needs rather than required for the initial authoring workflow.

---

## Phase 9 — Multi-repository workspaces

Allow lineage to span repositories.

A workspace may contain:

```text
customer-repo
claims-repo
eligibility-repo
```

The repository owning the table under test always owns the test case.

Cross-repository tables can participate in lineage and can be mocked.

Repository versions may eventually be independently selectable.

### Dependency

Requires stable relation identity and single-repo lineage/execution semantics.

---

## Later — CDC / Change Propagation Testing

Support questions such as:

> If this upstream row is inserted, updated, or deleted, what changes downstream?

Conceptually:

```text
state before
    ↓
upstream INSERT / UPDATE / DELETE
    ↓
incremental pipeline
    ↓
state after
```

Potentially show before/after/delta at each affected downstream table.

CDC should be considered in architectural decisions but should not influence the initial test model or POC implementation.

---

# Feature Dependencies

```text
Repo discovery
      │
      ├──────────────→ Schema discovery ──→ Mock editor
      │
      ▼
SQL dependency discovery
      │
      ▼
Internal execution graph
      │
      ├──────────────→ Table lineage UI
      │                      │
      │                      ▼
      │                 Mock boundaries
      │                      │
      └──────────────────────┘
                 │
                 ▼
           Execution planner
                 │
                 ▼
           SQL execution
    (DuckDB, Spark later)
                 │
                 ▼
             Actual output
                 │
                 ▼
         Expected/actual diff
                 │
                 ▼
           Test persistence
                 │
          ┌──────┴───────┐
          ▼              ▼
    pytest / CI     Test discovery
                         │
                         ▼
                       Coverage
```

Incremental execution builds on the same stack but adds target-before state and self-reference handling.

Multi-repo support should build on stable single-repo relation identity and lineage rather than being introduced into the first implementation.

---

# Execution Environment / Spark

Execution tentatively runs on DuckDB and is swapped for Spark later. The swap is a new executor behind the engine's executor interface, so the app, pytest tests, and saved cases do not change.

Most production SQL is expected to execute under Spark.

Local interactive execution therefore represents a significant technical risk once Spark is in scope.

The tool should not casually substitute another SQL engine if doing so changes DML or SQL semantics.

The execution feasibility spike should answer:

> Can we take repository SQL + mocked relations + optional target-before state, execute it with sufficiently faithful Spark semantics, and return results quickly enough for an interactive QA workflow?

Potential approaches include local Spark or a remote Spark execution environment. This decision should be based on measured fidelity and latency rather than UI convenience.

---

# Success Metrics

The primary measure should be whether the tool makes real test authoring materially easier.

## End-to-end authoring

A QA engineer unfamiliar with the tool should be able to take a real target and:

1. find it
2. understand its upstream dependencies
3. select appropriate mock boundaries
4. construct mock data
5. execute the SQL
6. understand an expected/actual difference
7. correct the expectation
8. save the test
9. execute the resulting test through normal pytest

without editing Python or manually reconstructing lineage.

## Time to first result

Measure:

> Time from selecting a target to seeing the first actual output.

This captures lineage usability, fixture ergonomics, and execution latency.

The POC should establish a baseline against the current QA workflow and demonstrate a meaningful reduction.

## Iteration latency

Measure:

> Time from changing one mock/expected value to seeing the new result.

This is especially important for an interactive tool. Spark setup overhead may be technically acceptable for CI while still making the authoring experience unusable.

## Test-authoring time

Compare:

> Time required to construct a representative test using the current process versus the authoring tool.

This is likely the most important product metric.

## Successful independent execution

100% of tests saved by the tool should be independently executable by the standard pytest/CI framework without requiring the application.

## Lineage correctness

For representative repository models, discovered upstream dependencies and pruning behavior should match the actual execution dependencies.

Incorrect lineage is more damaging than incomplete visualization because QA will make test-boundary decisions based on it.

## Discoverability

QA should be able to answer quickly:

- Does this table have tests?
- What tests exist?
- Which tables currently have no tests?
- What does a particular test mock and expect?

without manually searching the repository.

---

# Underlying Assumptions

The current design assumes:

- SQL and schemas are available in the repository.
- SQL is primarily DML.
- pytest is the canonical test runner.
- Tests are case folders of CSVs that pytest discovers and parametrizes over.
- Tests are durable and committed to GitHub.
- The authoring application is not required for CI execution.
- Most production execution uses Spark.
- Models are generally full-load or incremental.
- Incremental models may self-reference their existing target.
- A relation referenced but not produced by SQL in the current repo can initially be treated as a source.
- A table whose SQL cannot be parsed, or that has no schema, is classified as a source; lineage stops there.
- Source relations can be mocked.
- Relationship integrity between fixture tables is not currently modeled.
- QA primarily reasons about tables rather than individual SQL statements.
- Engineers own Git lifecycle.
- The currently checked-out repo state defines what the tool discovers.
- Tests from other branches are not combined into discovery or coverage.

These assumptions should be revisited when extending to multi-repository execution.

---

# Open Questions and Technical Risks

## Spark execution

Deferred. Execution tentatively runs on DuckDB until Spark is swapped in.

When Spark is in scope: can it be initialized and reused with sufficiently low latency for interactive test authoring?

## SQL parsing and lineage fidelity

How reliably can the repository's SQL be mapped into:

```text
inputs → operation → outputs
```

particularly for templated SQL, multi-statement files, merges, inserts, and multiple producers?

SQL that fails to parse becomes a source, so parse failures limit how far back lineage reaches rather than blocking a test. The remaining risk is SQL that parses but yields wrong dependencies, because QA chooses mock boundaries from that lineage.

## Multiple producers

How frequently do multiple SQL operations produce the same relation, and are their execution/order semantics discoverable from existing repository conventions?

## Comparison semantics

Row order, duplicates, NULL, and column subsets are decided in [Comparison defaults](#comparison-defaults). Still open:

- decimals: exact, or within a tolerance
- timestamps: time zones and precision
- nested Spark types

The POC should establish sensible defaults without exposing unnecessary configuration to QA.

## Incremental semantics

The framework needs a deterministic way to materialize `target_before`, execute incremental SQL, and inspect `target_after`.

This should be solved after the full-load authoring loop unless it blocks representative testing.

---

# POC Exit Criteria

The POC is successful when a QA engineer who did not build the application can use it on a real repository to:

> Find a target table, understand its lineage, mock appropriate upstream relations, construct a scenario, run the real SQL, inspect the output, reconcile actual versus expected results, save the test, and have that test execute successfully through ordinary pytest without the application.

The POC should demonstrate that this workflow is materially faster or easier than creating the same test manually.

If the execution framework cannot provide sufficiently faithful Spark behavior or interactive execution latency, that should be treated as a POC finding rather than compensated for by building additional UI.
