# SQL Test Authoring Tool — Structured Context Handoff

## Purpose

Continuation-ready handoff for the design of a QA-focused, lineage-aware SQL test authoring tool. It captures current product boundaries, decisions, assumptions, architecture, implementation sequence, deferred features, risks, and open questions.

---

# 1. Product summary

Build a **lightweight local web application** that helps QA author durable data-product tests stored in GitHub and executed through the existing parametrized pytest framework.

The tool is **not the test runner/platform**. It is an authoring and exploration client sitting on top of the repository and underlying test framework.

Core loop:

```text
Select table under test
        ↓
Discover upstream lineage
        ↓
Choose relations to mock
        ↓
Enter mock data
        ↓
Prune lineage upstream of mock boundaries
        ↓
Execute real SQL between mocks and target
        ↓
Inspect actual output
        ↓
Compare actual vs expected
        ↓
Edit/accept expected output
        ↓
Save durable pytest test artifact into repo
        ↓
CI later executes the same test independently
```

---

# 2. Fundamental architecture boundary

> **Pytest/framework defines and executes tests. GitHub stores them. CI enforces them. The tool makes them easy for QA to author and explore.**

The tool is only one consumer of the test framework. CI also runs tests independently.

A saved test must be fully executable without the authoring application.

---

# 3. Core test model

## Full load

```text
TestCase
├── table_under_test
├── mocked_tables
│   ├── table_a → rows
│   └── table_b → rows
└── expected_target → rows
```

## Incremental

Incremental models commonly self-reference the target. Model this as target state before and after execution rather than exposing a graph cycle to QA.

```text
TestCase
├── table_under_test
├── target_before → rows
├── mocked_tables
└── expected_target_after → rows
```

Conceptually:

```text
target(before) ──┐
                 ├── incremental SQL ──→ target(after)
mock inputs ─────┘
```

Everything reliably derivable from the repo should stay out of the persisted test definition.

---

# 4. Repository is the source of truth

The application discovers rather than duplicates:

- SQL
- output relations/models
- referenced relations
- schemas
- lineage
- existing tests

Tests are durable and committed to GitHub. Only individual executions are short-lived/ephemeral.

The currently checked-out repository state/commit determines what the tool discovers. Do **not** merge/discover tests across branches.

Engineers own Git lifecycle. The application writes/edits test artifacts in the working tree; engineers handle branch, commit, push, PR, and merge normally.

---

# 5. Initial lineage rule

The first implementation supports **one repository**.

```text
Referenced relation
      │
      ├── Produced by SQL in current repo?
      │       ├── YES → internal model; recurse upstream
      │       └── NO  → source relation; stop
      │
      └── Mocked?
              └── YES → execution boundary; stop upstream traversal
```

A table not produced by SQL in the current repo is a **source** and remains mockable.

---

# 6. Mocking and pruning

Mocks are relation/table-centric.

If a relation is mocked, the framework does not execute its producer(s). Any ancestors no longer needed by another unlocked path are pruned.

UI lineage states:

- **Mocked**
- **Executed**
- **Pruned**
- **Source**

Potential later state: **Blocked**.

---

# 7. SQL-aware lineage without messy UI

A physical relation may have multiple SQL producers, so the **internal execution graph must be SQL-aware**.

```text
Relation → SQL operation/producer → Relation
```

The QA-facing default remains table-centric. Multi-producer tables can show “2 producers” and expose producer details through drill-down.

> **Execution graph = SQL-aware. QA lineage graph = table-aware projection.**

Mocking remains relation-centric.

---

# 8. Stateful/multi-statement SQL

Distinguish composition:

```text
A ─┐
   ├→ T
B ─┘
```

from sequential mutation:

```text
T0 → SQL A → T1 → SQL B → T2
```

INSERT, MERGE, UPDATE, DELETE+INSERT, and similar patterns require execution ordering/write semantics, not only lineage. This is a key technical risk.

---

# 9. Spark execution

Most production SQL is Spark-based. Local interactive execution is a major technical risk.

Do not assume another SQL engine is equivalent for DML/incremental semantics.

Early spike must answer:

> Can repository SQL + mocked relations + optional target-before state execute with sufficiently faithful Spark semantics and low enough latency for interactive QA authoring?

Important metrics:

- time to first result
- rerun/iteration latency

---

# 10. Expected vs actual UX

Expected and actual are shown together.

Expected is editable; actual is read-only.

Show:

- matching rows/values
- changed values
- missing expected rows
- unexpected actual rows

Actions:

- edit expected cell
- accept actual cell
- accept actual row
- remove expected row
- accept all actual as expected

Comparison semantics still need decisions for ordering, duplicates, NULLs, decimals, timestamps, nested Spark types, and row alignment.

---

# 11. Mock editor

Schema-aware from repo-discovered schema.

Minimum POC:

- edit cells
- add/delete/duplicate rows
- NULL
- basic type validation
- paste tabular data from Excel/Sheets

Relationship integrity is not currently mapped and is not required for POC.

---

# 12. Test discovery

Test discoverability is in scope.

Discover committed tests in the current repo/commit only. Do not aggregate across branches.

Target browser should show test counts. Opening an existing test loads it into the same workbench used to create tests.

---

# 13. Coverage

Coverage is in scope.

## Initial

- test count per target
- whether target has ≥1 discovered test

## Later

Structural execution coverage from lineage + mock boundaries, including producer coverage for multi-producer tables.

Coverage is derived from current repo state + committed tests; do not persist a separate coverage database.

---

# 14. Git behavior

Current decisions:

- tests are durable in GitHub
- current checkout/commit defines discovery
- no cross-branch discovery
- engineers own Git workflow
- no branch/commit/push/PR management required
- test/PR review is out of scope

---

# 15. Multi-repo roadmap

Deferred until single-repo semantics are stable.

Future workspace:

```text
Workspace
├── customer-repo
├── claims-repo
└── eligibility-repo
```

Invariant:

> **The repo that owns the table under test owns the test case. Target determines ownership; mocks do not.**

Future concerns:

- globally unique relation identity
- repo dependency discovery
- per-repo version selection
- main as normal/default baseline
- cross-repo reproducibility
- dependency compatibility

---

# 16. CDC/change propagation roadmap

Later feature only.

Question:

> If an upstream row is inserted, updated, or deleted, what changes downstream?

Do not add CDC concepts to the POC. Only avoid architectural blockers by keeping fixtures as data, execution orchestration separable, and incremental target-before/after clean.

---

# 17. POC scope

Prove one complete loop:

> **Pick target → understand lineage → mock sources/boundaries → enter data → execute real SQL → inspect actual vs expected → edit expected → save a pytest case.**

Minimum:

1. Single local repo.
2. Discover SQL-defined models.
3. Discover referenced relations.
4. Unknown produced relations become sources.
5. Build upstream lineage.
6. Select mocks.
7. Prune at mock boundaries.
8. Schema-aware mock grid.
9. Execute remaining SQL.
10. Display target output.
11. Diff expected vs actual.
12. Edit expected.
13. Save pytest-compatible artifact.
14. Reload existing test.
15. Saved test runs independently through pytest.
16. Basic test discovery.
17. Basic target/test-count coverage if inexpensive.

---

# 18. Outside POC

- multi-repo
- repo version selection
- Git lifecycle UI
- commits/pushes/PRs
- test review
- relationship integrity modeling
- production-data sampling
- historical run management
- sophisticated semantic coverage
- schema migration tooling
- centralized/multi-user server
- CDC
- SQL editing
- schema editing

Incremental support may follow full-load if it materially complicates the first spike.

---

# 19. Recommended implementation order

## Phase 0 — Headless feasibility

Build `run_test(target, mocks, expected)`-like capability:

1. discover SQL outputs
2. identify inputs/outputs
3. classify unknown relations as sources
4. build lineage
5. apply mocks
6. prune
7. execute
8. return target
9. compare expected

Test representative real models.

## Phase 1 — Target/repo discovery

Local repo, model search, target selection, schemas.

## Phase 2 — Lineage UI

Upstream graph, sources, mock/unmock, execution states.

## Phase 3 — Mock editor

Schema-aware grid and spreadsheet paste.

## Phase 4 — Interactive execution

Target + mocks → run → actual.

## Phase 5 — Expected/actual diff

Editable expectation and accept actions.

## Phase 6 — Persistence/discovery/basic coverage

Save/load tests, test counts, simple coverage, verify ordinary pytest execution.

## Phase 7 — Incremental

Target-before, self-reference semantics, incremental DML.

## Phase 8 — Rich lineage/coverage/debugging

Producer drill-down, structural coverage, intermediate inspection.

## Phase 9 — Multi-repo

Federated lineage, identity, versions, target-repo ownership.

## Later — CDC

State/event/change-propagation testing.

---

# 20. Feature dependencies

```text
Repo discovery
      │
      ├──────────────→ Schema discovery ──→ Mock editor
      ▼
SQL dependency discovery
      ▼
Internal SQL-aware graph
      ├──────────────→ Table lineage UI
      │                      ↓
      │                 Mock boundaries
      └──────────────────────┘
                 ↓
           Execution planner
                 ↓
            Spark execution
                 ↓
             Actual output
                 ↓
         Expected/actual diff
                 ↓
           Test persistence
            ┌────┴─────┐
            ↓          ↓
       pytest/CI   Test discovery
                       ↓
                    Coverage
```

---

# 21. Success metrics

## Test-authoring time

Compare representative test creation with current workflow vs tool.

## Time to first result

Time from selecting target to first actual output.

## Iteration latency

Time from changing a mock/expected value to new result.

## End-to-end usability

A QA engineer who did not build the tool can find a target, understand lineage, mock inputs, construct data, run, understand mismatch, edit expectation, save, and run the test through ordinary pytest without manually editing Python.

## Independent execution

100% of saved tests execute through standard pytest/CI without the application.

## Lineage correctness

Discovered dependencies and pruning match actual execution dependencies for representative models.

## Discoverability

QA can quickly answer whether a table has tests, what tests exist, which targets lack tests, and what a test mocks/expects.

---

# 22. Underlying assumptions

- SQL and schemas live in repo.
- SQL is primarily DML.
- Pytest is canonical and parametrized.
- Tests are durable in GitHub.
- UI is not required for CI.
- Production execution is mostly Spark.
- Models are mostly full-load or incremental.
- Incremental models may self-reference.
- Unknown referenced relations in current repo are sources.
- Sources are mockable.
- Relationship integrity is not currently mapped.
- QA thinks primarily in tables/relations.
- Engineers own Git lifecycle.
- Current checkout/commit defines discovery.
- No cross-branch test aggregation.
- Default lineage is table-centric.
- Internal execution graph can be SQL-aware.

---

# 23. Open risks/questions

## Spark fidelity and latency

Can interactive execution be faithful and fast enough?

## SQL parsing/lineage

Can repo SQL reliably map to inputs → operation → outputs, including templating and DML?

## Stateful execution order

Can multi-statement/multi-producer mutation order be derived?

## Comparison semantics

Need defaults for unordered rows, duplicates, NULL, decimals, timestamps, nested types, and row alignment.

## Incremental execution

Need deterministic target-before materialization and target-after inspection.

## Non-table dependencies

UDFs, macros, runtime parameters, config, lookup files, etc. may later matter.

## Data governance

If future fixture tooling samples real Customer/Claims data, PHI/PII leakage into Git becomes a material risk. POC should prefer synthetic/manual fixtures unless an approved path exists.

---

# 24. Decisions to preserve

1. Pytest is under the hood and parametrized.
2. UI helps build tests; CI runs them independently.
3. Tests are durable; execution is short-lived.
4. Target table's repo owns the test.
5. Mocks do not determine ownership.
6. Start with one repo.
7. Unknown referenced relation = source.
8. Sources are mockable.
9. Default lineage is table-centric.
10. Internal execution graph may be SQL-aware.
11. Multi-producer detail uses drill-down/progressive disclosure.
12. Expected and actual appear together; expected is editable.
13. Discovery and coverage are in scope.
14. No test discovery across branches.
15. Engineers own Git lifecycle.
16. Test review/PR workflow is out of scope.
17. Spark/local execution is a major risk.
18. Full-load and incremental/self-reference are common.
19. Relationship integrity is not a POC prerequisite.
20. CDC is later and should not complicate POC.

---

# 25. POC exit criterion

> **A QA engineer who did not build the application can find a target table, understand its lineage, mock appropriate upstream relations, construct a scenario, run the real SQL, inspect the output, reconcile actual versus expected results, save the test, and have that test execute successfully through ordinary pytest without the application.**

The workflow should be materially faster or easier than manual test creation.

If faithful Spark execution or interactive latency cannot be achieved, treat that as a POC finding rather than hiding it behind more UI.

---

# 26. Suggested next concrete step

Do not begin with the full web app.

Pick a small representative set of SQL models from one real repo and build the Phase 0 headless spike.

Include:

- simple full-load model
- multiple upstream relations
- source relation not defined in repo
- meaningful mock/pruning boundary
- multi-producer or multi-statement case if common
- incremental/self-reference case for follow-on

Measure execution fidelity and latency. Build the UI around the same framework once this path is reliable.
