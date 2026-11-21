from nicegui import ui

from sql_test.engine import Catalog


def sql_view(repo_catalog: Catalog, target: str) -> None:
    operations = repo_catalog.producers(repo_catalog.resolve(target))
    if not operations:
        ui.label("No producer SQL").classes("text-grey-7").mark("sql-empty")
        return
    for operation in operations:
        ui.label(operation.sql_file.name).classes("text-subtitle1").mark("sql-file")
        ui.code(operation.sql, language="sql").classes("w-full").mark("sql-code")
