# Minimal consuming repository

Standalone copy-paste sample for adopting `sql-test` outside this monorepo.

```bash
cp -R examples/minimal-consumer /tmp/my-data
cd /tmp/my-data
uv sync
uv run pytest
uv run sql-test discover .
```

Requires Python 3.13+. Installs `sql-test` from the floating `@v0` tag (see the main README adopt section). Use `@main` only as a bleeding-edge fallback when that tag is missing.
