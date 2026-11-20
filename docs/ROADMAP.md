# Roadmap

Planned versions, the features in each, and the stories that make up each feature. Design decisions behind these are in [HELPER.md](HELPER.md).

Most stories can be done independently. When a story needs another one first, it says so under **Depends on** and links to it. A story with no dependencies can start any time, including ahead of its version. The version order is the planned order, not a hard sequence: for example, the CI workflow in v0.5 only needs v0.1.

All engine code lives in the package created by [ENG-1](#eng-1). That dependency is not repeated on every story.

The engine is always pointed at a repository and never assumes where one lives. `lakehouse-data-customer/` is a sample consuming repository kept in this directory for now. The tool's own tests use small fixture repositories of their own and must not depend on the sample being present.

---

## v0 — Hand-wired tests (done)

pytest tests in the sample repository's `tests/test_sql.py` load rows into DuckDB and run the SQL in `admin/sqls/`. Chained queries are wired by hand inside each test.

---

## v0.1 — Engine core

A headless engine that runs a case folder end to end on DuckDB, and a pytest plugin that runs every case folder. Done when the v0 scenarios run as case folders through pytest with no hand wiring.

Can start now:

- [ENG-1](#eng-1)
- [ENG-2](#eng-2)
- [ENG-3](#eng-3)
- [ENG-4](#eng-4)
- [ENG-5](#eng-5)
- [ENG-11](#eng-11)
- [ENG-14](#eng-14)
- [ENG-20](#eng-20)

### Project skeleton

<a id="eng-1"></a>
#### ENG-1 Package skeleton

Create the pip-installable `sql_test` package under `src/` with empty `engine/` subpackages for:

- discovery
- lineage
- execution
- comparison
- validation

- **Done when:** the package installs in the dev environment and the v0 tests still pass.
- **Depends on:** none

### Repository discovery

<a id="eng-20"></a>
#### ENG-20 Point the engine at a repository

The engine takes a repository root and reads where that repository keeps its SQL, its schemas, its cases, and its SQL-to-table mapping. Nothing defaults to the tool's own directory.

- **Done when:** the same code discovers a fixture repository under the tool's tests and the sample repository at a path passed in.
- **Depends on:** none

<a id="eng-2"></a>
#### ENG-2 Discover SQL producers

Map each SQL file to the table it writes:

- When the repository has a mapping file, use it. The sample repository's `admin/config/lookup_sql_table_mapping.csv` maps `table_ref` to `sql_ref` and records a `load_type`.
- Otherwise, a `CREATE TABLE AS`, `INSERT`, or `MERGE` names its own target.

Keep `load_type` with each producer for later use. What its values mean is not yet decided.

- **Done when:** in the sample repository, `medicaid_members.sql` and `medicaid_members_named_alice.sql` map to `medicaid_members` and `medicaid_members_named_alice` through the mapping, and a table mapped to two files lists both.
- **Depends on:** none

<a id="eng-3"></a>
#### ENG-3 Discover schemas

Read DDL files from the repository's schema location into each table's columns and types. Read them from the DDL text with sqlglot rather than from DuckDB, because DuckDB drops `varchar` lengths.

- **Done when:** a DDL file for `members` yields the following, replacing `test_medicaid_members_types`:
  - `member_id integer`
  - `member_name varchar(30)`
  - `lob varchar(2)`
- **Depends on:** none

<a id="eng-4"></a>
#### ENG-4 Discover case folders

List every `<table under test>/<case name>/` folder under the repository's case location, and its CSV files, without reading their contents.

- **Done when:** discovery returns, for each case:
  - its target
  - its name
  - its mocked table names
  - whether `expected.csv` exists
- **Depends on:** none

### Lineage

<a id="eng-5"></a>
#### ENG-5 Extract table references

For each SQL statement, list the tables it reads, excluding CTE names. Parse with a configurable dialect, defaulting to DuckDB.

- **Done when:** `medicaid_members_named_alice.sql` reads `medicaid_members`, and a query with a CTE does not report the CTE as a table.
- **Depends on:** none

<a id="eng-6"></a>
#### ENG-6 Build upstream lineage

Build the upstream graph of a target table:

- A table produced by SQL in the repo is a model, and traversal continues.
- Any other table is a source, and traversal stops.

- **Done when:** the lineage of `medicaid_members_named_alice` is `members` (source) → `medicaid_members` (model) → `medicaid_members_named_alice`.
- **Depends on:**
  - [ENG-2](#eng-2)
  - [ENG-5](#eng-5)

<a id="eng-7"></a>
#### ENG-7 Lineage boundaries

A model whose SQL cannot be parsed, or that has no schema, becomes a boundary. Traversal stops there, the table is treated like a source, and the reason is recorded.

- **Done when:** a model with unparseable SQL and a model with no schema each appear as a boundary with the right reason, and their upstream tables are not in the graph.
- **Depends on:**
  - [ENG-6](#eng-6)
  - [ENG-3](#eng-3)

### Execution planning

<a id="eng-8"></a>
#### ENG-8 Apply mocks and prune

Given a target and a set of mocked tables, mark each table in the lineage as one of:

- mocked
- executed
- pruned
- source
- boundary

A table upstream of a mock is pruned unless another executed path still needs it.

- **Done when:** mocking `medicaid_members` prunes `members` and leaves only the Alice SQL to execute, and a diamond-shaped lineage keeps a table that one path still needs.
- **Depends on:** [ENG-6](#eng-6). Boundary states appear once [ENG-7](#eng-7) lands.

<a id="eng-9"></a>
#### ENG-9 Report tables that still need data

List every table that will be read but is not produced by executed SQL and has no rows supplied. A run with any such table fails with a message naming them.

- **Done when:** running the Alice target with nothing mocked reports that `members` needs data.
- **Depends on:** [ENG-8](#eng-8)

<a id="eng-10"></a>
#### ENG-10 Order executed SQL

Order the executed SQL so each statement runs after the tables it reads have been produced.

- **Done when:** the Alice plan runs `medicaid_members.sql` before `medicaid_members_named_alice.sql`, and a cycle is reported as an error.
- **Depends on:** [ENG-8](#eng-8)

### Execution

<a id="eng-11"></a>
#### ENG-11 Execution layer with a DuckDB backend

An execution interface with a DuckDB implementation that uses a fresh in-memory database per run. The interface can:

- create a table from a schema
- load rows
- run SQL
- read a table

Spark is added behind the same interface later, in [SPK-2](#spk-2).

- **Done when:** the interface's own tests pass against DuckDB, and two runs do not share tables.
- **Depends on:** none

<a id="eng-12"></a>
#### ENG-12 Load mocked tables

Create each mocked table from its discovered schema and insert its rows. A boundary table with no schema takes its columns from the rows; how it is typed is an open question in [HELPER.md](HELPER.md).

- **Done when:** a mocked `members` loads with `member_id` as an integer.
- **Depends on:**
  - [ENG-11](#eng-11)
  - [ENG-3](#eng-3)

<a id="eng-13"></a>
#### ENG-13 Run a plan

Execute the ordered SQL against the loaded mocks and return the target's rows and the row count of every table in the plan.

- **Done when:** the Alice plan returns `(1, 'Alice')` with row counts for:
  - `members`
  - `medicaid_members`
  - the target
- **Depends on:**
  - [ENG-10](#eng-10)
  - [ENG-12](#eng-12)

### Comparison

<a id="eng-14"></a>
#### ENG-14 Decide comparison defaults

Decide:

- row ordering
- duplicate handling
- the CSV convention for NULL
- whether `expected.csv` must list every column or only some

Record the decisions in [HELPER.md](HELPER.md). These must be settled before cases are committed, because changing them later means migrating every case.

- **Done when:** the decisions are written in HELPER.md.
- **Depends on:** none

<a id="eng-15"></a>
#### ENG-15 Compare expected and actual

Compare expected and actual rows using the defaults from ENG-14, and report:

- matching rows
- changed values
- missing expected rows
- unexpected actual rows

- **Done when:** each of the four outcomes has a test.
- **Depends on:** [ENG-14](#eng-14)

### Case format and pytest

<a id="eng-16"></a>
#### ENG-16 Read and write case folders

Read a case folder's CSVs into typed rows using the discovered schemas and the NULL convention, and write rows back out in the same format.

- **Done when:** reading a case and writing it back produces identical files.
- **Depends on:**
  - [ENG-4](#eng-4)
  - [ENG-3](#eng-3)
  - [ENG-14](#eng-14)

<a id="eng-17"></a>
#### ENG-17 Run a case

The engine's entry point: take a case folder and return the actual rows, the comparison, and pass or fail. The app, pytest, and the CLI all call this.

- **Done when:** a passing and a failing case folder return the right result.
- **Depends on:**
  - [ENG-13](#eng-13)
  - [ENG-15](#eng-15)
  - [ENG-16](#eng-16)

<a id="eng-18"></a>
#### ENG-18 pytest plugin

Discover every case folder and run each as its own pytest test through ENG-17. A failure shows the comparison or the tables that still need data.

- **Done when:** `pytest` runs one test per case folder, named `<table under test>/<case name>`.
- **Depends on:**
  - [ENG-17](#eng-17)
  - [ENG-9](#eng-9)
  - [ENG-20](#eng-20)

<a id="eng-19"></a>
#### ENG-19 Port the v0 tests

In the sample repository, rewrite the v0 scenarios as case folders, add a schema for `members`, and remove the hand-wired tests from its `tests/test_sql.py`.

- **Done when:** the same scenarios pass through the plugin run against the sample repository, and the hand-wired tests are gone.
- **Depends on:** [ENG-18](#eng-18)

---

## v0.2 — CLI and static validation

A headless command-line interface over the engine, and checks that run without executing SQL.

### CLI

<a id="cli-1"></a>
#### CLI-1 `sql-test discover`

List, for the repository:

- models
- sources
- boundaries
- cases

- **Done when:** run against the sample repository's path, the command lists both v0 models, the `members` source, and every case.
- **Depends on:**
  - [ENG-2](#eng-2)
  - [ENG-4](#eng-4)
  - [ENG-6](#eng-6)
  - [ENG-20](#eng-20)

<a id="cli-2"></a>
#### CLI-2 `sql-test run`

Run one case, several cases, or all of them, and print each result and comparison.

- **Done when:** a failing case prints the same comparison pytest shows.
- **Depends on:** [ENG-17](#eng-17)

### Static validation

<a id="cli-3"></a>
#### CLI-3 Check case structure

Check that:

- the case folder parses
- its target table exists
- its mocked tables exist

- **Done when:** a misspelled target or mock is reported by name.
- **Depends on:**
  - [ENG-16](#eng-16)
  - [ENG-2](#eng-2)

<a id="cli-4"></a>
#### CLI-4 Check a case against lineage

Check that:

- mocked tables are upstream of the target
- no table still needs data

- **Done when:** a mock that is not upstream of the target, and a missing source, are each reported.
- **Depends on:**
  - [ENG-8](#eng-8)
  - [ENG-9](#eng-9)

<a id="cli-5"></a>
#### CLI-5 Check CSVs against schemas

Check that:

- CSV columns match the known schema
- every value parses to its column's type

- **Done when:** an unknown column and a non-integer `member_id` are each reported.
- **Depends on:** [ENG-16](#eng-16)

<a id="cli-6"></a>
#### CLI-6 `sql-test validate`

Run whichever checks exist and exit non-zero on any failure. Each check from CLI-3, CLI-4, and CLI-5 can be added to it as it lands.

- **Done when:** the command runs at least one check and its exit code reflects the result.
- **Depends on:**
  - [CLI-1](#cli-1)
  - at least one of:
    - [CLI-3](#cli-3)
    - [CLI-4](#cli-4)
    - [CLI-5](#cli-5)

---

## v0.3 — Authoring app

The local web app QA uses to build, run, and save cases. It calls the engine for everything and has no test logic of its own.

### App foundation

<a id="app-1"></a>
#### APP-1 Decide how the page reaches the repository

Decide how the page reads and writes the checked-out repository, and record it in [HELPER.md](HELPER.md). Options include:

- a local server started by `sql-test app`
- browser folder access

- **Done when:** the decision and its safeguards are written in HELPER.md.
- **Depends on:** none

<a id="app-2"></a>
#### APP-2 App shell

`sql-test app .` opens the page against the current repository and can list what `discover` lists.

- **Done when:** the page shows the repository's models and cases.
- **Depends on:**
  - [APP-1](#app-1)
  - [CLI-1](#cli-1)

### Target browser

<a id="app-3"></a>
#### APP-3 Browse and select a target

Search or browse tables, select one as the table under test, or select an existing case.

- **Done when:** selecting a table or a case opens it in the workbench.
- **Depends on:** [APP-2](#app-2)

### Lineage view

<a id="app-4"></a>
#### APP-4 Show lineage with states

Draw the upstream graph of the selected target with these states:

- mocked
- executed
- pruned
- source
- boundary

Tables that still need data are grey and turn colored once they have data. A boundary shows why it is a boundary.

- **Done when:** the Alice target shows `members` grey until rows are added.
- **Depends on:**
  - [APP-3](#app-3)
  - [ENG-8](#eng-8)
  - [ENG-9](#eng-9)
  - [ENG-7](#eng-7)

<a id="app-5"></a>
#### APP-5 Mock and unmock from the graph

Click a table to mock or unmock it. The graph redraws with the new states.

- **Done when:** mocking `medicaid_members` shows `members` as pruned.
- **Depends on:** [APP-4](#app-4)

### Mock editor

<a id="app-6"></a>
#### APP-6 Schema-aware grid

Edit a mocked table's rows in a grid with columns from its schema. Add and delete rows.

- **Done when:** rows entered for `members` reach the engine with the right types.
- **Depends on:**
  - [APP-3](#app-3)
  - [ENG-3](#eng-3)

<a id="app-7"></a>
#### APP-7 Duplicate rows, NULL, and type validation

In the grid:

- duplicate a row
- enter NULL distinctly from an empty string
- flag values that do not fit the column's type

- **Done when:** a non-integer `member_id` is flagged before running.
- **Depends on:** [APP-6](#app-6)

<a id="app-8"></a>
#### APP-8 Paste from a spreadsheet

Paste tabular data copied from Excel or Sheets into the grid, with a reminder that fixtures must be synthetic and must not contain real member data.

- **Done when:** pasting several rows and columns fills the grid.
- **Depends on:** [APP-6](#app-6)

### Run and compare

<a id="app-9"></a>
#### APP-9 Run and show the output

Run the case from the page and show the target's rows, with row counts on each table in the graph.

- **Done when:** running the Alice case shows one row and the row counts.
- **Depends on:**
  - [APP-5](#app-5)
  - [APP-6](#app-6)
  - [ENG-17](#eng-17)

<a id="app-10"></a>
#### APP-10 Expected and actual side by side

Show expected and actual together, with these rows marked:

- matching
- changed
- missing
- unexpected

Actual is read-only and expected is editable.

- **Done when:** each of the four outcomes is visible in the view.
- **Depends on:**
  - [APP-9](#app-9)
  - [ENG-15](#eng-15)

<a id="app-11"></a>
#### APP-11 Accept actual as expected

In the expected/actual view:

- accept an actual cell as expected
- accept an actual row as expected
- accept the whole actual result as expected
- remove an obsolete expected row

- **Done when:** accepting the whole actual result makes the case pass.
- **Depends on:** [APP-10](#app-10)

### Save and load

<a id="app-12"></a>
#### APP-12 Save a case

Write the case folder into the working tree. Nothing is committed.

- **Done when:** a case saved from the page passes through pytest without the app running.
- **Depends on:**
  - [APP-6](#app-6)
  - [ENG-16](#eng-16)
  - [ENG-18](#eng-18)

<a id="app-13"></a>
#### APP-13 Load a case

Open an existing case folder in the same workbench used to create cases, with its mocks set in the graph and its rows in the grids.

- **Done when:** loading a saved case and saving it again changes no files.
- **Depends on:**
  - [APP-3](#app-3)
  - [ENG-16](#eng-16)

---

## v0.4 — Discovery and coverage

Per-table test counts, and a separate count of tests whose pipeline runs a table. Coverage is always derived from the current checkout, never stored.

<a id="cov-1"></a>
#### COV-1 Test counts per table

Count the cases that target each table.

- **Done when:** each table reports its number of cases, including zero.
- **Depends on:** [ENG-4](#eng-4)

<a id="cov-2"></a>
#### COV-2 In-pipeline counts per table

For each table, count the other cases whose plan executes its SQL, using lineage with each case's mocks applied. No SQL is run.

- **Done when:** with only the Alice case, `medicaid_members` reports zero tests and one in a pipeline.
- **Depends on:**
  - [ENG-8](#eng-8)
  - [ENG-16](#eng-16)

<a id="cov-3"></a>
#### COV-3 `sql-test coverage`

Print tests and in-pipeline counts per table, untested tables first.

- **Done when:** the report lists untested tables before tested ones.
- **Depends on:**
  - [COV-1](#cov-1)
  - [COV-2](#cov-2)
  - [CLI-1](#cli-1)

<a id="cov-4"></a>
#### COV-4 Coverage in the target browser

Show TESTS and IN PIPELINES next to each table. Selecting the in-pipeline count lists those cases, and selecting one opens it.

- **Done when:** a table with zero tests and one pipeline case can be opened from the browser.
- **Depends on:**
  - [COV-1](#cov-1)
  - [COV-2](#cov-2)
  - [APP-3](#app-3)
  - [APP-13](#app-13)

---

## v0.5 — CI

Consuming repositories run their cases in GitHub Actions with a few lines of setup. This only needs v0.1 and can be pulled earlier.

<a id="ci-1"></a>
#### CI-1 Reusable GitHub Actions workflow

A workflow in this repository that:

1. checks out the calling repository
2. sets up Python
3. installs the package
4. runs pytest

- **Done when:** a test repository calling the workflow runs its cases in CI.
- **Depends on:** [ENG-18](#eng-18)

<a id="ci-2"></a>
#### CI-2 Versioned releases

Release the package and workflow together under tags such as `v1`, so consuming repositories pin a tag instead of `main`.

- **Done when:** a consuming repository pinned to a tag is unaffected by a change on `main`.
- **Depends on:** [CI-1](#ci-1)

<a id="ci-3"></a>
#### CI-3 Adoption guide

Document the minimal footprint of a consuming repository:

- SQL
- schemas
- cases
- optional config
- the workflow caller

- **Done when:** someone can set up a new repository from the guide alone.
- **Depends on:** [CI-1](#ci-1)

---

## v0.6 — Spark execution

Swap execution to Spark behind the same execution layer, so the app, pytest plugin, and saved cases do not change.

<a id="spk-1"></a>
#### SPK-1 Representative model set

Choose a small set of models from a real repository:

- a simple full-load model
- a model with several upstream tables
- a source not defined in the repo
- a meaningful mock boundary
- a multi-producer case, if common
- an incremental model

- **Done when:** the set is checked in as case folders.
- **Depends on:** [ENG-16](#eng-16)

<a id="spk-2"></a>
#### SPK-2 Spark backend

A Spark implementation of the execution interface from ENG-11.

- **Done when:** the execution interface's tests pass against Spark.
- **Depends on:** [ENG-11](#eng-11)

<a id="spk-3"></a>
#### SPK-3 Measure fidelity and latency

Run the representative set on DuckDB and on Spark, and record:

- results that differ
- time to first result
- rerun time

- **Done when:** the measurements are written up.
- **Depends on:**
  - [SPK-1](#spk-1)
  - [SPK-2](#spk-2)

<a id="spk-4"></a>
#### SPK-4 Choose execution per entry point

Using SPK-3, decide what the app and CI run on, and record it in [HELPER.md](HELPER.md). Options:

- local Spark
- remote Spark
- DuckDB

- **Done when:** the decision is written in HELPER.md.
- **Depends on:** [SPK-3](#spk-3)

---

## v0.7 — Incremental models

Models that read their own target, tested as target before and target after rather than as a cycle.

<a id="inc-1"></a>
#### INC-1 Recognize incremental models

Detect SQL that reads the table it writes, and show it as before and after rather than as a cycle.

- **Done when:** a self-referencing model is detected and its lineage has no cycle.
- **Depends on:**
  - [ENG-5](#eng-5)
  - [ENG-6](#eng-6)

<a id="inc-2"></a>
#### INC-2 Decide how target-before is stored

Decide how a case folder holds the target's before state, and record it in [HELPER.md](HELPER.md).

- **Done when:** the decision is written in HELPER.md.
- **Depends on:** none

<a id="inc-3"></a>
#### INC-3 Run incremental cases

Load the target's before state, run the incremental SQL, and compare the target after against expected.

- **Done when:** an incremental case passes and fails correctly.
- **Depends on:**
  - [INC-1](#inc-1)
  - [INC-2](#inc-2)
  - [ENG-13](#eng-13)
  - [SPK-4](#spk-4)

<a id="inc-4"></a>
#### INC-4 Incremental cases in the app

Edit the target's before state in the grid and show before and after in the lineage view.

- **Done when:** an incremental case can be created and saved from the page.
- **Depends on:**
  - [INC-3](#inc-3)
  - [APP-4](#app-4)
  - [APP-6](#app-6)

---

## v0.8 — Richer lineage and coverage

Added when QA or debugging needs show they are worth it.

<a id="lin-1"></a>
#### LIN-1 Multi-producer drill-down

A table written by several SQL statements shows "N producers" in the graph and lists them on drill-down.

- **Done when:** a table with two producers shows both.
- **Depends on:**
  - [ENG-2](#eng-2)
  - [APP-4](#app-4)

<a id="lin-2"></a>
#### LIN-2 Ordering for sequential writes

Order several statements that write the same table in sequence, such as an insert followed by a merge.

- **Done when:** a two-step write produces the same result as running the statements in repository order.
- **Depends on:** [ENG-10](#eng-10)

<a id="lin-3"></a>
#### LIN-3 Structural coverage

Report each table and producer, across all cases, as one of:

- tested
- in pipelines
- not executed

- **Done when:** a producer that no case executes is reported as not executed.
- **Depends on:**
  - [COV-2](#cov-2)
  - [LIN-1](#lin-1)

<a id="lin-4"></a>
#### LIN-4 Inspect intermediate results

After a run, open any executed table's rows and see at which table an input row was dropped.

- **Done when:** for the Alice case, Bea's row is shown as dropped at `medicaid_members_named_alice`.
- **Depends on:**
  - [APP-9](#app-9)
  - [ENG-13](#eng-13)

---

## Later — not yet planned

- **Pre-commit validation.** A hook running `sql-test validate`. Depends on [CLI-6](#cli-6).
- **Multi-repository workspaces.** Lineage across repositories, where the repository that owns the table under test owns the case. Depends on stable single-repository lineage from v0.1 and v0.8.
- **CDC and change propagation.** What changes downstream when an upstream row is inserted, updated, or deleted. Depends on v0.7.
- **Other consumers** such as IDE integrations or change-impact tooling, when there is a demonstrated use case.
