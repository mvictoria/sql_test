# Contributing

## Setup (this repository)

Requires Python 3.13+.

```bash
uv sync --extra spark
```

Spark tests need a JVM 17+ (OpenJDK works). Omit `--extra spark` for a DuckDB-only install; Spark-parametrized tests then skip.

## Tests

```bash
uv run pytest
```

Fixture repositories under `tests/fixtures/` are skipped by the default pytest run. Run a fixture's own tests by path in a separate session, for example:

```bash
uv run pytest tests/fixtures/repos/lakehouse-data-customer/tests
```

## Releases

The git tag is the version (`dynamic` via hatchling / `uv-dynamic-versioning`).

1. Start the **PR title** with `(major)`, `(minor)`, or `(patch)` as the first word when that PR should release (case-insensitive; example: `(patch) CI-2: versioned releases`). Later mentions are ignored. Skip the token if it should not release.
2. Merge with linear history (rebase). CD runs on `main`, finds the merged PR, and tags **`main`'s new tip** — not the old branch commits.
3. CD tags **`main`'s tip**, builds the wheel/sdist, creates/updates the GitHub Release, and moves floating `vX` (for example `v0`) in that same run — a bot tag push alone does not start a second workflow.

Manual tag push (`git tag vX.Y.Z && git push origin vX.Y.Z`) still runs the release job.

Way of working for agents and humans shipping changes: [AGENTS.md](../AGENTS.md).
