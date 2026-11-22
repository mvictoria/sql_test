from pathlib import Path
from urllib.parse import quote

from nicegui import ui

from sql_test.engine import Catalog
from sql_test.integrations.config import RepositoryConfig
from sql_test.integrations.discover import Discovery, discover
from sql_test.testing import CaseSummary, CoverageRow, coverage_report, pipeline_cases


def home_page(repository: Path, pipelines: str | None = None) -> None:
    catalog = RepositoryConfig.load(repository).catalog()
    result = discover(repository, catalog)
    if pipelines:
        _pipelines_page(result, catalog, pipelines)
        return
    with ui.row().classes("items-baseline gap-4"):
        ui.label("sql-test").classes("text-h5")
        ui.link("Settings", "/settings").mark("settings-link")
    cases_by_target = _cases_by_target(result)
    model_report = coverage_report(result.models, result.cases, catalog)
    source_report = coverage_report(result.sources, result.cases, catalog)
    with ui.column().classes("gap-2").mark("home-tables"):
        ui.label("Tables").classes("text-subtitle1")
        _coverage_grid(
            model_report, cases_by_target, link_targets=True, pipelines_gloss=True
        )
    with ui.column().classes("gap-2").mark("home-sources"):
        ui.label("Sources").classes("text-subtitle1")
        _coverage_grid(source_report, cases_by_target, link_targets=False)


def _coverage_grid(
    report: list[CoverageRow],
    cases_by_target: dict[str, tuple[CaseSummary, ...]],
    *,
    link_targets: bool,
    pipelines_gloss: bool = False,
) -> None:
    if not report:
        ui.label("None").classes("text-grey-7")
        return
    with ui.grid(columns="minmax(16rem, auto) 6rem 9rem minmax(12rem, 1fr)").classes(
        "items-center"
    ):
        for heading in ("Table", "Tests", "In pipelines", "Cases"):
            label = ui.label(heading).classes("text-caption text-weight-bold")
            if heading == "In pipelines" and pipelines_gloss:
                with label:
                    ui.tooltip(
                        "Cases that execute this table without targeting it."
                    ).mark("pipelines-gloss")
        for row in report:
            if link_targets:
                ui.link(
                    row.table, f"/workbench?target={quote(row.table, safe='')}"
                ).mark(f"table-{row.table}")
            else:
                ui.label(row.table).mark(f"table-{row.table}")
            ui.label(str(row.tests)).mark(f"tests-{row.table}")
            if row.pipelines:
                ui.link(
                    str(row.pipelines), f"/?pipelines={quote(row.table, safe='')}"
                ).mark(f"pipelines-{row.table}")
            else:
                ui.label("0").mark(f"pipelines-{row.table}")
            with ui.column().classes("gap-0").mark(f"table-cases-{row.table}"):
                for case in cases_by_target.get(row.table, ()):
                    ui.link(case.name, _case_href(case.target, case.name)).mark(
                        f"table-case-{case.target}/{case.name}"
                    )
                if not cases_by_target.get(row.table):
                    ui.label("—").classes("text-grey-7")


def _cases_by_target(result: Discovery) -> dict[str, tuple[CaseSummary, ...]]:
    grouped: dict[str, list[CaseSummary]] = {}
    for case in result.cases:
        grouped.setdefault(case.target, []).append(case)
    return {target: tuple(cases) for target, cases in grouped.items()}


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
