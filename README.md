# sql-test

## v0

The v0 tests live in `lakehouse-data-customer/`, a sample consuming repository kept here for now; the tool must not assume it is present. Its tests run the SQL files in `admin/sqls/` on DuckDB. Each test gets its own in-memory database. The test is parametrized with the rows to insert and the table name, `insert_test_data` loads that table, and the test runs the SQL it cares about and checks the result.

Chained queries are wired by hand. The Alice test loads `members`, runs `medicaid_members.sql` into a `medicaid_members` table, then runs `medicaid_members_named_alice.sql`.

## Helper

A local GUI for building and running test cases without writing Python. Details are in [docs/HELPER.md](docs/HELPER.md).

- Browse models, tables, and saved cases
- Coverage per model and per table
- View lineage of the selected model, see what has been mocked and what still needs test data
- Edit input data and view output after a run
- Save, load, and execute test cases

## Roadmap

Planned versions, features, and stories are in [docs/ROADMAP.md](docs/ROADMAP.md).

## Later

No particular order:

- A test gives the table under test and the data to insert. Intermediates are found automatically (sqlglot is a candidate) and run in order.
- Test cases may live in their own folders, which a test discovers. Each case has upstream data and expected data.
