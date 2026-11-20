# Multi-Entry-Point Architecture

## Overview

The SQL testing capability should be implemented as a **single pip-installable project with one shared engine and multiple thin entry points**.

The engine owns all test semantics. The local authoring application, pytest, CI, and any future developer tooling invoke that same implementation rather than independently implementing test behavior.

```text
                    sql-test-tool
                         │
                    Shared Engine
              ┌──────────┼──────────┐
              │          │          │
              ▼          ▼          ▼
         Web App       pytest       CLI
                                      │
                              ┌───────┴────────┐
                              ▼                ▼
                        Reusable GHA      Future tools
                                         (pre-commit)
```

This keeps test behavior consistent regardless of how a test is created or executed.

---

## Shared Engine

The engine is the core of the project and should not depend on a particular invocation environment.

It owns:

- repository discovery
- SQL discovery/parsing
- schema discovery
- lineage construction
- mock-boundary resolution
- execution planning
- fixture materialization
- Spark execution
- full-load and incremental semantics
- expected/actual comparison
- test-case discovery and loading
- validation
- cleanup

Conceptually:

```text
Repository + Test Case
         │
         ▼
      Engine
         │
    ┌────┼─────┐
    ▼    ▼     ▼
 Lineage Plan Execute
              │
              ▼
         Test Result
```

The engine should not need to know whether it was invoked by the web application, pytest, GitHub Actions, or a command-line operation.

---

# Python Package / CLI

The project should be pip-installable and expose a command-line interface.

For example:

```bash
pip install company-sql-test
```

Potential commands:

```bash
sql-test discover
sql-test validate
sql-test run
sql-test app
```

These commands are interfaces over the shared engine rather than separate implementations.

The exact CLI surface does not need to be finalized for the POC. The important architectural decision is that a headless interface exists beneath the web application.

---

# Entry Point 1: Local Authoring Application

The primary initial entry point is the local web application used by QA.

```text
Local repository
      │
      ▼
 Authoring App
      │
      ▼
 Shared Engine
```

The application provides the interactive experience:

- discover tables
- discover existing tests
- visualize lineage
- display coverage
- select mock boundaries
- edit mock data
- execute tests interactively
- inspect actual output
- compare actual and expected
- edit expected results
- save test artifacts into the repository

The application should contain presentation and interaction logic, but test execution semantics remain in the engine.

A conceptual invocation could eventually be:

```bash
sql-test app .
```

The application operates against the currently checked-out repository state.

---

# Entry Point 2: Pytest

Pytest remains the canonical test runner.

The package should provide the integration required for pytest to discover the committed test definitions and execute them through the shared engine.

```text
Committed Test Cases
        │
        ▼
      pytest
        │
        ▼
   Shared Engine
        │
        ▼
      Spark
```

The authoring application is not required for this path.

This is an important architectural invariant:

> A test created through the application must remain a normal repository test that can execute through pytest without the application being installed or running as a service.

Pytest provides the connection between durable test artifacts and normal engineering/CI test execution.

---

# Entry Point 3: Reusable GitHub Actions Workflow

The same project repository should contain a reusable GitHub Actions workflow for consuming data-product repositories.

A consuming repository should require very little CI-specific setup.

Conceptually:

```yaml
jobs:
  data-tests:
    uses: org/sql-test-tool/.github/workflows/data-tests.yml@v1
```

The reusable workflow is responsible for orchestration such as:

```text
Checkout calling repository
          │
          ▼
Set up Python / Spark environment
          │
          ▼
Install SQL test package
          │
          ▼
Run pytest / engine
```

The consuming repository continues to own:

- SQL
- schemas
- test definitions
- any minimal repo-specific configuration

The SQL testing project owns:

- engine
- pytest integration
- execution behavior
- common Spark setup
- reusable CI workflow

The workflow should operate against the checked-out repository rather than requiring individual SQL, schema, or test files to be passed as workflow parameters.

---

# Versioning

The reusable workflow should be versioned rather than consumed directly from `main`.

For example:

```yaml
uses: org/sql-test-tool/.github/workflows/data-tests.yml@v1
```

A release of the SQL testing project can therefore identify a compatible set of:

```text
sql-test-tool v1.x

├── Engine
├── pytest integration
├── CLI
├── Authoring application
└── Reusable GHA workflow
```

This avoids silently changing CI behavior across every consuming repository whenever the tool's `main` branch changes.

The persisted test-case format should also carry its own format/schema version if compatibility eventually requires it. Tool release version and test-definition format version should be treated as separate concepts.

---

# Entry Point 4: Future Pre-Commit Validation

Pre-commit is a potential later entry point, but it is **not part of the POC or near-term implementation plan**.

Because the project is pip-installable and exposes a CLI, adding a pre-commit hook later should require little architectural change.

Conceptually:

```text
git commit
    │
    ▼
pre-commit
    │
    ▼
sql-test validate
    │
    ▼
Shared Engine
```

The likely purpose of pre-commit would be **fast static validation**, not full Spark execution.

Potential checks include:

- test definition parses successfully
- target relation exists
- mocked relations exist
- mocked relations are valid dependencies of the target
- fixture columns conform to known schemas
- expected data conforms to the target schema
- fixture values can be parsed into expected types
- lineage can be resolved
- test paths/names follow repository conventions

Full Spark execution should generally remain with normal pytest/CI unless execution becomes sufficiently fast and reliable to justify local commit-time execution.

Pre-commit is therefore a useful consequence of the architecture, not a requirement driving the architecture.

---

# Other Future Entry Points

The same pattern allows additional integrations later without changing test semantics.

For example:

```text
                        Shared Engine
                             │
       ┌──────────┬──────────┼───────────┐
       ▼          ▼          ▼           ▼
    Web App     pytest      CLI        Future
       │                     │
       │                ┌────┴─────┐
       │                ▼          ▼
       │              GHA      pre-commit
       │
       └── interactive authoring
```

Possible future consumers could include:

- IDE integrations
- repository health/coverage reporting
- change-impact tooling
- CDC/change-propagation tooling
- scheduled validation
- automated test-generation tooling

These should only be introduced when there is a demonstrated use case.

---

# Repository Structure

The initial implementation can remain a single repository.

For example:

```text
sql-test-tool/
│
├── src/
│   └── sql_test/
│       ├── engine/
│       │   ├── discovery/
│       │   ├── lineage/
│       │   ├── execution/
│       │   ├── comparison/
│       │   └── validation/
│       │
│       ├── pytest_plugin/
│       ├── cli/
│       └── app/
│
├── .github/
│   └── workflows/
│       └── data-tests.yml
│
├── tests/
└── pyproject.toml
```

There is no immediate need to split the engine, application, pytest integration, and reusable workflow into separate repositories or independently distributed products.

The internal dependency direction should remain:

```text
                 Engine
               ↗   ↑   ↖
              /    │    \
           App    CLI   Pytest
                         │
                         ▼
                        GHA
```

More precisely, GitHub Actions should orchestrate the CLI or pytest interface rather than introducing CI-specific behavior into the engine.

---

# Consuming Repository Footprint

The desired end state is that adopting the framework requires very little framework code inside a data-product repository.

Conceptually:

```text
customer-data/
│
├── sql/
├── schemas/
├── tests/
│   └── data-products/
│       ├── test-case-1
│       └── test-case-2
│
├── data-test.yaml          # only if repo-specific config is needed
│
└── .github/
    └── workflows/
        └── data-tests.yml  # thin reusable-workflow caller
```

There should be **no copied test engine** in the consuming repository.

The goal is:

> Data-product repositories own their data products and test cases. The SQL testing repository owns the machinery used to author, validate, discover, and execute those tests.

---

# Implementation Sequence

The multi-entry-point architecture should not cause all entry points to be built simultaneously.

Recommended sequence:

```text
1. Shared engine / headless execution spike
              ↓
2. Minimal CLI around engine
              ↓
3. Local QA authoring application
              ↓
4. Pytest integration + durable test format
              ↓
5. Reusable GitHub Actions workflow
              ↓
6. Mature discovery / coverage
              ↓
7. Additional execution capabilities
              ↓
8. Much later: pre-commit validation
```

The exact ordering of the application and pytest integration may overlap during the POC because the application must ultimately save tests that pytest can execute.

The important constraint is that each new entry point remains thin and calls the same underlying implementation.

---

# Architectural Principle

The architecture should optimize for **one implementation of test semantics with multiple ways to invoke it**.

Avoid:

```text
Web App Engine
pytest Engine
GHA Engine
pre-commit Engine
```

Prefer:

```text
                 Shared Engine
              /      |       \
             /       |        \
          Web      pytest      CLI
                              /   \
                            GHA   future
                                  pre-commit
```

This minimizes drift between interactive authoring and CI execution while keeping consuming data-product repositories lightweight.