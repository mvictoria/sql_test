from pathlib import Path

from sql_test.engine.catalog.catalog import Catalog
from sql_test.engine.catalog.ddl import read_ddl_schemas
from sql_test.engine.catalog.mapping import read_operations


def mapped_sql_folder(
    sqls: Path, mapping: Path, schemas: Path | None = None
) -> Catalog:
    discovered = read_ddl_schemas(schemas or sqls)
    return Catalog(
        operations=read_operations(mapping, sqls),
        schemas=discovered.schemas,
        problems=discovered.problems,
    )
