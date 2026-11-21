import html
from pathlib import Path

from sql_test.engine.catalog.mapping import read_operations
from sql_test.engine.relation import Relation
from sql_test.integrations.discover import MAPPING, SQLS


def sql_section(repository: Path, target: str) -> str:
    relation = Relation.parse(target)
    operations = [
        operation
        for operation in read_operations(repository / MAPPING, repository / SQLS)
        if operation.writes == relation
    ]
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
