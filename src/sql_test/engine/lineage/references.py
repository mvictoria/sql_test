import sqlglot
from sqlglot import exp

from sql_test.engine.relation import Relation


class UnparseableSql(Exception):
    pass


def tables_read(sql: str, dialect: str = "duckdb") -> set[Relation]:
    try:
        tree = sqlglot.parse_one(sql, read=dialect)
    except sqlglot.errors.SqlglotError as error:
        raise UnparseableSql(str(error)) from error
    ctes = {cte.alias_or_name for cte in tree.find_all(exp.CTE)}
    return {
        Relation.from_table(table, dialect)
        for table in tree.find_all(exp.Table)
        if table.db or table.catalog or table.name not in ctes
    }


def ends_in_order_by(sql: str, dialect: str = "duckdb") -> bool:
    try:
        tree = sqlglot.parse_one(sql, read=dialect)
    except sqlglot.errors.SqlglotError as error:
        raise UnparseableSql(str(error)) from error
    return tree.args.get("order") is not None
