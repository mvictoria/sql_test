# AGENTS.md

A library for testing SQL transformations: mock upstream tables, run the real SQL, compare the output. Tests are case folders of CSVs that pytest runs through one shared engine.

## Docs

- **Design decisions** (case format, lineage, mocking, coverage, architecture): [docs/HELPER.md](docs/HELPER.md). Read it before changing engine behaviour or the case format.
- **Work items (source of truth):** [GitHub issues](https://github.com/mvictoria/sql_test/issues) titled `ID: …`, with area labels (`engine`, `user-interface`, `ci-cd`, …). Find the open issue before starting work; close it when the PR lands. Scope changes go on the issue.
- **Product roadmap:** [docs/ROADMAP.md](docs/ROADMAP.md) — shipped capabilities and planned *features* by theme/version, not task breakdown. Follow its horizon (Spark → incremental → richer lineage; Later items stay Later unless an issue is in progress).

## Way of working

- **TDD.** Each story starts with a failing test for its done-when. Write the code that makes it pass, then refactor, one behaviour per red/green cycle.
- **DDD.** Code uses the domain's words: table under test, case, mock, source, producer, lineage, plan, execution boundary. Name modules, types, and functions after them. A new term is defined in [docs/HELPER.md](docs/HELPER.md) before it appears in code. Source means source→target QA language, not a separate "boundary" relation type.
- **Ship on a PR.** Push the branch and open (or update) a pull request; do not leave finished work only local. The PR body is for humans: succinct — what changed, why, and which issue/story ID it serves (`Fixes #N` when applicable). Authoring-app (APP-*) PRs embed UI: screenshot the changed screen from the worktree app, commit it under `docs/screenshots/<story-id>/`, and show it in the PR body.
- **Keep the PR mergeable.** Before pushing, fetch and rebase the branch onto `origin/main` locally, resolve any conflicts commit by commit, and rerun prek and pytest. History stays linear: no merge commits on the branch. Push a rebased branch with `git push --force-with-lease`. Check that the PR shows as mergeable after pushing.
- **Release via the PR title.** To cut a package release when the PR lands, start the PR title with `(major)`, `(minor)`, or `(patch)` as the first word (case-insensitive; for example `(patch) CI-2: versioned releases`). After merge onto `main`, [`.github/workflows/cd.yml`](.github/workflows/cd.yml) tags **that new `main` tip** (not the pre-rebase branch SHAs), then builds and publishes from the tag. Omit the token if the PR should not release. Details: [README.md](README.md) (Releases) and [docs/HELPER.md](docs/HELPER.md) (Versioning).

## Conventions

- One story per commit, message prefixed with its ID: `ENG-1: package skeleton`.
- Layers import in one direction, as laid out in [docs/HELPER.md](docs/HELPER.md): `engine` (catalog, lineage, planner) imports no other layer; `executors` import only the engine's executor interface; `testing` imports the engine; `integrations` wire them together. `tests/test_layers.py` enforces this.
- The engine is handed an executor and never imports one. Executors know SQL and rows, not lineage or case folders.
- SQL-engine-specific behaviour stays inside an executor. DuckDB is the tentative executor; Spark replaces it later behind the same interface.
- The engine is always given a repository path. Adopt sample: `examples/minimal-consumer/`. Richer chained-SQL fixture: `tests/fixtures/repos/lakehouse-data-customer/`.

## Gotchas

- Fixture repositories are data. pytest skips `tests/fixtures/`; run a fixture's own tests by path in a separate pytest run, because two `test_sql.py` files collide in one session.
- `prek run` fixes files and can still print `Passed`. Check `git status` after running it.
- Fixtures with deliberately unparseable SQL need excluding from the sqlfluff hook in `prek.toml`.
