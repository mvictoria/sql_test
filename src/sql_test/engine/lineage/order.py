from graphlib import TopologicalSorter

import sqlglot
from sqlglot import exp


def tables_read(sql: str, dialect: str = "duckdb") -> set[str]:
    return {
        table.name for table in sqlglot.parse_one(sql, read=dialect).find_all(exp.Table)
    }


def execution_order(table: str, sqls: dict[str, str], given: set[str]) -> list[str]:
    upstream: dict[str, set[str]] = {}
    pending = [table]
    while pending:
        current = pending.pop()
        if current in upstream or current in given or current not in sqls:
            continue
        upstream[current] = tables_read(sqls[current])
        pending.extend(upstream[current])
    return [
        name for name in TopologicalSorter(upstream).static_order() if name in upstream
    ]
