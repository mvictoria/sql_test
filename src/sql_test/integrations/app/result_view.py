from collections.abc import Callable

from nicegui import ui

from sql_test.engine import Row, RunResult
from sql_test.integrations.app.compare_view import DiffPanel
from sql_test.integrations.app.state import RESULT_VIEWS, WorkbenchState

_REMOVED = "background:#ffeef0"
_ADDED = "background:#e6ffed"
_DIFFERING = "background:#fff3cd;font-weight:600"


def result_view(state: WorkbenchState, on_switch: Callable[[str], None]) -> None:
    result, panel = state.run_result, state.panel
    if result is None or panel is None:
        return
    view = state.result_view if state.result_view in RESULT_VIEWS else "output"
    with ui.column().classes("w-full").mark(f"result result-view-{view}"):
        _verdict(panel)
        with ui.row():
            for name, label in (("output", "Output"), ("diff", "Diff")):
                button = ui.button(
                    label, on_click=lambda _, name=name: on_switch(name)
                ).mark(f"result-{name}")
                button.props("unelevated" if name == view else "outline")
        if view == "output":
            _output(result)
        else:
            _diff(panel)


def _verdict(panel: DiffPanel) -> None:
    if panel.passed:
        ui.label("Passed").classes("text-h6 text-green-9").mark("verdict-passed")
    elif not panel.has_expected:
        ui.label("Failed — add expected rows").classes("text-h6 text-red-9").mark(
            "verdict-failed"
        )
    else:
        ui.label("Failed").classes("text-h6 text-red-9").mark("verdict-failed")


def _output(result: RunResult) -> None:
    ui.label("Output").classes("text-subtitle1")
    rows = result.rows
    if not rows:
        ui.label("No rows").classes("text-grey-7").mark("output-rows-0")
        return
    columns = list(rows[0].keys())
    with ui.grid(columns=f"repeat({len(columns)}, 10rem)").mark(
        f"output-rows-{len(rows)}"
    ):
        for name in columns:
            ui.label(name).classes("text-caption text-weight-bold")
        for row in rows:
            for name in columns:
                ui.label(_text(row.get(name)))


def _diff(panel: DiffPanel) -> None:
    ui.label("Diff").classes("text-subtitle1")
    comparison = panel.comparison
    if comparison is None:
        ui.label("Add expected rows to see a diff").classes("text-grey-7").mark(
            "diff-empty"
        )
        return
    if not (comparison.changed or comparison.missing or comparison.unexpected):
        ui.label("No differences").classes("text-grey-7").mark("diff-clean")
        return
    columns = panel.columns
    ui.label(
        "− missing / old · + added / new — expected is editable in the Expected grid"
    ).classes("text-caption text-grey-8")
    with ui.grid(columns=f"2rem repeat({len(columns)}, 10rem)").classes(
        "gap-0 font-mono"
    ):
        ui.label("")
        for name in columns:
            ui.label(name).classes("text-caption text-weight-bold")
        for change in comparison.changed:
            ui.label("@@ changed @@").classes("text-indigo-9 text-weight-bold").style(
                "grid-column: 1 / -1"
            ).mark("diff-hunk diff-changed")
            _diff_row(
                "-", change.expected, columns, change.differing_columns, "changed"
            )
            _diff_row("+", change.actual, columns, change.differing_columns, "changed")
        for row in comparison.missing:
            _diff_row("-", row, columns, (), "missing")
        for row in comparison.unexpected:
            _diff_row("+", row, columns, (), "added")


def _diff_row(
    marker: str,
    row: Row,
    columns: tuple[str, ...],
    differing: tuple[str, ...],
    outcome: str,
) -> None:
    side = "diff-removed" if marker == "-" else "diff-added"
    background = _REMOVED if marker == "-" else _ADDED
    markers = f"diff-row diff-{outcome} {side}"
    ui.label(marker).style(background).mark(markers)
    for name in columns:
        style = background + (";" + _DIFFERING if name in differing else "")
        ui.label(_text(row.get(name))).style(style).mark(markers)


def _text(value: object) -> str:
    return "" if value is None else str(value)
