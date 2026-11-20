# SQL Test Authoring Tool — Conversation Transcript

> Chronological transcript of the product/design discussion. Minor formatting normalization has been applied for readability; the substance and evolution of the discussion are preserved.

## User

We're an engineering team building an app to help our qa team test sqls for data product. Current thought is well build light local web app that will

Allow them to select table(s) under test. See lineage and insert mock data, lineage wil update so mocked datatable prunes upstream tables. They'll see mocked tables and what remains in lineage that is unlocked

Be able to run end to end

Be able to see output results

Be able to store data as test case in repo to be executed by ci

## Assistant

The concept is coherent. Frame it less as a SQL runner and more as a lineage-aware test harness for data products.

The key abstraction: a test case defines a target, mocked boundary tables, execution parameters, and assertions. The UI is an editor/debugger for that test case.

Proposed workflow:

```text
Select target model/table
        ↓
Load upstream lineage
        ↓
Choose tables to mock
        ↓
Enter / load fixture data
        ↓
Prune lineage upstream of mocked nodes
        ↓
Show executable graph
        ↓
Run graph locally
        ↓
Inspect intermediate + final results
        ↓
Add assertions
        ↓
Save test definition + fixtures to repo
        ↓
Same runner executes in CI
```

Lineage pruning is particularly important. If an intermediate table is mocked, its upstream sources become irrelevant to that execution while other unlocked branches continue to execute.

The architecture should separate a headless test engine from the UI so local interactive execution and CI use the same semantics.

## User

Pytest is under the hood runner

## Assistant

That makes the architecture cleaner. Pytest should be the canonical execution layer rather than adding a proprietary test runner.

The QA UI handles target selection, lineage, fixture editing, results, and assertions. A Python testing library handles lineage resolution, mock substitution, SQL execution, and comparisons. Pytest remains underneath for both local and CI execution.

A declarative test-case format is preferable to generating bespoke Python for every case. A parametrized pytest harness can discover the cases.

## User

Yeah pytest will be parametrized. Probably just have mocked tabels and data table under test and expectation

## Assistant

That is the right abstraction. Keep the persisted test case minimal:

```text
TestCase
├── table_under_test
├── mocks
│   ├── table_a → rows
│   └── table_b → rows
└── expectation
    └── expected rows
```

Everything else should be derived by the framework. A full expected relation is a strong primitive for data-product QA; sophisticated assertion DSLs can wait.

A useful interaction is Actual → Set as expectation, after QA has reviewed the result.

## User

Should see both outputs and expected ehrre it differsand be able to edit expected

## Assistant

Make the result diff/editor a primary screen. Show expected and actual together, with changed, missing, and unexpected rows/values. Expected is editable; actual is read-only.

Useful actions include accepting an actual cell/row into expected, removing obsolete expected rows, and accepting the entire actual result when bootstrapping a new test.

Row identity/comparison semantics matter: SQL relations are unordered, duplicates may matter, and useful diffs require a way to align logical rows where possible.

## User

Ok put a hat on - what is missing

## Assistant

The core UX is good, but several semantics/failure modes need attention:

- Explicit equality/comparison semantics: order, duplicates, NULLs, types, decimals, timestamps.
- Schema-aware fixture editing.
- Clear lineage states: mocked, executed, pruned, potentially blocked.
- Intermediate result inspection for debugging.
- Fixture ergonomics such as spreadsheet paste and CSV import.
- Deterministic execution and awareness of uncontrolled dependencies.
- Distinguishing assertion failures from SQL/fixture/schema errors.
- Minimal test metadata such as name/description.
- Exact reproducibility between UI and CI.

A key concern is test isolation: if unlocked lineage reaches mutable warehouse sources, the test may not be deterministic.

## User

Schema and sqls live in the parent repo - these would be discovered when lineage is built

## Assistant

That removes configuration from the test artifact. SQL, schemas, and dependency information are authoritative in the repo. A test references repo objects rather than redefining them.

The persisted model should stay close to target + mocks + expectation. Schema, lineage, execution configuration, and keys should be derived unless a real use case forces overrides.

Important remaining questions include mock boundary semantics, unmocked leaves, repo/version coupling, comparison semantics, intermediate inspection, and persistence/discovery.

## User

So to make this sit on top of many repos it would have to be able to select a repo? Potentially also have a git client to create branch and commit saved test. Would also want existing tests and coverage to be discovered

## Assistant

At that point the app is a repo-aware SQL testing workbench. A repository/working tree provides models, schemas, tests, and lineage inputs.

A workspace concept can expose repo, branch/working tree, discovered data products, existing tests, and coverage.

For a local app, avoid owning cloning/auth if possible; point at an existing checkout. Git branch/commit integration could complete the workflow, but push/PR integration should be deferred.

Existing-test discovery should be first-class. Selecting a target should show existing tests and load them into the same editor used to create tests.

Coverage should initially be structural and carefully defined: target coverage, boundary coverage, and eventually execution/producer coverage rather than claiming generic code coverage.

## User

Ok problem - we have 2 repos one owns customer the other owns claims. Occasionally we need a claim table in customer testing. How to allow multiple repo selection

## Assistant

The unit of execution should become a workspace rather than a repo. A workspace can contain multiple repos and build one federated lineage graph.

Repo ownership should remain visible, but the graph can traverse across repos. QA can mock a Claims relation while testing a Customer target, pruning upstream Claims lineage at that boundary.

Avoid requiring manual repo selection every time if dependencies can be declared/resolved automatically.

Globally unique model identity is required across repos.

Tests should still be owned by one repo. Cross-repo execution introduces version/reproducibility concerns and should be treated carefully.

## User

Repo with table under test owns the test cas through right

## Assistant

Yes. Make this an invariant:

> Target determines test ownership. Mocks do not.

If the target is in Customer and a mocked dependency is in Claims, the test is persisted only in Customer. This keeps Git ownership and review clean.

## User

Ok and would need to be able to select versions of a repo. But ideally repo under test is at main

## Assistant

Use main as the default baseline for every repo, with per-repo version overrides. The target repo can normally start from main; dependency repos can be overridden when testing unreleased changes.

Changing a dependency repo version should recalculate lineage. This can eventually enable cross-repo change-impact testing.

## User

Ok. What if a table has data from 2 sqls separated by upstream raw sources. How does thay play in

## Assistant

This exposes a modeling requirement: the internal execution graph needs SQL-producing nodes, not only physical table nodes.

A physical relation may have multiple producers. Internally represent relation → SQL operation → relation. This preserves which upstream path generated data.

Mocking remains table-centric. Mocking the produced relation bypasses all producers. Mocking only one upstream source cuts only that branch.

A more difficult case is when multiple SQL files sequentially mutate the same table via INSERT/MERGE/UPDATE. Then lineage alone is insufficient; execution order and write semantics matter.

## User

How to build thay sql/table aware lineage without making it messy? Do they need to drill down?

## Assistant

Use progressive disclosure. Keep the default lineage table-centric because that matches QA's mental model. Mark tables with multiple producers, e.g. “2 SQLs,” and allow drill-down into producer details.

Internally maintain the full SQL-aware graph:

```text
Relation → SQL operation → Relation
```

The UI graph is a simplified relation-to-relation projection. Mocking stays relation-centric.

This separation is important:

- Execution graph = SQL-aware.
- QA lineage graph = table-aware projection.

## User

What else aren't we considering

## Assistant

Pressure-test semantics and failure modes rather than adding UI:

- Stateful SQL, cycles, incremental models, self-reference.
- Non-table execution dependencies such as UDFs/macros/runtime parameters.
- SQL dialect/runtime fidelity.
- Fixture realism and relationship integrity.
- Partial-column fixtures.
- Schema evolution.
- Branch/test discovery semantics.
- Dirty Git state/conflicts.
- Cross-repo identity/contracts and version compatibility.
- Coverage definitions.
- Test review and regression review.
- Security/data governance around copying real healthcare data into fixtures.

Avoid letting the tool become a general IDE. Keep the boundary focused on discovering, constructing, running, debugging, and saving data-product tests.

## User

Models are usually either full load or incremental which have a self reference

Mostly will be spark, but locally running will be a problem.

Relationship integrity is not cureently mapped anywhere but is a good point

Schema evolution shouldn't matter bc sqls are dml only and tests are short lived

Dont allow test discovery across branches. A commit is the only thing that matters

Engineer will own git lifestyle this is just a helper

## Assistant

Those constraints simplify the design.

Full-load models are straightforward. Incremental models require target pre-state as an input:

```text
target(before) ──┐
                 ├── incremental SQL ──→ target(after)
mock inputs ─────┘
```

The UI should present “Existing target data” rather than exposing a lineage cycle.

Spark execution is the largest technical spike. Avoid assuming DuckDB equivalence if Spark semantics are authoritative. Prove whether local Spark or another faithful execution approach can support interactive latency.

Git should shrink to a helper: operate on the current repo state and write test artifacts; engineers own branch/commit/PR lifecycle.

## User

Coverage should be there along eith test discoverability

Test review is probably out of scope. Besides loading a branch with open pr not sure how to help here

## Assistant

Keep coverage and discoverability in scope; drop test review as a product concept.

The tool can operate against whatever branch/commit is currently checked out without being PR-aware.

Test discoverability should be primary navigation: search tables/tests, show test counts, and load existing tests into the same workbench.

Coverage should be precisely defined. Start with target coverage/test count; later add lineage execution coverage and producer coverage. Coverage should live naturally on lineage and connect directly to test discovery.

## User

Tests being short lived means exec time. Not how long the test is kept for. Tests are kept in github

## Assistant

Correction: tests are durable repo assets; individual executions are short-lived.

That means schema evolution can matter because committed tests persist while SQL/schema/lineage change. Execution should be ephemeral and isolated.

Useful statuses include PASS, FAIL, INVALID, and ERROR.

Interactive Spark startup/rerun latency becomes an explicit architecture requirement because short execution/iteration time matters to QA authoring.

## User

Tool isn't the only thing that runs tests. They run on ci also

Tool helps build tests

## Assistant

Correct. The test framework is the product-independent foundation. The tool is a GUI/client for authoring and interactively running tests; CI consumes the same tests independently.

Architecture:

```text
GitHub repo
    │
committed test cases
    │
 ┌──┴───────────┐
 ▼              ▼
QA tool         CI
 │              │
 ▼              ▼
pytest framework
      │
      ▼
Spark execution
```

The clean boundary is:

> pytest/framework defines and executes tests. GitHub stores them. CI enforces them. The tool makes them easy for QA to author and explore.

## User

What would be the iterative plan of building

1st would like to only consider a single repo set of sqls. If a table is not defined in that repo considered to be source (still mockable).

What is bare minimum to make this usable poc

## Assistant

Aggressively constrain the POC. Prove one loop:

> Pick target → understand upstream tables → mock sources/boundaries → run real SQL → inspect actual vs expected → edit expected → save a pytest case.

Start with a headless execution spike before UI:

1. Discover SQL-defined tables.
2. Parse enough SQL to identify input/output tables.
3. Treat referenced tables not produced by repo SQL as sources.
4. Construct upstream lineage.
5. Replace selected relations with mock data.
6. Prune upstream lineage at mocks.
7. Execute remaining SQL.
8. Return target relation.
9. Compare to expected.

Then build four minimal surfaces: target selector, lineage/mock selection, mock data editor, and run + expected/actual diff. Include save/load of real pytest cases. Basic test discovery and simple target coverage can follow cheaply.

Explicitly defer multi-repo, Git UI, relationship integrity, sophisticated coverage, PR integration, CDC, etc.

Suggested order: execution feasibility → target discovery → lineage → mock editor → interactive execution → diff → persistence/discovery → incremental → richer coverage → multi-repo.

POC success criterion: a QA engineer who did not build the tool can create a real test substantially more easily than today, and the saved test runs through ordinary pytest without the application.

## User

Oh another feature way down list.

Cdc - data changes on upstream table what happens

## Assistant

CDC/change propagation fits naturally later. It changes the test semantics from static input/output to state + event:

```text
Given initial upstream/target state
When upstream INSERT/UPDATE/DELETE occurs
And pipeline executes
Then downstream target reaches expected state
```

This is particularly relevant for incremental models. A future UI could show before/after/delta at each downstream table.

Keep it on the roadmap but do not implement it in the POC.

## User

Do we need to know this is coming before starting basic example

## Assistant

No. Do not design the POC around CDC.

Only avoid unnecessary blockers:

- Keep fixtures as data rather than UI-specific state.
- Separate execution orchestration enough that multiple executions could be added later.
- Represent incremental self-reference cleanly as target-before → target-after.

Do not introduce CDC events/deltas into the initial test model.

## User

write doc for what we've discussed

want - brief overview, planned features, underlying assumptions, what's in scope/outside of boundaries, planned order of implementation, dependencies between features

include success metrics - your example on time to see data or whatever is good

what else would you incldue in doc

## Assistant

Recommended additional sections: design principles, core domain model, open technical questions/risks, and explicit POC exit criteria.

A full design draft was produced covering:

- Overview
- Design principles
- Core test model
- Lineage model
- SQL-aware lineage
- Planned UX
- Coverage
- POC scope
- Explicitly out of scope
- Implementation phases
- Feature dependencies
- Spark execution risk
- Success metrics
- Underlying assumptions
- Open questions/technical risks
- POC exit criteria

Key POC exit criterion:

> A QA engineer who did not build the application can find a target table, understand lineage, mock upstream relations, construct a scenario, run real SQL, inspect/reconcile actual vs expected, save the test, and have it execute successfully through ordinary pytest without the application.

## User

how can i get the entire context of what we discussed as a file

## Assistant

Recommended creating both:

1. A full chronological Markdown transcript.
2. A structured Markdown context handoff containing decisions, requirements, assumptions, rejected ideas, unresolved questions, architecture, roadmap, and enough history for another session to continue.

## User

Create both the full transcript and structured context handoff as Markdown files.
