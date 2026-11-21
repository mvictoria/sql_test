import sqlglot
from sqlglot import exp

from sql_test.engine.relation import Relation


def tables_read(sql: str, dialect: str = "duckdb") -> set[Relation]:
    tree = sqlglot.parse_one(sql, read=dialect)
    ctes = {cte.alias_or_name for cte in tree.find_all(exp.CTE)}
    return {
        Relation.from_table(table, dialect)
        for table in tree.find_all(exp.Table)
        if table.db or table.catalog or table.name not in ctes
    }
