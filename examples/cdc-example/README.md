# CDC example

Consumer sample focused on incremental/CDC testing, plus chained full-load models. The **merge** model `seen` uses history in `events.csv`, batch changes in `delta/events.csv`, then historic + CDC runs — case `seen/absorb_new_events`.

```bash
cp -R examples/cdc-example /tmp/cdc-demo
cd /tmp/cdc-demo
uv sync
uv run pytest
uv run sql-test discover .
uv run sql-test app .
```

Requires Python 3.13+. Installs `sql-test` from the floating `@v0` tag.
