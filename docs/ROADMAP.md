# Roadmap

Planned versions, the features in each, and the stories that make up each feature. Design decisions behind these are in [HELPER.md](HELPER.md). Architectural direction is in [foss-architecture-thoughts.md](foss-architecture-thoughts.md): specific implementation, general architecture.

Most stories can be done independently. When a story needs another one first, it says so under **Depends on** and links to it. A story with no dependencies can start any time, including ahead of its version. The version order is the planned order, not a hard sequence: for example, the CI workflow in v0.5 only needs v0.1.

All engine code lives in the package created by [ENG-1](#eng-1). That dependency is not repeated on every story.

Nothing assumes where a repository lives. The engine is given a folder of SQL and a mapping, and the test layer is given a repository. `lakehouse-data-customer/` is a sample consuming repository kept in this directory for now. The tool's own tests use small fixture repositories of their own and must not depend on the sample being present.

---

## v0 — Hand-wired tests (done)

pytest tests in the sample repository's `tests/test_sql.py` load rows into DuckDB and run the SQL in `admin/sqls/`. Chained queries are wired by hand inside each test.

---

## v0.1 — Engine core

A headless engine, and a test layer over it, that run a case folder end to end on DuckDB, and a pytest plugin that runs every case folder. Done when the v0 scenarios run as case folders through pytest with no hand wiring.

The engine knows relations, operations, and rows. The test layer knows cases, mocks, and expected results, and hands the engine a case's mocks as given rows.

Done:

- [ENG-1](#eng-1)
- [ENG-20](#eng-20)
- [ENG-10](#eng-10), ahead of the plan it belongs in
- [ENG-23](#eng-23)
- [ENG-21](#eng-21)
- [ENG-2](#eng-2)
- [ENG-3](#eng-3)
- [ENG-4](#eng-4)
- [ENG-22](#eng-22)
- [ENG-5](#eng-5)
- [ENG-6](#eng-6)
- [ENG-8](#eng-8)
- [ENG-9](#eng-9)
- [ENG-7](#eng-7)
- [ENG-11](#eng-11)

Can start now:

- [ENG-12](#eng-12)
- [ENG-14](#eng-14)

### Project skeleton

<a id="eng-1"></a>
#### ENG-1 Package skeleton (done)

Create the pip-installable `sql_test` package under `src/` with empty `engine/` subpackages for:

- discovery
- lineage
- execution
- comparison
- validation

- **Done when:** the package installs in the dev environment and the v0 tests still pass.
- **Depends on:** none

<a id="eng-23"></a>
#### ENG-23 Lay out packages by layer (done)

Replace ENG-1's layout with one package per layer, so dependencies point one way:

- the engine: catalog, lineage, planner
- executors: DuckDB, later Spark
- the test layer: cases, comparison, validation
- integrations: the pytest plugin, later the CLI and app server

The engine depends on the executor interface, not on an executor. The test layer depends on the engine. Integrations depend on the test layer. Record the layout and the package names in [HELPER.md](HELPER.md).

The engine is handed its executor, for example `Engine(sqls, mapping, executor=DuckDBExecutor)`, instead of creating one.

- **Done when:** the existing code lives in the new layout, the tests pass with only their imports and the engine's construction changed, and no engine module imports from the test layer or an executor.
- **Depends on:** none

### Catalog

<a id="eng-20"></a>
#### ENG-20 Point the engine at a folder of SQL (done)

The engine is given, in code, a folder of SQL holding DDL and DML, and a SQL-to-table mapping. Nothing defaults to the tool's own directory. `Engine(sqls, mapping).run(table, rows)` loads the given rows, runs the table's SQL, and returns the table's rows. The engine uses no test vocabulary: rows, not mocks. A config file for these paths comes later, in [CFG-1](#cfg-1).

- **Done when:** given `members` and `lob` rows, the fixture repository's `medicaid_members` returns only the Medicaid member.
- **Depends on:** none

<a id="eng-21"></a>
#### ENG-21 Relation identity (done)

A relation is identified by an optional catalog, an optional schema, and a name, not by a bare table name or a file path. Real repositories may use three-level names such as `catalog.schema.table`. sqlglot parses and normalizes names; the engine wraps them in its own small type. A shorter name, as written in SQL, a mapping, or given rows, resolves to a relation when exactly one matches. Leave room for a repository later, for multi-repository workspaces. Running SQL with qualified names on DuckDB, which needs attached catalogs and schemas, belongs to the executor, not this story. Define *relation* in [HELPER.md](HELPER.md).

- **Done when:**
  - `catalog.schema.table`, `schema.table`, and `table` parse into their parts
  - `claims.members` and `billing.members` are different relations, and table references in SQL keep their qualification
  - a bare `members` resolves when only one relation matches
  - an ambiguous bare name is an error that names the candidates
- **Depends on:** none

<a id="eng-2"></a>
#### ENG-2 Discover operations (done)

An operation is a SQL statement that writes a relation. Lineage runs relation → operation → relation, so one relation can have several producers. Each operation records:

- its SQL file
- the relation it writes
- its kind: a bare `SELECT` is a full load; `CREATE TABLE AS`, `INSERT`, `INSERT OVERWRITE`, and `MERGE` come later
- its `load_type`, whose values are not yet defined

The relation an operation writes comes from the repository's mapping file when it has one. The sample repository's `admin/config/lookup_sql_table_mapping.csv` maps `table_ref` to `sql_ref`. Otherwise, a `CREATE TABLE AS`, `INSERT`, or `MERGE` names its own target. Define *operation* in [HELPER.md](HELPER.md).

- **Done when:** in the sample repository, `medicaid_members.sql` and `medicaid_members_named_alice.sql` are full-load operations writing `medicaid_members` and `medicaid_members_named_alice`, and a relation mapped to two files has two operations.
- **Depends on:** [ENG-21](#eng-21)

<a id="eng-3"></a>
#### ENG-3 Discover schemas (done)

A relation's schema is its ordered columns, each a name and a type normalized by sqlglot. Repositories may store schemas as SQL DDL, YAML, or JSON; each format has a reader, and every reader returns schemas keyed by relation plus any problems. Start with the DDL reader: every `CREATE TABLE` with a column list in the SQL folder, whichever file it is in. One file can define several relations, and DDL can sit beside DML. Parse in the DDL's own dialect, defaulting to sqlglot's generic dialect, because both DuckDB and sqlglot's DuckDB dialect drop `varchar` lengths. Report, without stopping discovery:

- a statement that cannot be parsed
- a relation defined more than once

YAML and JSON readers come later, in [CFG-2](#cfg-2).

- **Done when:** the sample repository's `members_ddl.sql` yields each of its four relations, with `members` as the following:
  - `member_id INT`
  - `member_name VARCHAR(30)`
  - `lob VARCHAR(2)`
- **Depends on:** none

<a id="eng-22"></a>
#### ENG-22 Catalog from a repository convention (done)

The engine reads a catalog of relations, operations, and schemas, not files. The catalog's relations are everything its operations and schemas mention: a relation written by an operation or given a schema is declared; one only read by SQL is inferred, as a source. A repository adapter builds the catalog from one repository's conventions. The first adapter is the convention the engine already reads: a folder of SQL plus a mapping CSV. The adapter chooses which readers to use for the repository's mapping and schemas, for example the mapping CSV and the DDL reader. A different repository layout is a new adapter, with no change to lineage, the planner, or the test layer. Define *catalog* and *repository adapter* in [HELPER.md](HELPER.md).

- **Done when:**
  - the engine is built from a catalog that the folder-and-mapping adapter produces, and the engine's tests change only in how the engine is constructed
  - in the sample repository, all four relations are declared
  - a relation read by SQL but written by no operation and given no schema is inferred
- **Depends on:**
  - [ENG-2](#eng-2)
  - [ENG-3](#eng-3)

<a id="eng-4"></a>
#### ENG-4 Discover case folders (done)

Part of the test layer. List every `<table under test>/<case name>/` folder under the repository's case location, and its CSV files, without reading their contents.

- **Done when:** discovery returns, for each case:
  - its target
  - its name
  - its mocked table names
  - whether `expected.csv` exists
- **Depends on:** none

### Lineage

<a id="eng-5"></a>
#### ENG-5 Extract table references (done)

For each SQL statement, list the relations it reads, excluding CTE names. Parse with a configurable dialect, defaulting to DuckDB. Keep sqlglot inside the parsing module; other modules see relations, not sqlglot types.

- **Done when:** `medicaid_members.sql` reads `members` and `lob`, `medicaid_members_named_alice.sql` reads `medicaid_members`, and a query with a CTE does not report the CTE as a relation.
- **Depends on:** none

<a id="eng-6"></a>
#### ENG-6 Build upstream lineage (done)

Build the upstream graph of a target relation as relation → operation → relation:

- A relation written by an operation in the catalog is a model, and traversal continues through each of its operations.
- Any other relation is a source, and traversal stops.

The graph can be projected to relation → relation for the default lineage view. Lineage says only what depends on what; what runs is the planner's job.

- **Done when:** the lineage of `medicaid_members_named_alice` is `members` and `lob` (sources) → `medicaid_members.sql` → `medicaid_members` (model) → `medicaid_members_named_alice.sql` → `medicaid_members_named_alice`, and its projection drops the operations.
- **Depends on:**
  - [ENG-2](#eng-2)
  - [ENG-5](#eng-5)

<a id="eng-7"></a>
#### ENG-7 Sources that stop lineage (done)

A model whose SQL cannot be parsed, or that has no schema, is classified as a **source**. Traversal stops there, and the reason is recorded for drill-down.

- **Done when:** a model with unparseable SQL and a model with no schema each appear as a source with the right reason, and their upstream relations are not in the graph.
- **Depends on:**
  - [ENG-6](#eng-6)
  - [ENG-3](#eng-3)

### Planning

<a id="eng-8"></a>
#### ENG-8 Plan a run (done)

Given a target and the relations whose rows are given, return a plan without executing anything. The plan marks each relation in the lineage as one of:

- given
- executed
- pruned
- source

A relation upstream of a given relation is pruned unless another executed path still needs it. The plan can be inspected, for example by the app's lineage view, before or instead of running it. Define *plan* in [HELPER.md](HELPER.md).

- **Done when:** giving `medicaid_members` prunes `members` and `lob` and leaves only the Alice operation to execute, and a diamond-shaped lineage keeps a relation that one path still needs.
- **Depends on:** [ENG-6](#eng-6). Source reasons from unparseable or schemaless models appear once [ENG-7](#eng-7) lands.

<a id="eng-9"></a>
#### ENG-9 Report relations that still need rows (done)

List every relation the plan will read that no executed operation produces and that has no given rows. Running such a plan fails with a message naming them. The test layer words this as tables that still need mock data.

- **Done when:** planning the Alice target with no rows given reports that `members` and `lob` need rows.
- **Depends on:** [ENG-8](#eng-8)

<a id="eng-10"></a>
#### ENG-10 Order executed operations (done)

Order the executed operations so each runs after the relations it reads have been produced. Built ahead of ENG-8: the engine currently runs every mapped SQL upstream of the requested table, stopping at tables whose rows are given and at tables with no SQL. The ordering now lives in the plan.

- **Done when:** the Alice plan runs `medicaid_members.sql` before `medicaid_members_named_alice.sql`, and a cycle is reported as an error.
- **Depends on:** [ENG-8](#eng-8)

### Execution

<a id="eng-11"></a>
#### ENG-11 Executor interface with a DuckDB executor (done)

An executor interface with a DuckDB implementation that uses a fresh in-memory database per run. The interface takes relations and operations, not lineage or cases, and is sized by this first implementation rather than designed for every engine up front. Roughly:

- set up and tear down a run
- create a relation from a schema and rows
- execute an operation
- read a relation

How an operation's kind becomes SQL, for example a full-load `SELECT` becoming a table, is decided per executor. The current `DuckDBBackend` becomes this executor. Spark is added behind the same interface later, in [SPK-2](#spk-2).

- **Done when:** the interface's own tests pass against DuckDB, and two runs do not share relations.
- **Depends on:** none

<a id="eng-12"></a>
#### ENG-12 Load given rows

Create each relation whose rows are given from its discovered schema, and insert the rows. A source relation with no schema takes its columns from the rows; how it is typed is an open question in [HELPER.md](HELPER.md).

- **Done when:** given `members` rows with `member_id` as the string `"1"`, `members` loads with `member_id` as the integer `1`, replacing the sample repository's `test_medicaid_members_types`.
- **Depends on:**
  - [ENG-11](#eng-11)
  - [ENG-3](#eng-3)

<a id="eng-13"></a>
#### ENG-13 Execute a plan

The executor runs a plan's ordered operations against the given rows and returns the target's rows and the row count of every relation in the plan. `Engine.run(table, rows)` becomes planning followed by executing the plan.

- **Done when:** the Alice plan returns `(1, 'Alice')` with row counts for:
  - `members`
  - `lob`
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

Part of the test layer. Compare expected and actual rows using the defaults from ENG-14, and report:

- matching rows
- changed values
- missing expected rows
- unexpected actual rows

- **Done when:** each of the four outcomes has a test.
- **Depends on:** [ENG-14](#eng-14)

### Case format and pytest

<a id="eng-16"></a>
#### ENG-16 Read and write case folders

Read a case folder's CSVs into typed rows using the discovered schemas and the NULL convention, and write rows back out in the same format. The case format is a public contract: other tools and people write cases by hand, so it is documented in [HELPER.md](HELPER.md) with a format version, and changes to it are versioned.

- **Done when:** reading a case and writing it back produces identical files, and the format and its version are written in HELPER.md.
- **Depends on:**
  - [ENG-4](#eng-4)
  - [ENG-3](#eng-3)
  - [ENG-14](#eng-14)

<a id="eng-17"></a>
#### ENG-17 Run a case

The test layer's entry point: take a case folder, give its mocks to the engine as rows, and return the actual rows, the comparison, and pass or fail. The app, pytest, and the CLI all call this.

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

In the sample repository, rewrite the v0 scenarios as case folders and remove the hand-wired tests from its `tests/test_sql.py`. The schemas already exist in `members_ddl.sql`.

- **Done when:** the same scenarios pass through the plugin run against the sample repository, and the hand-wired tests are gone.
- **Depends on:** [ENG-18](#eng-18)

---

## v0.2 — CLI and static validation

A headless command-line interface over the engine, and checks that run without executing SQL.

### Repository config

<a id="cfg-1"></a>
#### CFG-1 Define a repository config file

Define a config file in the consuming repository that says where its SQL, schemas, cases, and SQL-to-table mapping live, so the CLI, app, pytest plugin, and CI can find them without code. Decide its name and format, for example TOML, which Python reads without a new dependency, or YAML, which needs PyYAML. Record the decision in [HELPER.md](HELPER.md).

- **Done when:** a repository's paths can be read from its config file, and the decision is written in HELPER.md.
- **Depends on:**
  - [ENG-20](#eng-20)
  - [ENG-22](#eng-22): the config describes the conventions a repository adapter reads

<a id="cfg-2"></a>
#### CFG-2 YAML and JSON readers

Readers for schemas and SQL-to-table mappings stored as YAML or JSON, returning the same results as the DDL reader and the mapping CSV reader. Types are written as text and normalized by sqlglot, so `varchar(30)` means the same in every format. YAML needs PyYAML; JSON needs nothing new. Build them when a repository needs them.

- **Done when:** a YAML schema and a JSON schema for `members` each yield the same columns as `members_ddl.sql`, and a YAML mapping yields the same operations as the mapping CSV.
- **Depends on:**
  - [ENG-3](#eng-3)
  - [ENG-22](#eng-22)

### CLI

<a id="cli-1"></a>
#### CLI-1 `sql-test discover` (done)

List, for the repository:

- models
- sources
- cases

Built ahead of ENG-2 and ENG-6: models come from the mapping; sources are tables lineage cannot execute through (not produced here, or producer SQL that fails to parse). Full operation and lineage graphs land with those stories.

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
#### APP-1 Decide how the page reaches the repository (done)

Decide how the page reads and writes the checked-out repository, and record it in [HELPER.md](HELPER.md). Options include:

- a local server started by `sql-test app`
- browser folder access

- **Done when:** the decision and its safeguards are written in HELPER.md.
- **Depends on:** none

<a id="app-2"></a>
#### APP-2 App shell (done)

`sql-test app .` opens the page against the current repository and can list what `discover` lists.

- **Done when:** the page shows the repository's models and cases.
- **Depends on:**
  - [APP-1](#app-1)
  - [CLI-1](#cli-1)

### Target browser

<a id="app-3"></a>
#### APP-3 Browse and select a target (done)

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

Tables that still need data are grey and turn colored once they have data. A source shows why it is a source when that is not obvious (for example unparseable SQL).

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

Swap execution to a Spark executor behind the same executor interface, so the app, pytest plugin, and saved cases do not change.

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
- **Undefined-relation checks.** Flag inferred relations with no schema, naming the SQL that reads them, with a did-you-mean against declared relations, and a strict mode with an allowlist of external sources. Mostly the repository's own linting's job; add only if users ask. Depends on [ENG-22](#eng-22).
