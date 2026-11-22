from nicegui import ui

from sql_test.engine import Catalog


def sql_view(repo_catalog: Catalog, target: str) -> None:
    """Read-only producer SQL — workbench hides mock editor chrome in this view."""
    with ui.column().classes("w-full gap-2").mark("sql-read"):
        ui.label("Producer SQL").classes("text-subtitle1")
        ui.label("Read-only — switch back to lineage to edit mocks and run.").classes(
            "text-caption text-grey-8"
        ).mark("sql-read-hint")
        operations = repo_catalog.producers(repo_catalog.resolve(target))
        if not operations:
            ui.label("No producer SQL").classes("text-grey-7").mark("sql-empty")
            return
        for operation in operations:
            ui.label(operation.sql_file.name).classes("text-subtitle1").mark("sql-file")
            ui.code(operation.sql, language="sql").classes("w-full").mark("sql-code")
