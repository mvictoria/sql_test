# FOSS Architecture Direction

## Overview

The project should be designed as a FOSS **visual test-authoring environment for SQL data transformations**, rather than as a Spark-specific or organization-specific QA application.

The core workflow remains:

```text id="r9ryir"
Select target
    ↓
Discover lineage
    ↓
Choose mock boundaries
    ↓
Enter mock data
    ↓
Execute real transformation SQL
    ↓
Compare expected vs actual
    ↓
Edit expectation
    ↓
Save durable test
    ↓
Run independently in CI
```

The FOSS direction does not require broad engine or repository support in the initial implementation.

Instead, the architecture should establish clean seams between:

- test definition
- repository discovery
- lineage
- execution planning
- execution engine
- result comparison
- pytest
- UI

The initial implementation can continue to target our actual environment. Generalization should happen when additional use cases appear.

---

# Product Positioning

The project should not primarily position itself as:

- another SQL testing framework
- another data-quality platform
- another SQL IDE
- a Spark testing tool

A better framing is:

> **Visual test authoring for SQL data transformations.**

More concretely:

> Select a SQL model, use lineage to choose which upstream tables to mock, enter test data, execute the real transformation, compare actual and expected output, and save a durable test that can run independently in CI.

The primary differentiation is the use of **lineage as an interactive mechanism for defining the test boundary**.

---

# Architectural Principle

The most important architectural rule is:

> **The test definition and test execution core must not depend on the UI, pytest, or a specific SQL execution engine.**

Conceptually:

```text id="7ixfsl"
                 Test artifacts
                       │
                       ▼
                     Core
                ┌──────┼──────┐
                │      │      │
                ▼      ▼      ▼
               UI     CLI   pytest
                       │
                       ▼
                    Executor
```

The UI is one client of the testing core.

Pytest is another.

A CLI can be another.

CI should never require the UI.

---

# Canonical Test Model

The durable test definition should remain intentionally small.

For a full-load transformation:

```text id="2vm68m"
TestCase
├── target
├── mocks
└── expected
```

For an incremental transformation:

```text id="nwvxt8"
TestCase
├── target
├── target_before
├── mocks
└── expected
```

The test definition should not unnecessarily persist information that can be derived from the repository, such as:

- schema
- lineage
- SQL
- execution plan
- coverage

A human should be able to inspect and understand a test artifact directly in Git without using the application.

---

# Test Format as a Public Contract

For an internal tool, test storage can rely heavily on organizational conventions.

For FOSS, the test-case representation becomes part of the public interface.

A test should be representable in a simple format such as YAML:

```yaml id="96mt0h"
name: duplicate_claim

target: customer_summary

mocks:
  claims:
    rows:
      - claim_id: 1
        customer_id: 100
        amount: 50

expected:
  rows:
    - customer_id: 100
      claim_total: 50
```

The exact format does not need to be finalized during the first POC.

The important properties are:

- human readable
- easy to review in Git
- easy to create manually
- independent of the UI
- independent of pytest
- sufficiently stable to become a durable repository artifact

The GUI should not create a proprietary representation that can only be understood or executed through the GUI.

---

# Core Architecture

A likely high-level architecture is:

```text id="87axrj"
                         Web UI
                           │
                           ▼
                  ┌──────────────────┐
                  │ Application Core │
                  │                  │
                  │ Test cases       │
                  │ Test discovery   │
                  │ Lineage          │
                  │ Coverage         │
                  │ Comparison       │
                  └────────┬─────────┘
                           │
          ┌────────────────┼────────────────┐
          ▼                ▼                ▼
     Repo/Catalog       Planner         Test Model
          │                │
          │                ▼
          │          Execution Plan
          │                │
          │                ▼
          │             Executor
          │                │
          │       ┌────────┼─────────┐
          │       ▼        ▼         ▼
          │     Spark    DuckDB   Postgres...
          │
          └────────── SQL Lineage
```

This does not imply that all of these implementations need to exist initially.

It defines where responsibilities should live.

---

# Repository / Catalog Layer

The core should not assume that every repository organizes SQL, schemas, and tests in the same way.

Instead, repository discovery should expose a canonical representation to the rest of the application.

Conceptually:

```python id="jgnbqy"
class Repository:
    def relations(self): ...
    def producers(self): ...
    def schema(self, relation): ...
    def tests(self): ...
```

The first implementation can support the current repository conventions.

A future project might provide:

```text id="x64p93"
GenericSqlRepo
DbtRepo
SQLMeshRepo
CustomRepo
```

without requiring changes to lineage, test authoring, or the UI.

A lightweight configuration file may eventually describe repository conventions:

```yaml id="h8bqeb"
models:
  paths:
    - sql/

schemas:
  paths:
    - schemas/

tests:
  path: tests/data/

dialect: spark
executor: spark
```

Configuration should only be introduced where convention-based discovery is insufficient.

---

# Canonical Relation Identity

The core should not assume that a relation is uniquely identified by a bare table name or filesystem path.

Different systems use identifiers such as:

```text id="9j38sc"
table
schema.table
database.schema.table
catalog.schema.table
```

Multi-repository support will introduce another namespace dimension.

The internal relation model should therefore allow a stable qualified identity.

Conceptually:

```text id="rcn69j"
Relation
├── catalog?
├── database?
├── schema?
├── name
└── repository?
```

The UI can display a shorter friendly name when it is unambiguous.

Getting relation identity correct early reduces the risk of major changes when multi-repository workspaces are introduced.

---

# SQL Operations as First-Class Internal Objects

The internal lineage/execution model should distinguish relations from operations.

Canonical representation:

```text id="pr1e6q"
Relation
    ↓
SQL Operation
    ↓
Relation
```

rather than treating lineage internally as only:

```text id="azmv6g"
Table → Table
```

For example:

```text id="0vebhq"
raw_claims
     │
     ▼
claims.sql
     │
     ▼
staged_claims
```

This allows the internal model to eventually represent:

- multiple producers for one table
- INSERT
- INSERT OVERWRITE
- MERGE
- UPDATE
- full-load models
- incremental models
- ordered operations

The QA-facing graph can still project this into the simpler:

```text id="bex9ad"
raw_claims → staged_claims
```

SQL-level detail should use progressive disclosure rather than cluttering the default lineage view.

---

# Separate Lineage from Execution Planning

Lineage answers:

> What depends on what?

The test boundary answers:

> What has the test chosen to mock?

The execution planner answers:

> Given this lineage and these mocks, exactly what must execute?

These should remain distinct concepts:

```text id="1n13dy"
Repository catalog
       ↓
Lineage graph
       ↓
Mock boundaries
       ↓
Execution planner
       ↓
Execution plan
       ↓
Executor
```

This separation becomes increasingly important for:

- incremental models
- self-reference
- multiple producers
- ordered DML
- multi-repository lineage
- future CDC/change-propagation testing

The visual lineage graph should not itself become the execution engine.

---

# Executor Abstraction

SQL execution should sit behind a defined boundary.

Conceptually:

```python id="l0q0g2"
class Executor:
    def setup(self): ...
    def create_relation(self, relation, schema, rows): ...
    def execute(self, operation): ...
    def read_relation(self, relation): ...
    def teardown(self): ...
```

The exact interface should be driven by the first real implementation rather than designed as a universal abstraction upfront.

The initial executor can be whichever engine is required to prove the product internally.

Likely future executors include:

```text id="j6tg6d"
Spark
DuckDB
Postgres
Snowflake
BigQuery
```

Supporting these is not an initial requirement.

The architectural requirement is simply that core application logic does not directly depend on Spark-specific APIs throughout the codebase.

---

# SQL Dialect vs. Execution Engine

SQL dialect and execution engine should be treated as related but conceptually separate concerns.

The lineage/parser layer needs to understand operations such as:

```text id="s9c99e"
SELECT
INSERT INTO
INSERT OVERWRITE
MERGE INTO
CREATE TABLE AS
UPDATE
DELETE
```

The executor is responsible for actually performing those operations.

Conceptually:

```text id="6yxl06"
SQL
 ↓
Dialect / parser
 ↓
Canonical operations
 ↓
Planner
 ↓
Executor
```

A SQL parsing library such as SQLGlot may be useful here, but the project should avoid coupling every layer directly to a particular parser's internal representation.

---

# Execution Engines and the FOSS Default

Spark should not define the identity of the project.

It can be the first executor if that best supports the initial real-world use case.

For broader FOSS adoption, a lightweight local executor such as DuckDB may eventually provide a better default installation experience:

```text id="kz5d8p"
Core
 │
 ├── DuckDB
 │    easy local execution
 │
 ├── Spark
 │    Spark fidelity
 │
 └── other engines
```

However, the project should not claim that executing SQL through a different engine guarantees equivalent semantics.

Where engine-specific behavior matters, users should execute tests using an appropriate executor.

Engine portability should be an explicit capability rather than an assumed property.

---

# Pytest Integration

Pytest remains a first-class integration but should not define the internal test model.

The relationship should be:

```text id="hwe0r3"
TestCase
    │
    ├── UI
    ├── CLI
    └── pytest integration
```

For pytest, existing test cases can be discovered and parameterized:

```text id="t41j5p"
discover test cases
       ↓
pytest parametrization
       ↓
core test runner
       ↓
executor
```

This preserves the current desired organizational workflow while allowing other users to execute the same test definitions without adopting pytest.

---

# CLI

A headless CLI is valuable for FOSS even if the primary user experience is visual.

For example:

```text id="46bnfv"
sqltest run tests/customer_summary/duplicate_claim.yaml
```

or:

```text id="r7xoq5"
sqltest test .
```

The CLI provides:

- an easy way to validate the core independently of the UI
- a non-pytest execution path
- debugging for contributors
- a straightforward automation interface

The CLI and UI should invoke the same underlying core.

---

# Coverage

Coverage should remain derived rather than persisted.

The initial implementation can report simple target coverage:

```text id="8rxw1f"
customer_summary          8 tests
customer_demographics     4 tests
member_attribution        0 tests
```

Future structural coverage can use the execution planner to determine which operations are exercised by discovered tests.

Because coverage is derived from canonical test definitions and lineage, it should work independently of whether tests are executed through the UI, CLI, or pytest.

---

# Multi-Repository Direction

Multi-repository support should eventually introduce a workspace:

```text id="u08qrx"
Workspace
├── customer-repo
├── claims-repo
└── eligibility-repo
```

The workspace produces a federated relation catalog and lineage graph.

The ownership invariant remains:

> **The repository owning the table under test owns the test case.**

Mocks can reference relations owned by other repositories.

The first implementation should remain single-repository, but relation identity and repository discovery should avoid assumptions that make federation unnecessarily difficult later.

---

# CDC / Change Propagation

CDC remains a future feature.

The current model:

```text id="3yixgx"
inputs → execute → expected
```

extends naturally to incremental testing:

```text id="tkid3r"
target_before + inputs
          ↓
       execute
          ↓
   expected_after
```

and potentially later:

```text id="q08qlc"
state_before
     ↓
INSERT / UPDATE / DELETE
     ↓
execute affected pipeline
     ↓
state_after
```

No CDC implementation is needed now.

The only architectural requirement is to avoid tightly coupling execution to an assumption that every test consists of exactly one immutable input snapshot and one execution step.

---

# Avoid Premature Plugin Architecture

The project should establish **extension seams**, not immediately build a plugin ecosystem.

Avoid beginning with complex dynamic systems for:

- executor plugins
- repository plugins
- dialect plugins
- hooks
- extension registries

Instead, use ordinary interfaces and modules.

For example:

```text id="kzyfsv"
core/
    catalog
    lineage
    planner
    testcase
    comparison

executors/
    spark

integrations/
    pytest

cli/

server/

ui/
```

When a second executor or repository type is actually implemented, the project can validate and refine the abstraction based on real requirements.

Plugin discovery/loading can be added later if external extensions become valuable.

---

# Dependency Direction

The intended dependency direction is:

```text id="4osfqk"
UI ─────────────┐
CLI ────────────┼──→ Core
pytest ─────────┘      │
                       ├──→ Catalog
                       ├──→ Lineage
                       ├──→ Planner
                       ├──→ Comparison
                       └──→ Executor interface
```

Core must not depend on:

- UI
- pytest
- a particular SQL executor

Engine-specific implementations depend on the core contracts rather than the reverse.

---

# POC Impact

The FOSS direction should **not materially expand the POC**.

The POC remains:

```text id="z6sgcu"
single repo
    ↓
discover SQL/schema
    ↓
select target
    ↓
display table lineage
    ↓
select mock boundaries
    ↓
edit fixture data
    ↓
execute
    ↓
expected ↔ actual
    ↓
save durable test
```

Only one:

- repository convention
- SQL dialect
- executor
- test-framework integration

needs to work initially.

The difference is that these implementations should live behind deliberate architectural boundaries.

---

# Headless Core as an Early Deliverable

The initial execution spike should establish the headless core API rather than putting execution logic directly into the application server.

Conceptually:

```python id="dhbb6m"
repo = load_repo(".")

case = TestCase.load("tests/example.yaml")

plan = plan_test(repo, case)

result = executor.run(plan)

comparison = compare(result, case.expected)
```

The same flow should eventually support:

```text id="23x4su"
                 ┌── Web UI
                 │
TestCase → Core ──┼── CLI
                 │
                 └── pytest
```

This is the most important architectural consequence of the FOSS direction.

---

# FOSS Success Signals

Beyond internal QA success metrics, useful signals for the open-source project would include:

- successful use against repositories not designed by the original team
- users adopting the tool without changing their existing CI architecture
- users creating tests without needing the UI to execute them
- requests or contributions for additional executors
- requests or contributions for additional repository conventions
- tests authored by QA/analysts who previously depended on engineers
- community fixes for previously unsupported SQL patterns
- third parties successfully extending the project without modifying the core

A particularly strong architectural validation would be:

> A user with a substantially different SQL repository can implement a small repository or executor adapter and use the existing lineage, authoring UI, comparison, and test-discovery functionality unchanged.

---

# What Not to Generalize Yet

FOSS should not become justification for solving hypothetical requirements.

The initial project should not attempt to support:

- every SQL dialect
- every execution engine
- every repository layout
- dbt and SQLMesh integrations
- arbitrary test frameworks
- distributed execution
- cloud execution
- dynamic plugin discovery
- multi-repository workspaces
- CDC
- Git hosting providers

Build the real internal use case first.

The goal is:

> **Specific implementation, general architecture.**

If the core boundaries are correct, broader support can emerge from actual users and contributors rather than speculation.
