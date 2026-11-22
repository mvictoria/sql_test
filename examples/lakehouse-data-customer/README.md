# Lakehouse sample (chained SQL)

Richer consumer example than [minimal-consumer](../minimal-consumer/): several models, mocks across tables, both inline `test_sql.py` and case folders.

```bash
cp -R examples/lakehouse-data-customer /tmp/lakehouse-demo
cd /tmp/lakehouse-demo
uv sync
uv run pytest
uv run sql-test discover .
uv run sql-test app .
```

Requires Python 3.13+. Installs `sql-test` from the floating `@v0` tag.
