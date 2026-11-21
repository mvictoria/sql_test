# Roadmap

Planned versions, the features in each, and the stories that make up each feature. Design decisions behind these are in [HELPER.md](HELPER.md). Architectural direction is in [foss-architecture-thoughts.md](foss-architecture-thoughts.md): specific implementation, general architecture.

Most stories can be done independently. When a story needs another one first, it says so under **Depends on** and links to it. A story with no dependencies can start any time, including ahead of its version. The version order is the planned order, not a hard sequence: for example, the CI workflow in v0.5 only needs v0.1.

All engine code lives in the package created by [ENG-1](#eng-1). That dependency is not repeated on every story.

Nothing assumes where a repository lives. The engine is given a folder of SQL and a mapping, and the test layer is given a repository. `lakehouse-data-customer/` is a sample consuming repository kept in this directory for now. The tool's own tests use small fixture repositories of their own and must not depend on the sample being present.

---

## v0 — Hand-wired tests (done)

pytest tests in the sample repository's `tests/test_sql.py` load rows into DuckDB and run the SQL in `admin/sqls/`. Chained queries are wired by hand inside each test.

---

## v0.1 — Engine core (done)

A headless engine, and a test layer over it, that run a case folder end to end on DuckDB, and that a repository's own pytest tests call to run its case folders. Done when the v0 scenarios run as case folders through the sample repository's pytest tests.

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
- [ENG-12](#eng-12)
- [ENG-13](#eng-13)
- [ENG-14](#eng-14)
- [ENG-16](#eng-16)
- [ENG-15](#eng-15)
- [ENG-17](#eng-17)
- [ENG-18](#eng-18)
- [ENG-19](#eng-19)
- [ENG-25](#eng-25)
- [ENG-26](#eng-26)
- [ENG-24](#eng-24)
- [ENG-27](#eng-27)
- [ENG-28](#eng-28)
- [ENG-29](#eng-29)
- [ENG-33](#eng-33)
- [ENG-31](#eng-31)
- [ENG-34](#eng-34)

Planning performance still open: [ENG-30](#eng-30), [ENG-32](#eng-32), [ENG-36](#eng-36), [COV-5](#cov-5) (measured by [TEST-2](#test-2)).

v0.5 CI is done: [CI-1](#ci-1), [CI-2](#ci-2), [CI-3](#ci-3), [CI-4](#ci-4), [CI-5](#ci-5). Authoring app v0.3 is done ([APP-8](#app-8), [APP-17](#app-17), [APP-19](#app-19), and the earlier APP stories). [APP-25](#app-25) is done. [APP-30](#app-30) is done. [CFG-1](#cfg-1) is done.

**Before the next release** (from [UAT.md](UAT.md)): adoption first — [CI-6](#ci-6), [DOC-1](#doc-1), [CLI-7](#cli-7), [ENG-36](#eng-36), [APP-20](#app-20), [APP-21](#app-21) — then or beside massive-repo perf [ENG-31](#eng-31) and [ENG-32](#eng-32). Workbench navigation track in parallel: [APP-30](#app-30) (done), then [APP-27](#app-27), [APP-26](#app-26), [APP-28](#app-28), [APP-29](#app-29). Keep [APP-18](#app-18) parked until UAT and front-end design say synthetic fill is next. Do not open Spark, incremental, or richer lineage until after the release. Further CLI commands ([CLI-2](#cli-2)–[CLI-6](#cli-6)) stay parked; the CLI's job today is `sql-test app` (plus [CLI-7](#cli-7) when built).

### Project skeleton

<a id="eng-1"></a>
#### ENG-1 Package skeleton (done)

Create the pip-installable `sql_test` package under `src/` with empty `engine/` subpackages for:

- discovery
- lineage
- execution
- comparison

- **Done when:** the package installs in the dev environment and the v0 tests still pass.
- **Depends on:** none

<a id="eng-23"></a>
#### ENG-23 Lay out packages by layer (done)

Replace ENG-1's layout with one package per layer, so dependencies point one way:

- the engine: catalog, lineage, planner
- executors: DuckDB, later Spark
- the test layer: cases, comparison
- integrations: the CLI and app server

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
#### ENG-12 Load given rows (done)

Create each relation whose rows are given from its discovered schema, and insert the rows. A source relation with no schema takes its columns from the rows; how it is typed is an open question in [HELPER.md](HELPER.md).

- **Done when:** given `members` rows with `member_id` as the string `"1"`, `members` loads with `member_id` as the integer `1`, replacing the sample repository's `test_medicaid_members_types`.
- **Depends on:**
  - [ENG-11](#eng-11)
  - [ENG-3](#eng-3)

<a id="eng-13"></a>
#### ENG-13 Execute a plan (done)

The executor runs a plan's ordered operations against the given rows and returns the target's rows. `Engine.run(table, rows)` is planning followed by executing the plan. Row counts per relation moved to [APP-9](#app-9), the first story that shows them.

- **Done when:** the Alice plan returns `(1, 'Alice')`.
- **Depends on:**
  - [ENG-10](#eng-10)
  - [ENG-12](#eng-12)

<a id="eng-24"></a>
#### ENG-24 Engine cleanup (done)

Behaviour-preserving cleanup of the engine, one commit per item:

- [x] One run path: `run`, `run_rows`, and `run_result` share a single load-and-execute step.
- [x] One run method: `Engine.run` returns a `RunResult` with the target's rows, row counts, and whether the target's SQL orders its rows. `run_rows` and `run_result` are gone, and `run_case` no longer parses SQL.
- [x] Front doors: `sql_test.engine`, `sql_test.executors`, and `sql_test.testing` export what other layers use; `tests/test_layers.py` checks that the test layer and integrations import through them ([APP-15](#app-15) dropped the app exemption). `discover()` reads models and sources from the catalog instead of parsing SQL itself.
- [x] Front doors export only names used outside their layer: `sql_test.engine` (including `Executor`) and `sql_test.testing`. Executors import only `sql_test.engine.executor`.
- [x] The executor interface reads rows one way: `read_rows`.
- [x] The executor interface is one call, `run(given, operations)`, which owns the whole lifecycle and returns the rows of every given and written relation. `Engine` takes an executor instance; `setup`, `create_relation`, `execute`, `read_rows`, `teardown`, and `read_relation` are gone.
- [x] The catalog answers lookups itself: `resolve(name)`, `schema(relation)`, and `producers(relation)` replace the `Relation.parse(...).resolve(catalog.relations().keys())` and `catalog.schemas.get(...)` pairs in the engine, the test layer, and the app. `relations()` is a set; `Evidence` is gone. `read_case` takes the catalog. `Engine.plan` resolves given names the same way `run` does.
- [x] A flat plan: `Plan` carries `target`, `states`, `built_from`, `source_reasons`, `needs_rows`, `unused`, and the engine's `operations`, instead of a nested `Lineage` that callers reached through. `check_rows` is gone; `Engine.run` raises `MissingRows` itself. The lineage's projection is computed once per plan.
- [x] `Engine.execute(plan, rows)` runs a plan without planning again; `run` is `plan` then `execute`. `run_case` plans once, checks unused, then executes.

- **Done when:** each item's commit lands with the existing tests passing unchanged.
- **Depends on:** none

<a id="eng-25"></a>
#### ENG-25 Report unused mocks (done)

The plan lists the given relations the run never reads, as `Plan.unused`: a mock upstream of another mock on every path to the target, or a mock outside the target's lineage. A mock that another path still reads is used. The app's mock frontier and the test layer both read this instead of working it out themselves. A case with an unused mock fails, naming it.

- **Done when:** given `medicaid_members` and `members` for `medicaid_members_named_alice`, the plan's unused relations are `{members}`; in a diamond where another path still reads the upstream mock, nothing is unused; and a case folder with a mock outside the target's lineage fails naming it.
- **Depends on:** [ENG-10](#eng-10)

<a id="eng-26"></a>
#### ENG-26 Parse each SQL once (done)

Planning a run parsed every SQL file in the repository once per name it resolved, so a plan at 200 files took most of a second. Parsing is memoized on the SQL text, so an unchanged file is parsed once per process and an edited file is parsed again the next time it is read, with no invalidation step. DDL files are memoized the same way. A catalog is a frozen snapshot that works out its relations once; a long-running caller such as the app sees edits by building a new catalog.

- **Done when:** resolving several names in one catalog parses each SQL once; a second catalog over the same unchanged files parses nothing; and a catalog built after a SQL file is edited sees the new tables it reads.
- **Depends on:** [ENG-24](#eng-24)

<a id="eng-33"></a>
#### ENG-33 Parse only DDL in the DDL reader (done)

The DDL reader reads every file in the schemas folder, which is often the SQL folder. It parsed every statement in them only to keep the `CREATE TABLE`s, so on a cold start each model's SQL was parsed twice: once by the DDL reader, then by lineage. It now parses only statements that begin with `CREATE`, and skips a file that never mentions `create` without splitting it. Measured on generated repositories with one DDL file per table, median of 3–5 fresh processes:

| Models (files) | Cold catalog build | Full `pytest` run |
| --- | --- | --- |
| 300 (601) | 1.12 s → 0.75 s | 2.53 s → 2.04 s |
| 1,000 (2,001) | 2.82 s → 2.10 s | 4.32 s → 3.19 s |
| 3,000 (6,001) | 7.79 s → 5.68 s | 12.64 s → 7.48 s |

A rebuild after a one-file edit is unchanged, because it already parsed only the edited file.

The saving applies once per process, on the first catalog build: once per local `pytest` run, once per CI job (once per pytest-xdist worker, in parallel), and once per app start. After a branch switch it applies to the files that changed. It does not make each case faster; per-case cost is planning and execution ([ENG-31](#eng-31), [ENG-32](#eng-32)).

- **Done when:** a first catalog over a SQL folder that holds both DDL and model SQL parses each model's SQL once.
- **Depends on:** [ENG-26](#eng-26)

<a id="eng-27"></a>
#### ENG-27 Share one DuckDB instance across runs (done)

Each run opened and closed its own DuckDB database, which cost more than the run itself: a sample-repository case took 58 ms, most of it opening the database. The DuckDB executor keeps one instance; each run attaches its own in-memory database through its own cursor and detaches it at the end, even when the run fails.

- **Done when:** concurrent runs on one executor each see only their own rows; a failed run leaves nothing a later run can read; and two runs still do not share relations.
- **Depends on:** [ENG-24](#eng-24)

<a id="eng-28"></a>
#### ENG-28 Run three-level names on DuckDB (done)

Gap: the catalog handles `catalog.schema.table` names ([ENG-21](#eng-21)), but the DuckDB executor never creates the catalog part, so a mock or model named `lakehouse.claims.members` fails with `Catalog Error: Schema with name lakehouse does not exist!`. [ENG-21](#eng-21) left this to the executor and no story picked it up. In DuckDB the catalog part is an attached database, and attached names are global to an instance, so two concurrent runs on the shared instance from [ENG-27](#eng-27) cannot both attach `lakehouse`. A run with any three-level relation uses a throwaway DuckDB instance that attaches each catalog under its own name; one- and two-level runs keep the shared instance. DuckDB's own database names, `memory`, `system`, and `temp`, are reserved: a relation using one as its catalog is an error rather than a table in the shared instance.

- **Done when:** a mock named `lakehouse.claims.members` loads and reads back; SQL reading `lakehouse.claims.members` and writing `lakehouse.claims.out` runs; concurrent three-level runs on one executor each see only their own rows; and a relation in catalog `memory` is an error naming it.
- **Depends on:** [ENG-21](#eng-21), [ENG-27](#eng-27)

<a id="eng-29"></a>
#### ENG-29 Look up relations and producers by index (done)

Resolving a name compared it with every relation in the catalog, and finding a relation's producers scanned every operation, so planning a chain of n tables did about n² comparisons: 5,202 for 50 tables. A frozen catalog now keeps two indexes, built once: relations by name, since a reference can only match relations of its name, and operations by the relation they write. Lineage and coverage resolve names through the catalog instead of against the whole relation set. `Relation.parse` is memoized on the name text.

- **Done when:** resolving a name compares it only with relations of that name; planning a 50-table chain makes fewer than 250 relation comparisons; and parsing the same name twice parses it once.
- **Depends on:** [ENG-26](#eng-26)

<a id="eng-30"></a>
#### ENG-30 Memoize upstream lineage by target

`plan_run` rebuilds the target's full upstream lineage on every call, even when `given` is ignored by the walk and many cases share a target. On [TEST-2](#test-2)'s 1000 models × 100 cases, almost all of the ~8s is 100k identical-shaped `plan_run`s. While the walk still ignores givens ([ENG-31](#eng-31)), cache `upstream_lineage` per catalog by target so a second plan for the same target reuses the lineage. A new catalog ([APP-17](#app-17)) starts empty. After [ENG-31](#eng-31), revisit the cache key — truncated walks depend on the given frontier.

- **Done when:** two `plan_run`s for the same target on one catalog walk lineage once; [TEST-2](#test-2)'s `pipeline_counts` phase drops by roughly the cases-per-model factor when targets repeat; and a second catalog over edited SQL sees the new lineage.
- **Depends on:** [ENG-6](#eng-6), [ENG-29](#eng-29)

<a id="eng-31"></a>
#### ENG-31 Stop the plan's lineage walk at given relations (done)

Planning a run walks the target's whole upstream lineage, then prunes everything above the given relations. A case usually mocks the target's direct inputs and executes one SQL, but its plan still visits every table above them. On a 1,000-table chain with 2,000 case folders, a case took 55 ms for tables with about 100 upstream tables and 146 ms for tables with about 950, and planning was about 80% of that. The plan's walk stops at a relation the run is given rows for, so planning costs the same however deep the table sits. Unused mocks keep their meaning: a mock above another mock, or outside the lineage, is never reached and is reported as unused. A relation that another path still reads is still reached. The app's lineage view keeps the full walk, so it can show pruned tables.

Measured on the same 1,000-table chain with 2,000 case folders, this PC (4 cores): a case at the bottom of the chain (about 100 upstream tables) takes about 18–20 ms before and after. A case at the top (about 950) went from about 55 ms to 18 ms. The whole serial pytest run went from 89–112 s to 52–59 s. Coverage, which plans every saved case for the app's home page, went from 43–53 s to 0.2–0.3 s over the 2,000 cases.

- **Done when:** planning a case that mocks its target's direct inputs reads no SQL above those inputs; the plan for the top of a 1,000-table chain with its input mocked visits two relations; a mock above another mock is still unused; and in a diamond where another path still reads an upstream mock, nothing is unused.
- **Depends on:** [ENG-10](#eng-10), [ENG-29](#eng-29)

<a id="eng-32"></a>
#### ENG-32 Read each SQL file once per catalog

`Operation.sql` reads its file from disk every time it is asked, so planning the 1,000 cases in the [ENG-31](#eng-31) measurement read about 950 files per case. A catalog is a frozen snapshot, so it reads each mapped SQL file once and keeps the text. A long-running caller still sees edits, because it builds a new catalog ([APP-17](#app-17)).

- **Done when:** planning several runs from one catalog reads each SQL file once; and a catalog built after a SQL file is edited sees the new text.
- **Depends on:** [ENG-26](#eng-26), [APP-17](#app-17)

<a id="eng-34"></a>
#### ENG-34 Parse each column type once when typing cells (done)

Typing a case CSV cell with its column's type parsed the type name with sqlglot every time, for every cell of every mock and expected file. That cost 43–113 µs per cell and made reading a case's CSVs cost more than running its SQL. Each type name is now parsed once per process, and typing a cell takes under 1 µs. Measured on a case whose two mocks and expected file each have 10 columns of mixed types, median of 7–25 runs:

| Rows per file | Per case |
| --- | --- |
| 4 | 48.5 ms → 26.5 ms |
| 100 | 728 ms → 441 ms |
| 1,000 | 7.41 s → 3.86 s |

The saving applies to every case, on every run. What remains is almost all loading mocks into DuckDB ([ENG-35](#eng-35)).

- **Done when:** typing 1,000 cells of one column parses its type at most once.
- **Depends on:** [ENG-14](#eng-14)

<a id="eng-35"></a>
#### ENG-35 Load each mock in one insert

The DuckDB executor loads a mock with `executemany`, which runs one `INSERT` per row. In the [ENG-34](#eng-34) measurement, after that fix, this was 96% of a case with 100-row mocks: about 207 ms per mock. A single multi-row `INSERT` loads the same rows two to three and a half times faster in a micro-benchmark.

- **Done when:** loading a mock of many rows runs one insert; and a 100-row mock of 10 columns loads at least twice as fast as with `executemany`.
- **Depends on:** [ENG-27](#eng-27)

<a id="eng-36"></a>
#### ENG-36 Reuse a plan for the same target and givens

Callers that plan many cases (coverage, batch runs) repeat `plan_run` for the same target and given frontier. Cache the plan per catalog keyed by target, which relations are given, and which of those have zero rows (`needs_rows` / empty mocks). Distinct from [ENG-30](#eng-30) (lineage only) and from [COV-5](#cov-5) (coverage-only dedupe): this helps every `plan_run` caller. Invalidate with the catalog.

- **Done when:** two `plan_run`s with the same target and given row-count map return the same plan without walking lineage again; a given with zero rows still appears in `needs_rows`; and [TEST-2](#test-2) stays under a tighter budget once this lands (record the new numbers in the story or the test).
- **Depends on:** [ENG-8](#eng-8), [ENG-30](#eng-30)

### Comparison

<a id="eng-14"></a>
#### ENG-14 Decide comparison defaults (done)

Decide:

- row ordering
- duplicate handling
- the CSV convention for NULL
- whether `expected.csv` must list every column or only some

Record the decisions in [HELPER.md](HELPER.md). These must be settled before cases are committed, because changing them later means migrating every case.

- **Done when:** the decisions are written in HELPER.md.
- **Depends on:** none

<a id="eng-15"></a>
#### ENG-15 Compare expected and actual (done)

Part of the test layer. Compare expected and actual rows using the defaults from ENG-14, and report:

- matching rows
- changed values
- missing expected rows
- unexpected actual rows

- **Done when:** each of the four outcomes has a test.
- **Depends on:** [ENG-14](#eng-14)

### Case format and pytest

<a id="eng-16"></a>
#### ENG-16 Read and write case folders (done)

Read a case folder's CSVs into typed rows using the discovered schemas and the NULL convention, and write rows back out in the same format. The case format is a public contract: other tools and people write cases by hand, so it is documented in [HELPER.md](HELPER.md) with a format version, and changes to it are versioned.

- **Done when:** reading a case and writing it back produces identical files, and the format and its version are written in HELPER.md.
- **Depends on:**
  - [ENG-4](#eng-4)
  - [ENG-3](#eng-3)
  - [ENG-14](#eng-14)

<a id="eng-17"></a>
#### ENG-17 Run a case (done)

The test layer's entry point: take a case folder, give its mocks to the engine as rows, and return the actual rows, the comparison, and pass or fail. The app, pytest, and the CLI all call this.

- **Done when:** a passing and a failing case folder return the right result.
- **Depends on:**
  - [ENG-13](#eng-13)
  - [ENG-15](#eng-15)
  - [ENG-16](#eng-16)

<a id="eng-18"></a>
#### ENG-18 Run case folders from a repository's pytest tests (done)

A repository's own pytest tests import the test layer and run its case folders, one parametrized test per case. The repository says where its case folders live; the library takes a path. A failure shows the comparison or the tables that still need data.

```python
@pytest.mark.parametrize("case", case_folders(CASES), ids=case_id)
def test_case(case, engine):
    result = run_case(case, engine)
    assert result.passed, result.report()
```

- **Done when:** a parametrized test over `case_folders(root)` runs one test per case folder, named `<table under test>/<case name>`, for any `root`.
- **Depends on:**
  - [ENG-17](#eng-17)
  - [ENG-9](#eng-9)
  - [ENG-20](#eng-20)

<a id="eng-19"></a>
#### ENG-19 Port the v0 tests (done)

In the sample repository, show both ways a repository's pytest tests use the library:

- `tests/test_sql.py` imports the engine and passes rows inline in Python.
- `tests/test_cases.py` runs one parametrized test per case folder under `tests/cases/`.

- **Done when:** the v0 scenarios pass both ways in the sample repository.
- **Depends on:** [ENG-18](#eng-18)

---

## v0.2 — CLI and static validation

The CLI starts the authoring app (`sql-test app [repository] [--port]`). pytest remains the test runner. Extra commands and static validation below are parked until something needs them (for example a pre-commit hook).

### Repository config

<a id="cfg-1"></a>
#### CFG-1 Define a repository config file (done)

Define a config file in the consuming repository that says where its SQL, schemas, cases, and SQL-to-table mapping live, so the CLI, app, and CI can find them without code. Decide its name and format, for example TOML, which Python reads without a new dependency, or YAML, which needs PyYAML. Record the decision in [HELPER.md](HELPER.md).

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
#### CLI-2 `sql-test run` (parked)

Run one case, several cases, or all of them, and print each result and comparison. Parked: pytest already runs cases.

- **Done when:** a failing case prints the same comparison pytest shows.
- **Depends on:** [ENG-17](#eng-17)

### Static validation (parked)

Parked until a hook or other consumer needs static checks without executing SQL.

<a id="cli-3"></a>
#### CLI-3 Check case structure (parked)

Check that:

- the case folder parses
- its target table exists
- its mocked tables exist

- **Done when:** a misspelled target or mock is reported by name.
- **Depends on:**
  - [ENG-16](#eng-16)
  - [ENG-2](#eng-2)

<a id="cli-4"></a>
#### CLI-4 Check a case against lineage (parked)

Check that:

- mocked tables are upstream of the target
- no table still needs data

- **Done when:** a mock that is not upstream of the target, and a missing source, are each reported.
- **Depends on:**
  - [ENG-8](#eng-8)
  - [ENG-9](#eng-9)

<a id="cli-5"></a>
#### CLI-5 Check CSVs against schemas (parked)

Check that:

- CSV columns match the known schema
- every value parses to its column's type

- **Done when:** an unknown column and a non-integer `member_id` are each reported.
- **Depends on:** [ENG-16](#eng-16)

<a id="cli-6"></a>
#### CLI-6 `sql-test validate` (parked)

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

<a id="app-14"></a>
#### APP-14 Edit the repository config (done)

Done so far: the app reads its paths from `RepositoryConfig`, and the `SQLS` and `MAPPING` constants are gone. A settings page shows the repository's `[tool.sql-test]` paths and lets QA change them. Each path is checked before saving: it exists, and with the new paths the catalog still discovers SQL, the mapping, and schemas. Saving writes only the `[tool.sql-test]` table and leaves the rest of `pyproject.toml`, including comments, unchanged. Writing uses [tomlkit](https://github.com/python-poetry/tomlkit); the choice is recorded in [HELPER.md](HELPER.md). A repository with no config opens this page to create one, instead of `sql-test app` exiting with the config error.

- **Done when:** changing `cases` in the app updates `pyproject.toml` with the rest of the file byte-for-byte unchanged, and the page then lists the cases from the new folder.
- **Depends on:**
  - [CFG-1](#cfg-1)
  - [APP-2](#app-2)

<a id="app-15"></a>
#### APP-15 Use the layers' front doors (done)

The app imports engine, executor, and test-layer names from `sql_test.engine`, `sql_test.executors`, and `sql_test.testing`, not from their modules, and drops the `app` exemption from `tests/test_layers.py`. The grid and the compare view type rows with `Column.cast` instead of loading them through `DuckDBExecutor().run`. Also:

- [x] `frontier_mocks` reads `Plan.unused` from [ENG-25](#eng-25) instead of walking the lineage itself, so a mock another path still reads is kept. The SQL view reads `catalog.operations` instead of re-reading the mapping.
- [x] The compare view passes `ordered=result.ordered`, so an ORDER BY target compares in order in the app as it does in pytest.
- [x] A request builds the catalog once instead of once per helper.
- [x] The CLI (or test) hands the app one executor via `register_app` / `serve`; app modules do not construct `DuckDBExecutor`, so [ENG-27](#eng-27)'s shared DuckDB instance is reused across plan and run.

- **Done when:** `tests/test_layers.py` checks the app with no exemption, and no app module creates an executor.
- **Depends on:** [ENG-24](#eng-24)

<a id="app-16"></a>
#### APP-16 Replace authoring UI with NiceGUI (done)

The authoring app is built with [NiceGUI](https://nicegui.io) instead of a stdlib HTTP server and hand-written HTML strings. `register_app(repository)` registers the home and workbench pages; `serve` still binds to localhost only and then calls `ui.run`. The workbench keeps its state (mocks, grid rows, result) in one object and rebuilds its views on each action, instead of posting a form and re-rendering the whole page. The pure helpers (case load and save, engine access, `frontier_mocks`, grid typing, compare) stay free of UI code. Tests use NiceGUI's `User` fixture.

- **Done when:** the existing app behaviors pass as NiceGUI `User` tests in `tests/test_app.py`; the stdlib router, HTTP server, and HTML builders are gone; `sql-test app` still binds to localhost only.
- **Depends on:**
  - [APP-2](#app-2)
  - the shipped APP stories: [APP-3](#app-3), [APP-4](#app-4), [APP-5](#app-5), [APP-6](#app-6), [APP-9](#app-9), [APP-10](#app-10), [APP-12](#app-12), [APP-13](#app-13)

<a id="app-17"></a>
#### APP-17 Rebuild the catalog when SQL files change (done)

While `sql-test app` is running, a SQL file under the repository's configured paths may be added, modified, or deleted outside the app. The next request discards the old catalog and builds a new immutable one from the checkout, so home, lineage, and SQL views match. The mapping file is watched the same way. Catalogs stay snapshots ([ENG-26](#eng-26)); there is no in-place patch of operations or indexes.

Do not assume the rebuild is free. Pressure-test a representative repository (on the order of hundreds of SQL files): after one file changes, rebuilding the catalog with memoized parse must stay fast enough for interactive use. If it is not, revisit incremental update then — not before.

Measured on generated repositories with one DDL file per table: one workbench action builds the catalog, discovers, and plans lineage. After a one-file edit this takes 112 ms for 300 models (601 files), 264 ms for 1,000 models (2,001 files), and 965 ms for 3,000 models (6,001 files). That's acceptable, so the story stays closed. Before the fix, the DDL cache's 1,024-entry limit meant 1,000 models took 2.7 s even with no file changed.

- **Done when:** editing a mapped SQL's upstream tables updates lineage on the next request; adding a mapped SQL shows the new model; deleting a mapped SQL removes it; and a rebuild after a one-file change on a large fixture repo is timed and recorded as acceptable for the app, or the story is reopened for incremental update.
- **Depends on:**
  - [APP-16](#app-16)
  - [ENG-26](#eng-26)

### Target browser

<a id="app-3"></a>
#### APP-3 Browse and select a target (done)

Search or browse tables, select one as the table under test, or select an existing case.

- **Done when:** selecting a table or a case opens it in the workbench.
- **Depends on:** [APP-2](#app-2)

### Lineage view

<a id="app-4"></a>
#### APP-4 Show lineage with states (done)

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
#### APP-5 Mock and unmock from the graph (done)

Click a table to mock or unmock it. The graph redraws with the new states.

- **Done when:** mocking `medicaid_members` shows `members` as pruned.
- **Depends on:** [APP-4](#app-4)

### Mock editor

<a id="app-6"></a>
#### APP-6 Schema-aware grid (done)

Edit a mocked table's rows in a grid with columns from its schema. Add and delete rows.

- **Done when:** rows entered for `members` reach the engine with the right types.
- **Depends on:**
  - [APP-3](#app-3)
  - [ENG-3](#eng-3)

<a id="app-7"></a>
#### APP-7 Duplicate rows, NULL, and type validation (done)

In the grid:

- duplicate a row
- enter NULL distinctly from an empty string
- flag values that do not fit the column's type

- **Done when:** a non-integer `member_id` is flagged before running.
- **Depends on:** [APP-6](#app-6)

<a id="app-8"></a>
#### APP-8 Paste from a spreadsheet (done)

Paste tabular data copied from Excel or Sheets into the grid, with a reminder that fixtures must be synthetic and must not contain real member data.

- **Done when:** pasting several rows and columns fills the grid.
- **Depends on:** [APP-6](#app-6)

<a id="app-19"></a>
#### APP-19 Tab order follows cells in the mock grid (done)

Typing mock rows is awkward today because Tab leaves the cell and lands on row actions (duplicate, delete, and similar) beside the grid. Tab and Shift+Tab should move only between data cells, left to right then to the next row, the way a spreadsheet does. When focus is on the last cell of a row, Tab adds a new empty row (same shape as Add row) and moves into its first cell. Shift+Tab from the first cell of a row moves to the last cell of the previous row when there is one; it does not delete rows.

- **Done when:** Tab never focuses a row-action control while editing cells; Tab from the last cell of a row creates a new row and focuses its first cell; Shift+Tab walks cells in reverse without leaving the grid for row actions.
- **Depends on:** [APP-6](#app-6)

<a id="app-18"></a>
#### APP-18 Seeded Faker fill on the mock grid (parked)

Speed up mock authoring so QA can generate a case quickly without inventing every cell or pasting real data:

1. Mock the frontier as today.
2. On a mocked table's grid, generate N synthetic rows from the schema (column types and light name hints such as `*_name` or `*_id`), with a visible seed so the same seed reproduces the same rows.
3. Edit any cells by hand if needed.
4. Run the pipeline, review output, accept or adjust expected ([APP-11](#app-11)).
5. Save the case ([APP-12](#app-12)). Pytest runs the saved CSVs and does not depend on Faker.

Faker is an optional dependency of the authoring app only. It does not write `expected.csv` by itself (run + accept keeps expected intentional). It does not invent join keys across tables; related multi-table generate is out of scope until QA outgrows single-table fill. Same synthetic-data reminder as paste ([APP-8](#app-8)). Separate from [TEST-1](#test-1) (Hypothesis tests the engine; Faker helps QA fill grids).

- **Done when:** from an empty `members` grid, generating 5 rows fills schema-typed synthetic values; regenerating with the same seed yields the same rows; QA can edit, run, accept expected, and save; a case saved that way passes under pytest without importing Faker.
- **Depends on:**
  - [APP-6](#app-6)
  - [APP-9](#app-9)
  - [APP-11](#app-11)
  - [APP-12](#app-12)
- **Parked until:** UAT and front-end design work make mock entry easier overall ([UAT.md](UAT.md)); only then decide whether seeded Faker fill is the right next control (hand entry, Tab order, and paste may already be enough).

### Navigation and focus (workbench UX)

Fewer hops between “pick a table,” “open a case,” “fill mocks,” “read SQL,” and “run / fix expected.” IDs start at APP-26 so they do not collide with UAT adoption stories APP-20–APP-21. [APP-25](#app-25) (fold Apply into Run) is done. Build order: [APP-30](#app-30) → [APP-27](#app-27) → [APP-26](#app-26) → [APP-28](#app-28) / [APP-29](#app-29).

<a id="app-26"></a>
#### APP-26 Cases belong to their table

A case is always for one table under test. Home should not make QA hunt a flat Cases list separately from the table it belongs to. Opening a table for a new case must still show that table's existing cases so opening one is one click from the same place — not back through home.

- **Done when:** on home, cases for `medicaid_members_named_alice` appear with that table (not only in a disconnected global list); opening the table in the workbench lists those cases and choosing one loads it ([APP-13](#app-13)).
- **Depends on:**
  - [APP-3](#app-3)
  - [APP-13](#app-13)

<a id="app-27"></a>
#### APP-27 Keep run, compare, and expected edit in one focus

After Run, the verdict, diff / accept, and enough of Expected to fix a failure should stay in one working region. Today result sits above a long editor and Save/Run sit at the bottom, so the fail → fix → re-run loop is mostly scrolling. Primary actions (Run, Save) stay reachable while that region is in view — sticky bar or equivalent.

- **Done when:** after a failing Alice run, QA can accept or edit expected and see the comparison update without scrolling away from the result region to find Expected or primary actions; Run and Save remain reachable from that region.
- **Depends on:**
  - [APP-10](#app-10)
  - [APP-11](#app-11)
  - [APP-25](#app-25)

<a id="app-28"></a>
#### APP-28 Spreadsheet-like grid without per-cell NULL chrome

Mock and expected grids should read as tables of values. A NULL control must not sit inside every cell beside the input. NULL stays distinct from empty string ([HELPER.md](HELPER.md)); the affordance can be keyboard, a selected-cell action, clear-to-null, or another pattern — pick one that keeps Tab and paste ([APP-19](#app-19), [APP-8](#app-8)) intact.

- **Done when:** the `members` grid shows typed values without a NULL button inside each cell; QA can still set and clear NULL distinctly from an empty string; Tab order and spreadsheet paste still behave as in [APP-19](#app-19) and [APP-8](#app-8).
- **Depends on:**
  - [APP-7](#app-7)
  - [APP-8](#app-8)
  - [APP-19](#app-19)

<a id="app-29"></a>
#### APP-29 See a node's SQL without leaving lineage

The Lineage / SQL toggle replaces the whole body, so checking what a step does costs a round-trip and drops the graph. Keep the lineage view; show that relation's producer SQL beside or under the graph (side panel or strip) when QA selects the node or an explicit SQL control on it. A full-pipeline SQL page is optional secondary; it must not be the only way to read one node's SQL.

- **Done when:** from the Alice lineage graph, opening `medicaid_members` SQL shows its statement while the graph remains visible; dismissing or collapsing that SQL returns to graph-only without a tab that destroys lineage context.
- **Depends on:**
  - [APP-4](#app-4)

<a id="app-30"></a>
#### APP-30 Jump from blocked or mocked node to its grid (done)

Mocking a node (or reading “Blocked — still need rows: lob, members”) still leaves QA to scroll and find that table's editor. Clicking a mocked or needs-rows name — in the blocked status, the mocks summary, or the lineage node after mock — scrolls or focuses that table's grid so decide and edit are one gesture.

- **Done when:** with Alice blocked on `members`, activating `members` from the blocked status (or the mocked node) brings the `members` grid into view and focus; mocking a new frontier table lands on its grid the same way.
- **Depends on:**
  - [APP-5](#app-5)
  - [APP-6](#app-6)

### Run and compare

<a id="app-9"></a>
#### APP-9 Run and show the output (done)

Run the case from the page and show the target's rows, with row counts on each table in the graph. The engine returns the row count of every relation in the plan alongside the target's rows, so an empty result shows where the rows were lost.

- **Done when:** running the Alice case shows one row and row counts for `members`, `lob`, `medicaid_members`, and the target.
- **Depends on:**
  - [APP-5](#app-5)
  - [APP-6](#app-6)
  - [ENG-17](#eng-17)

<a id="app-25"></a>
#### APP-25 Fold Apply into Run (done)

“Apply to engine” is a ritual click beside Run. Run already types mocks and executes; Apply only previews schema types. Typing and engine types happen as part of Run (and optionally when the grid needs types), so Apply is not required on the happy path. If a type-preview control remains, it is secondary — not a peer of Run/Save.

- **Done when:** the Alice case reaches Passed with Run (and Save) only — never clicking Apply; column engine types still appear after a successful Run (or an equivalent non-blocking preview); the primary action row is Run and Save, not Apply / Run / Save as three equal peers.
- **Depends on:**
  - [APP-6](#app-6)
  - [APP-9](#app-9)

<a id="app-10"></a>
#### APP-10 Expected and actual side by side (done)

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
#### APP-11 Accept actual as expected (done)

In the expected/actual view:

- accept an actual cell as expected
- accept an actual row as expected
- accept the whole actual result as expected
- remove an obsolete expected row

Accepting rewrites the Expected grid and compares it again with the run on screen, without running the engine again. Saving the case writes it to `expected.csv`.

- **Done when:** accepting the whole actual result makes the case pass.
- **Depends on:** [APP-10](#app-10)

### Save and load

<a id="app-12"></a>
#### APP-12 Save a case (done)

Write the case folder into the working tree. Nothing is committed.

- **Done when:** a case saved from the page passes through pytest without the app running, and loading that case then saving again changes no files.
- **Depends on:**
  - [APP-6](#app-6)
  - [APP-13](#app-13)
  - [ENG-16](#eng-16)
  - [ENG-18](#eng-18)

<a id="app-13"></a>
#### APP-13 Load a case (done)

Open an existing case folder in the same workbench used to create cases, with its mocks set in the graph and its rows in the grids (including expected when present).

- **Done when:** opening a discovered case shows its mocks on the graph and its CSV rows in the grids.
- **Depends on:**
  - [APP-3](#app-3)
  - [ENG-16](#eng-16)
  - [APP-10](#app-10)

---

## v0.4 — Discovery and coverage

Per-table test counts, and a separate count of tests whose pipeline runs a table. Coverage is always derived from the current checkout, never stored.

<a id="cov-1"></a>
#### COV-1 Test counts per table (done)

Count the cases that target each table.

- **Done when:** each table reports its number of cases, including zero.
- **Depends on:** [ENG-4](#eng-4)

<a id="cov-2"></a>
#### COV-2 In-pipeline counts per table (done)

For each table, count the other cases whose plan executes its SQL, using lineage with each case's mocks applied. No SQL is run.

- **Done when:** with only the Alice case, `medicaid_members` reports zero tests and one in a pipeline.
- **Depends on:**
  - [ENG-8](#eng-8)
  - [ENG-16](#eng-16)

<a id="cov-3"></a>
#### COV-3 `sql-test coverage` (done)

Print tests and in-pipeline counts per table, untested tables first. The CLI and the app home both call `coverage_report` from the test layer (built on [COV-1](#cov-1) and [COV-2](#cov-2)).

- **Done when:** the report lists untested tables before tested ones.
- **Depends on:**
  - [COV-1](#cov-1)
  - [COV-2](#cov-2)
  - [CLI-1](#cli-1)

<a id="cov-4"></a>
#### COV-4 Coverage in the target browser (done)

Show TESTS and IN PIPELINES next to each table. Selecting the in-pipeline count lists those cases, and selecting one opens it.

- **Done when:** a table with zero tests and one pipeline case can be opened from the browser.
- **Depends on:**
  - [COV-1](#cov-1)
  - [COV-2](#cov-2)
  - [APP-3](#app-3)
  - [APP-13](#app-13)

<a id="cov-5"></a>
#### COV-5 Deduplicate coverage planning by case shape

`pipeline_counts` and `pipeline_cases` call `plan_run` once per case. Many cases share a target and the same mock set, so the plan is identical. Group by `(target, frozenset(mocks))` before planning, and reuse that plan for every case in the group. Cheap coverage-only win; [ENG-36](#eng-36) is the engine-wide form. Enough alone to collapse [TEST-2](#test-2)'s 100k plans to 1,000 on independent models.

- **Done when:** `pipeline_counts` over 100 identical cases for one target plans once; [TEST-2](#test-2)'s `pipeline_counts` phase scales with distinct `(target, mocks)` pairs, not with case count; and in-pipeline counts match the pre-dedupe behaviour.
- **Depends on:** [COV-2](#cov-2)

---

## v0.5 — CI (done)

Consuming repositories run their cases in GitHub Actions with a few lines of setup. This only needs v0.1 and can be pulled earlier.

Done:

- [CI-1](#ci-1)
- [CI-2](#ci-2)
- [CI-3](#ci-3)
- [CI-4](#ci-4)
- [CI-5](#ci-5)

<a id="ci-1"></a>
#### CI-1 Reusable GitHub Actions workflow (done)

A workflow in this repository that:

1. checks out the calling repository
2. sets up Python
3. installs the package from the workflow's git SHA
4. runs pytest

- **Done when:** a test repository calling the workflow runs its cases in CI.
- **Depends on:** [ENG-18](#eng-18)

<a id="ci-2"></a>
#### CI-2 Versioned releases (done)

Release the package and workflow together under tags such as `v0`, so consuming repositories pin a tag instead of `main`. Local installs use the same tags via `uv` and a git URL. A PR title that starts with `(major)`, `(minor)`, or `(patch)` tags the post-merge `main` tip; `cd.yml` then builds and publishes.

- **Done when:** a consuming repository pinned to a tag is unaffected by a change on `main`.
- **Depends on:** [CI-1](#ci-1)

<a id="ci-3"></a>
#### CI-3 Adoption guide (done)

Document the minimal footprint of a consuming repository:

- SQL
- schemas
- cases
- optional config
- the workflow caller

- **Done when:** someone can set up a new repository from the guide alone.
- **Depends on:** [CI-1](#ci-1)

<a id="ci-4"></a>
#### CI-4 Python version matrix (done)

Support Python 3.13 through 3.15. CI runs the suite on each version; lint and type checks run once on 3.15. The package floor is `requires-python = ">=3.13"` so case CSVs can keep stdlib `csv.QUOTE_NOTNULL` (NULL vs empty string is wrong on 3.12). Keep `uv.lock` for this repository's install.

- **Done when:** tool CI matrices 3.13–3.15 and the package installs on 3.13+.
- **Depends on:** [CI-1](#ci-1)

<a id="ci-5"></a>
#### CI-5 Tool CI on pull requests only (done)

Run the tool's CI workflow on pull requests only, not on pushes to `main`. Skip the run when the PR only changes Markdown. Releases still run via CD on `main`.

- **Done when:** merging to `main` does not start the tool CI workflow, and a Markdown-only PR does not start it either.
- **Depends on:** [CI-1](#ci-1)

---

## Pre-release — adoption (from UAT)

Findings and method: [UAT.md](UAT.md). Happy path after install is strong; getting a stranger to that path is not. Do this before opening v0.6+. Massive-repo planning cost is a parallel track: [ENG-31](#eng-31), [ENG-32](#eng-32).

<a id="ci-6"></a>
#### CI-6 Floating adopt tag and pins

[UAT.md](UAT.md) #1 and #5: documented `git+…@v0` and the sample workflow pin `@v0` failed because no floating major tag existed. Ship (or keep current) a floating adopt tag that matches the README and the sample workflow, document `@main` only as a bleeding-edge fallback, and make a greenfield `uv add "sql-test @ git+…@<tag>"` succeed.

- **Done when:** a new directory can `uv add` the documented tag and import `sql_test`; the sample workflow pin resolves; README and [CI-3](#ci-3) adopt text name the same tag.
- **Depends on:** [CI-2](#ci-2), [CI-3](#ci-3)

<a id="doc-1"></a>
#### DOC-1 Copy-pasteable consumer project

[UAT.md](UAT.md) #2, #3, #10, #11: the sample's `pyproject.toml` is only `[tool.sql-test]`, so literal README `uv add` fails without a `[project]` table (and usually `[tool.uv] package = false`). Adopt docs must include a full minimal consumer `pyproject.toml`, mapping CSV headers (`table_ref`, `sql_ref`), Python version floor, and either a standalone sample that installs `sql-test` itself or a clear “this folder is monorepo-only” warning.

- **Done when:** following the adopt section alone produces a consumer repo that installs, discovers, and runs one case under pytest without reading HELPER.
- **Depends on:** [CI-6](#ci-6), [CI-3](#ci-3)

<a id="cli-7"></a>
#### CLI-7 `sql-test init`

[UAT.md](UAT.md) #4 and #13: adopters invent mapping shape, DDL layout, case folders, `conftest.py`, and `test_case_folders.py`. `sql-test init [path]` writes a minimal consumer skeleton (config, mapping stub, sqls stub, one empty case layout, pytest wiring) so `discover` and pytest work before any product SQL exists.

- **Done when:** `sql-test init /tmp/demo && cd /tmp/demo && uv sync && uv run pytest` is green (or skips with an explicit “add SQL” message), and `sql-test discover .` lists the stub model once a SELECT + mapping row are filled in.
- **Depends on:** [DOC-1](#doc-1), [CLI-1](#cli-1)

<a id="eng-36"></a>
#### ENG-36 Diagnose adoption failures

[UAT.md](UAT.md) #6–#9: missing DDL, bad `sql_ref`, typo’d `sqls=` path, wrong mapping headers, INSERT-as-producer, and misnamed mock columns often look like unused mocks, empty actuals, `KeyError`, or raw `CycleError`. Validate mapping headers; name missing SQL files and configured paths; reject or explain INSERT/MERGE producers until those kinds exist; report unknown mock/expected columns against the schema before compare looks like a logic fail.

- **Done when:** each of those failure modes names the file or config key involved, and none of the UAT reproduction steps surface only `mocks the run never reads` or an uncaught traceback for those mistakes.
- **Depends on:** [ENG-9](#eng-9), [ENG-25](#eng-25), [ENG-2](#eng-2)

<a id="app-20"></a>
#### APP-20 First-run authoring polish

[UAT.md](UAT.md) #12, #15–#19: blank workbench is dense; Case name is easy to miss; compliance copy says “member” data; port-in-use looks like success then dies; broken configured paths show errno. Emphasize naming a case before Save; generalize the synthetic-data reminder; fail clearly when the port is taken; warm up broken-path errors the way Settings does for missing config; gloss “in pipelines” on first contact.

- **Done when:** a UAT-style first save without a name points at the Case name field; compliance copy is repo-agnostic; a busy port never prints a false “serving at” success; a bad `sqls=` path names the path.
- **Depends on:** [APP-16](#app-16), [APP-14](#app-14)

<a id="app-21"></a>
#### APP-21 Accept actual as expected in the workbench

[UAT.md](UAT.md) #20: [APP-11](#app-11) is marked done, but the adopt README still said accept was missing and a greenfield Run still left expected hand-built. Wire (or restore) accept cell / row / all in the NiceGUI expected view so a good Run can become a passing case without editing CSV by hand.

- **Done when:** after Run, accepting the whole actual result fills expected and the case passes; README no longer says accept is unimplemented.
- **Depends on:** [APP-11](#app-11), [APP-16](#app-16)

---

## v0.6 — Spark execution

Swap execution to a Spark executor behind the same executor interface, so the app, pytest tests, and saved cases do not change.

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

## Framework testing — not a product version

Work that hardens how *this* repository tests the engine and test layer. It is not a feature QA sees in the app. Example-based tests stay; these add property-based coverage where the input space is large.

<a id="test-1"></a>
#### TEST-1 Property-based tests with Hypothesis (done)

Add Hypothesis as a **dev** dependency and use it only in this repository's tests — not in the authoring app, and not to generate checked-in case folders (those stay hand-written or Faker-once-then-commit).

Cover pure rules first, in this order:

1. **Comparison** ([ENG-15](#eng-15)): generated multisets of rows; same multiset passes; remove / change / add a row yields missing / changed / unexpected under the [comparison defaults](HELPER.md#comparison-defaults).
2. **Column cast / CSV cell round-trip** ([ENG-14](#eng-14), [ENG-16](#eng-16)): typed values survive write-as-text then `Column.cast`; invalid text raises.
3. **Relation parse and resolve** ([ENG-21](#eng-21)): random catalogs of one-, two-, and three-level names; unique short names resolve, ambiguous bare names error naming candidates, unknown names stay as written.
4. **Small synthetic plans** ([ENG-8](#eng-8), [ENG-25](#eng-25)): tiny DAGs with random givens; pruned relations are not executed, `unused` ⊆ given, `needs_rows` empty iff every source still needed is given. Not a substitute for the scale suite or real-SQL lineage tests.

Do not use Hypothesis for DuckDB execution, the app UI, or N-table scale shapes.

- **Done when:** Hypothesis is in the dev dependency group; each of the four areas has at least one `@given` test that fails if the property is broken; existing example-based tests still pass.
- **Depends on:**
  - [ENG-15](#eng-15) for comparison
  - [ENG-14](#eng-14) and [ENG-16](#eng-16) for cast / case cells
  - [ENG-21](#eng-21) for relations
  - [ENG-8](#eng-8) and [ENG-25](#eng-25) for plan properties

<a id="test-2"></a>
#### TEST-2 Engine-only case volume (done)

A regression guard for catalog + coverage planning at repository scale, without DuckDB. 1000 independent models × 100 in-memory cases each (100k `plan_run`s via `pipeline_counts`). Complements `tests/test_scale.py`, which exercises lineage shapes through the executor. Follow-on speedups: [ENG-30](#eng-30), [ENG-32](#eng-32), [ENG-36](#eng-36), [COV-5](#cov-5).

- **Done when:** `tests/test_engine_perf.py` builds a 1000-model catalog, runs `case_counts` and `pipeline_counts` over 100k cases, and fails if catalog or pipeline phases blow a fixed wall-clock budget.
- **Depends on:**
  - [COV-1](#cov-1)
  - [COV-2](#cov-2)

---

## Later — not yet planned

- **Plan micro-opts.** Skip `TopologicalSorter` on trivial graphs, or build a states-only plan for coverage, only if [ENG-30](#eng-30), [ENG-32](#eng-32), [ENG-36](#eng-36), and [COV-5](#cov-5) leave a measured gap on [TEST-2](#test-2).
- **Pre-commit validation.** A hook running `sql-test validate`. Depends on [CLI-6](#cli-6).
- **Multi-repository workspaces.** Lineage across repositories, where the repository that owns the table under test owns the case. Depends on stable single-repository lineage from v0.1 and v0.8.
- **CDC and change propagation.** What changes downstream when an upstream row is inserted, updated, or deleted. Depends on v0.7.
- **Other consumers** such as IDE integrations or change-impact tooling, when there is a demonstrated use case.
- **pytest plugin.** Collect case folders without a test file in the repository. Deferred until the parametrized style has been used for a while, so the behaviour (how case folders are found, how the engine is built, opt-in or automatic) is chosen from experience. Depends on [CFG-1](#cfg-1).
- **Undefined-relation checks.** Flag inferred relations with no schema, naming the SQL that reads them, with a did-you-mean against declared relations, and a strict mode with an allowlist of external sources. Mostly the repository's own linting's job; add only if users ask. Depends on [ENG-22](#eng-22).
- **Browser E2E for the app.** Click-through coverage (for example Playwright) once the workbench is interactive enough that the NiceGUI `User` tests in `tests/test_app.py`, which simulate the browser without rendering, are not enough.
