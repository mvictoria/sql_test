import html
from pathlib import Path

from sql_test.integrations.app.engine_access import catalog


def sql_section(repository: Path, target: str) -> str:
    repo_catalog = catalog(repository)
    operations = repo_catalog.producers(repo_catalog.resolve(target))
    if not operations:
        return "<h2>SQL</h2><p class='empty'>No producer SQL</p>"
    blocks = "".join(
        (
            f"<h2>{html.escape(operation.sql_file.name)}</h2>"
            f"<pre><code>{html.escape(operation.sql)}</code></pre>"
        )
        for operation in operations
    )
    return blocks
