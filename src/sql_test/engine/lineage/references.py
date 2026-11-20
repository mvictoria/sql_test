import sqlglot
from sqlglot import exp


def tables_read(sql: str, dialect: str = "duckdb") -> set[str]:
    return {
        table.name for table in sqlglot.parse_one(sql, read=dialect).find_all(exp.Table)
    }
