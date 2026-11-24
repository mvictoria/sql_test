# Spark consuming repository

Same footprint as [minimal-consumer](../minimal-consumer/), but the engine uses `SparkExecutor` instead of DuckDB. Needs a JVM 17+ (OpenJDK works) and the `spark` optional extra.

```bash
cp -R examples/spark-example /tmp/spark-demo
cd /tmp/spark-demo
uv sync
uv run pytest
uv run sql-test discover .
```

From this monorepo (after `uv sync --extra spark`):

```bash
uv run pytest examples/spark-example/tests
```

Requires Python 3.13+. Installs `sql-test[spark]` from the floating `@v0` tag. Use `@main` only as a bleeding-edge fallback when that tag is missing.
