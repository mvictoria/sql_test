# sql-test

## v0

Tests run the SQL files in `sqls/` on DuckDB. Each test gets its own in-memory database. The test is parametrized with the rows to insert and the table name, `insert_test_data` loads that table, and the test runs the SQL it cares about and checks the result.

Chained queries are wired by hand. The Alice test loads `members`, runs `medicaid_members.sql` into a `medicaid_members` table, then runs `medicaid_members_named_alice.sql`.

## Later

No particular order:

- A test gives the table under test and the data to insert. Intermediates are found automatically (sqlglot is a candidate) and run in order.
- Test cases may live in their own folders, which a test discovers. Each case has upstream data and expected data.
