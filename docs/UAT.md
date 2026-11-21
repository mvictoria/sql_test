# UAT — adoption and first-run findings

User-acceptance pass against the product as a **new consuming-repository adopter**, not a contributor. No product changes were made during the pass; this doc only records what hurt and what worked.

**When:** 2026-11-21
**Method:** follow the README adopt path literally; spin up a greenfield repo (`/tmp/uat-orders-data`: DDL + SELECT SQL + mapping + case folders + pytest); break common things on purpose; drive the authoring app (home → workbench → mock → run → save; settings; empty and broken repos).

Related planning: [ROADMAP.md](ROADMAP.md) pre-release stories from this pass.

---

## Verdict

Once installed and wired like the sample, the happy path is strong: `discover` / `coverage`, pytest over case folders, chained models, and app run-of-an-existing-case all behave well.

**Getting to that happy path is the hard part.** Distribution, first-run packaging, and failure diagnosis block or confuse before a green test appears.

---

## Pain points

Ordered roughly by how much they block a new adopter.

### Blockers / first-hour failures

1. **Documented install does not work.**
   `uv add "sql-test @ git+https://github.com/mvictoria/sql_test.git@v0"` fails: there is no `v0` tag and no GitHub releases. `@main` works as a workaround the README never mentions.

2. **README `uv add` assumes a `[project]` table the sample does not have.**
   Sample `lakehouse-data-customer/pyproject.toml` is only `[tool.sql-test]`. Literal copy → `Project is missing a [project] table`. A consumer also needs something like `[tool.uv] package = false` (or hatch packaging config); none of that is in the adopt section.

3. **Sample consumer is not a standalone project.**
   It runs from the monorepo venv. As a template for “my data repo,” it has no installable deps or own environment story.

4. **No scaffold.**
   No `sql-test init`. Adopters must invent mapping CSV shape, DDL layout, case folder layout, and `conftest.py` + `test_case_folders.py`. README shows snippets; there is no one-command bootstrap.

5. **CI pin uses the same missing tag.**
   Sample workflow calls `mvictoria/sql_test/.github/workflows/data-tests.yml@v0`.

### Misleading / harsh failures

6. **Wrong root-cause messages.**
   Missing DDL, bad `sql_ref`, or a typo’d `sqls=` path often surfaces as `mocks the run never reads: <table>` — not “SQL file missing,” “DDL missing,” or “configured path does not exist.”

7. **Bad mapping headers → raw `KeyError: 'sql_ref'`.**
   No message naming the expected columns (`table_ref`, `sql_ref`; extra columns such as `load_type` are ignored — see [HELPER.md](HELPER.md)).

8. **INSERT-style producer SQL → raw `graphlib.CycleError`.**
   SELECT-style producers work; `INSERT INTO <target> SELECT …` blows up with a traceback. Easy mistake for warehouse SQL authors.

9. **Wrong CSV column names look like a logic failure.**
   Misnamed mock columns → empty actual + “missing” expected rows, not “unknown columns on \<relation\>.”

### Adoption / docs friction

10. **Python 3.14+** is a sharp gate and easy to miss until tooling complains.
    *(Floor later moved to 3.13+ — still call out the requirement in adopt docs.)*

11. **Mapping CSV under-documented in README.**
    HELPER explains `table_ref` / `sql_ref` and ignored extras; the adopt section does not.

12. **“In pipelines” unexplained on first contact.**
    Coverage and the home page show it; the meaning only clicks after lineage vocabulary sinks in.

13. **pytest wiring is mandatory boilerplate** the library does not absorb yet (HELPER notes a collector plugin is deferred). Easy to miss that `discover` ≠ running tests.

14. **Runtime pulls NiceGUI and a large web stack** even for pytest-only CI (~60 packages in a path-installed consumer env). Heavy for “just run CSV cases in CI.”

### Authoring app UX

15. **Blank workbench is usable but dense:** lineage legend, blocked state, empty expected grid, and Case name field with little “name then save” guidance.

16. **Save without a case name errors correctly**, but the Case name field is easy to overlook before Run/Save.

17. **Compliance copy is customer-specific:** “must not contain real **member** data” — odd in a generic FOSS / non-members repo.

18. **Port-in-use** prints “serving at http://…” then dies with a uvicorn bind error — looks like success then failure.

19. **Broken configured paths at runtime** → “Something went wrong” + errno. Creating config via Settings is warmer; a broken checkout is colder.

20. **Accept actual as expected** still missing (README admits it) — after a good Run, expected rows are still hand-built.

---

## What worked

- After path or `@main` install: missing `[tool.sql-test]` keys report clearly.
- Empty repo → `sql-test app` opens **Settings** instead of exiting only with a config error.
- Missing mock → `These relations still need rows: …`
- Missing `expected.csv` → explicit problem string.
- Wrong expected rows → readable `missing` / `unexpected` diff via `result.report()`.
- App: open existing case → Run → **Passed** on the greenfield repo.
- Second model chained off a mocked mid-table passed under pytest without extra ceremony.
- Header-only `expected.csv` (expect no rows) passed when the SQL returned no rows.

---

## Suggested focus for “polish from UAT”

Turned into roadmap stories under **Pre-release — adoption (from UAT)** in [ROADMAP.md](ROADMAP.md):

1. Ship a real floating major tag and align README + sample CI pins — [CI-6](ROADMAP.md#ci-6) (done).
2. Copy-pasteable consumer `pyproject` / standalone sample — [DOC-1](ROADMAP.md#doc-1).
3. `sql-test init` or template — [CLI-7](ROADMAP.md#cli-7).
4. Path / DDL / mapping / INSERT diagnoses — [ENG-35](ROADMAP.md#eng-35).
5. App first-run polish — [APP-20](ROADMAP.md#app-20); accept expected in the UI — [APP-21](ROADMAP.md#app-21).

Massive-repo planning cost stays a parallel track: [ENG-31](ROADMAP.md#eng-31), [ENG-32](ROADMAP.md#eng-32).

---

## Reproduce the greenfield check

Sketch of the repo that eventually went green (after abandoning `@v0` for a path or `@main` install):

```text
uat-orders-data/
├── admin/sqls/                 # DDL + open_orders.sql (SELECT …)
├── admin/config/lookup_sql_table_mapping.csv
├── tests/cases/<table>/<case>/{mocks…, expected.csv}
├── tests/conftest.py           # Engine + DuckDBExecutor from RepositoryConfig
├── tests/test_case_folders.py  # parametrize case_folders(...)
└── pyproject.toml              # [project] + [tool.uv] package = false + [tool.sql-test]
```

Commands that mattered once install worked: `uv run sql-test discover .`, `uv run sql-test coverage .`, `uv run pytest`, `uv run sql-test app .`.
