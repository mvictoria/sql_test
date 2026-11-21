from pathlib import Path
from urllib.parse import quote

from nicegui import ui

from sql_test.engine import Catalog
from sql_test.integrations.config import RepositoryConfig
from sql_test.integrations.discover import Discovery, discover
from sql_test.testing import coverage_report, pipeline_cases


def home_page(repository: Path, pipelines: str | None = None) -> None:
    catalog = RepositoryConfig.load(repository).catalog()
    result = discover(repository, catalog)
    if pipelines:
        _pipelines_page(result, catalog, pipelines)
        return
    ui.label("sql-test").classes("text-h5")
    _tables(result, catalog)
    _cases(result)


def _tables(result: Discovery, catalog: Catalog) -> None:
    tables = (*result.models, *result.sources)
    report = coverage_report(tables, result.cases, catalog)
    models = set(result.models)
    ui.label("Tables").classes("text-subtitle1")
    if not report:
        ui.label("None").classes("text-grey-7")
        return
    with ui.grid(columns="minmax(16rem, auto) 6rem 9rem").classes("items-center"):
        for heading in ("Table", "Tests", "In pipelines"):
            ui.label(heading).classes("text-caption text-weight-bold")
        for row in report:
            with ui.row().classes("items-baseline gap-2"):
                ui.link(
                    row.table, f"/workbench?target={quote(row.table, safe='')}"
                ).mark(f"table-{row.table}")
                ui.label("model" if row.table in models else "source").classes(
                    "text-caption text-grey-7"
                )
            ui.label(str(row.tests)).mark(f"tests-{row.table}")
            if row.pipelines:
                ui.link(
                    str(row.pipelines), f"/?pipelines={quote(row.table, safe='')}"
                ).mark(f"pipelines-{row.table}")
            else:
                ui.label("0").mark(f"pipelines-{row.table}")


def _cases(result: Discovery) -> None:
    ui.label("Cases").classes("text-subtitle1")
    if not result.cases:
        ui.label("None").classes("text-grey-7")
        return
    for case in result.cases:
        ui.link(
            f"{case.target} / {case.name}", _case_href(case.target, case.name)
        ).mark(f"case-{case.target}/{case.name}")


def _pipelines_page(result: Discovery, catalog: Catalog, table: str) -> None:
    if table not in {*result.models, *result.sources}:
        ui.link("← sql-test", "/")
        ui.label(f"Unknown table {table}").mark("not-found")
        return
    ui.link("← sql-test", "/").mark("home-link")
    ui.label(f"In pipelines — {table}").classes("text-h5")
    ui.label("Cases that execute this table without targeting it.")
    cases = pipeline_cases(table, result.cases, catalog)
    if not cases:
        ui.label("None").classes("text-grey-7")
    for case in cases:
        ui.link(
            f"{case.target} / {case.name}", _case_href(case.target, case.name)
        ).mark(f"pipeline-case-{case.target}/{case.name}")


def _case_href(target: str, name: str) -> str:
    return f"/workbench?case={quote(f'{target}/{name}', safe='')}"
