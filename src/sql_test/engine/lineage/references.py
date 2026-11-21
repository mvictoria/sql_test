import sqlglot
from sqlglot import exp

from sql_test.engine.relation import Relation


def tables_read(sql: str, dialect: str = "duckdb") -> set[Relation]:
    return {
        Relation.from_table(table, dialect)
        for table in sqlglot.parse_one(sql, read=dialect).find_all(exp.Table)
    }
