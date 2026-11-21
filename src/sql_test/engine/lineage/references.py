from dataclasses import dataclass
from functools import lru_cache

import sqlglot
from sqlglot import exp

from sql_test.engine.relation import Relation


class UnparseableSql(Exception):
    pass


def tables_read(sql: str, dialect: str = "duckdb") -> set[Relation]:
    return set(_reads(sql, dialect).tables)


def ends_in_order_by(sql: str, dialect: str = "duckdb") -> bool:
    return _reads(sql, dialect).ordered


@dataclass(frozen=True)
class _Reads:
    tables: frozenset[Relation]
    ordered: bool


def _reads(sql: str, dialect: str) -> _Reads:
    reads = _parsed(sql, dialect)
    if isinstance(reads, str):
        raise UnparseableSql(reads)
    return reads


@lru_cache(maxsize=65536)
def _parsed(sql: str, dialect: str) -> _Reads | str:
    """What `sql` reads, or why it does not parse; keyed on the text, so an edit misses."""
    try:
        tree = sqlglot.parse_one(sql, read=dialect)
    except sqlglot.errors.SqlglotError as error:
        return str(error)
    ctes = {cte.alias_or_name for cte in tree.find_all(exp.CTE)}
    return _Reads(
        tables=frozenset(
            Relation.from_table(table, dialect)
            for table in tree.find_all(exp.Table)
            if table.db or table.catalog or table.name not in ctes
        ),
        ordered=tree.args.get("order") is not None,
    )
