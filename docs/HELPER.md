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

pytest discovers the case folders and runs one parametrized test per case, so a saved case needs no Python.

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
      │       │           └── No  → boundary; stop
      │       │
      │       └── No → source table; stop
      │
      └── Mocked?
              │
              └── Yes → execution boundary; stop upstream traversal
```

A table not defined by SQL in the current repository is considered an external/source table.

Lineage goes as far back as the SQL can be parsed. Wherever parsing breaks, or a table has no schema, that table is a boundary: traversal stops there and the table is treated like a source. A parse failure shortens lineage rather than blocking the test.

Source and boundary tables remain mockable.

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

The UI should distinguish at least:

- **Mocked** — supplied by the test
- **Executed** — real repository SQL will execute
- **Pruned** — no longer required because of a mock boundary
- **Source** — referenced but not produced in the current repository
- **Boundary** — produced in the repository, but its SQL cannot be parsed or it has no schema; drill-down shows which

Every table that will be read but is not produced by executed SQL needs test data. That includes unmocked source and boundary tables and mocked tables with no rows yet. These tables are shown grey until data is added, and colored once they have data. Running with grey tables reports which tables still need data.

---

# SQL-Aware Lineage

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

## Repository discovery

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

CI runs pytest or the CLI. It does not add CI-specific behavior to the engine.

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
- validation

Avoid one implementation per entry point. Separate app, pytest, and CI engines would drift, and a case could pass in the app and fail in CI.

## Entry points

**Authoring app.** The local web application QA uses. It contains presentation and interaction logic only and runs against the checked-out repository, for example `sql-test app .`.

**pytest.** The package provides a pytest plugin that discovers committed case folders and runs each one through the engine. A case saved by the app is a normal repository test, and it runs through pytest without the app installed or running.

**CLI.** A headless interface over the engine, for example:

```bash
sql-test discover
sql-test validate
sql-test run
sql-test app
```

The exact commands are not final. What matters is that a headless interface exists beneath the app.

**Reusable GitHub Actions workflow.** It lives in the tool's repository. A consuming repository calls it in a few lines:

```yaml
jobs:
  data-tests:
    uses: org/sql-test-tool/.github/workflows/data-tests.yml@v1
```

The workflow checks out the calling repository, sets up Python, installs the package, and runs pytest. It works from the checked-out repository, not from SQL, schema, or case files passed as parameters.

**Pre-commit, later.** A hook running `sql-test validate` for fast static checks only:

- the case parses
- the target and mocked tables exist
- mocked tables are upstream of the target
- CSV columns match known schemas
- CSV values parse to the expected types
- lineage resolves
- case paths and names follow repository conventions

Execution stays with pytest and CI. Pre-commit is a consequence of having a CLI, not a requirement driving the design, and it is not part of the POC.

**Other consumers** such as IDE integrations, coverage reporting, change-impact tooling, and CDC tooling can be added the same way, only when there is a demonstrated use case.

## Ownership

Data-product repositories own their data products and test cases. The tool's repository owns the machinery that authors, validates, discovers, and executes them. No engine code is copied into a consuming repository.

A consuming repository needs very little:

```text
customer-data/
├── sql/
├── schemas/
├── cases/
│   └── <table under test>/<case name>/
├── data-test.yaml                       only if repo-specific config is needed
└── .github/workflows/data-tests.yml     calls the reusable workflow
```

This layout is illustrative. Where SQL, schemas, and cases live, and how SQL files map to tables, can differ per repository. The sample repository keeps SQL in `admin/sqls/` and maps each table to its SQL file in `admin/config/lookup_sql_table_mapping.csv`, with columns `load_type`, `table_ref`, and `sql_ref`.

## Versioning

The engine, pytest plugin, CLI, app, and reusable workflow are released together as one version. Consuming repositories pin a tag such as `@v1`, never `main`, so a change on the tool's `main` branch cannot silently change CI in every consuming repository.

The case format carries its own format version if compatibility ever requires it. The tool's release version and the case format version are separate.

## Tool repository layout

One repository is enough. The engine, app, pytest plugin, and workflow do not need to be split into separate repositories or products. An illustrative layout:

```text
sql-test-tool/
├── src/sql_test/
│   ├── engine/
│   │   ├── discovery/
│   │   ├── lineage/
│   │   ├── execution/
│   │   ├── comparison/
│   │   └── validation/
│   ├── pytest_plugin/
│   ├── cli/
│   └── app/
├── .github/workflows/data-tests.yml
├── tests/
└── pyproject.toml
```

## Entry point sequence

Entry points are added one at a time, and each stays thin:

1. Engine as a headless spike (Phase 0).
2. Minimal CLI around the engine.
3. Authoring app (Phases 1–5).
4. pytest plugin and durable case format (Phase 6). This may overlap with the app, because the app must save cases that pytest can run.
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

Execution tentatively runs on DuckDB and is swapped for Spark later. The swap happens inside the engine's execution layer, so the app, pytest plugin, and saved cases do not change.

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
- A table whose SQL cannot be parsed, or that has no schema, is a lineage boundary and is treated like a source.
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

SQL that fails to parse becomes a lineage boundary, so parse failures limit how far back lineage reaches rather than blocking a test. The remaining risk is SQL that parses but yields wrong dependencies, because QA chooses mock boundaries from that lineage.

## Multiple producers

How frequently do multiple SQL operations produce the same relation, and are their execution/order semantics discoverable from existing repository conventions?

## Comparison semantics

Expected-vs-actual comparison needs defined behavior for:

- unordered rows
- duplicate rows
- NULL
- decimals
- timestamps
- nested Spark types

The POC should establish sensible defaults without exposing unnecessary configuration to QA.

CSV also needs a NULL convention, because an empty cell could mean NULL or an empty string.

## Incremental semantics

The framework needs a deterministic way to materialize `target_before`, execute incremental SQL, and inspect `target_after`.

This should be solved after the full-load authoring loop unless it blocks representative testing.

---

# POC Exit Criteria

The POC is successful when a QA engineer who did not build the application can use it on a real repository to:

> Find a target table, understand its lineage, mock appropriate upstream relations, construct a scenario, run the real SQL, inspect the output, reconcile actual versus expected results, save the test, and have that test execute successfully through ordinary pytest without the application.

The POC should demonstrate that this workflow is materially faster or easier than creating the same test manually.

If the execution framework cannot provide sufficiently faithful Spark behavior or interactive execution latency, that should be treated as a POC finding rather than compensated for by building additional UI.
