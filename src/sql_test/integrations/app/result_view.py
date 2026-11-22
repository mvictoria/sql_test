from collections.abc import Callable

from nicegui import ui

from sql_test.engine import Row, RunResult, Schema
from sql_test.integrations.app.accept import (
    ExpectedRows,
    accept_all,
    accept_cell,
    accept_row,
    remove_row,
)
from sql_test.integrations.app.compare_view import DiffPanel, target_schema
from sql_test.integrations.app.state import RESULT_VIEWS, WorkbenchState

_REMOVED = "background:#ffeef0"
_ADDED = "background:#e6ffed"
_DIFFERING = "background:#fff3cd;font-weight:600"

type OnAccept = Callable[[ExpectedRows], None]


def _accept_all(schema: Schema, rows: list[Row], on_accept: OnAccept) -> None:
    """Accept actual as expected; empty actual needs an explicit confirm (UAT-8)."""
    if rows:
        on_accept(accept_all(schema, rows))
        return
    with ui.dialog() as dialog, ui.card().classes("gap-2"):
        ui.label(
            "Actual has no rows. Set expected to no rows? "
            "A filter or mock mistake can empty the result."
        ).mark("accept-empty-prompt")
        with ui.row().classes("gap-2"):
            ui.button("Cancel", on_click=dialog.close).props("flat").mark(
                "accept-empty-cancel"
            )
            ui.button(
                "Expect no rows",
                on_click=lambda: (on_accept(accept_all(schema, [])), dialog.close()),
            ).props("unelevated color=positive").mark("accept-empty-confirm")
    dialog.open()


def result_view(
    state: WorkbenchState, on_switch: Callable[[str], None], on_accept: OnAccept
) -> None:
    result, panel = state.run_result, state.panel
    if result is None or panel is None:
        return
    view = state.result_view if state.result_view in RESULT_VIEWS else "output"
    schema = target_schema(state.catalog, state.target)
    with ui.column().classes("w-full").mark(f"result result-view-{view}"):
        _verdict(panel)
        with ui.row():
            for name, label in (("output", "Output"), ("diff", "Diff")):
                button = ui.button(
                    label, on_click=lambda _, name=name: on_switch(name)
                ).mark(f"result-{name}")
                button.props("unelevated" if name == view else "outline")
            if schema is not None and not panel.passed:
                ui.button(
                    "Expect no rows" if not result.rows else "Accept all actual",
                    on_click=lambda: _accept_all(schema, result.rows, on_accept),
                ).props("outline color=positive").mark("accept-all")
        if view == "output":
            _output(result)
        elif schema is None:
            _diff(panel, None)
        else:
            expected = state.grid_rows.get("expected", [{}])
            _diff(panel, _Acceptor(schema, expected, on_accept))


class _Acceptor:
    """Turns a click on a diff row into new expected rows."""

    def __init__(
        self, schema: Schema, expected: ExpectedRows, on_accept: OnAccept
    ) -> None:
        self.schema, self.expected, self.on_accept = schema, expected, on_accept

    def row(self, actual: Row, replacing: Row | None = None) -> None:
        self.on_accept(
            accept_row(self.expected, self.schema, actual, replacing=replacing)
        )

    def cell(self, expected: Row, column: str, value: object) -> None:
        self.on_accept(accept_cell(self.expected, self.schema, expected, column, value))

    def remove(self, expected: Row) -> None:
        self.on_accept(remove_row(self.expected, self.schema, expected))


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


def _diff(panel: DiffPanel, acceptor: _Acceptor | None) -> None:
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
        "− missing / old · + added / new — click a highlighted cell to accept it,"
        " or edit expected in the Expected grid"
    ).classes("text-caption text-grey-8")
    with ui.grid(columns=f"2rem repeat({len(columns)}, 10rem) auto").classes(
        "gap-0 font-mono items-center"
    ):
        ui.label("")
        for name in columns:
            ui.label(name).classes("text-caption text-weight-bold")
        ui.label("")
        for index, change in enumerate(comparison.changed):
            ui.label("@@ changed @@").classes("text-indigo-9 text-weight-bold").style(
                "grid-column: 1 / -1"
            ).mark("diff-hunk diff-changed")
            _diff_row(
                "-", change.expected, columns, change.differing_columns, "changed"
            )
            ui.label("")
            cells = _diff_row(
                "+", change.actual, columns, change.differing_columns, "changed"
            )
            if acceptor is None:
                ui.label("")
                continue
            for name in change.differing_columns:
                cells[name].on(
                    "click",
                    lambda _, old=change.expected, name=name, new=change.actual: (
                        acceptor.cell(old, name, new.get(name))
                    ),
                ).classes("cursor-pointer").tooltip("Accept this cell").mark(
                    f"diff-row diff-changed diff-added accept-cell-changed-{index}-{name}"
                )
            _action(
                "Accept row",
                f"accept-row-changed-{index}",
                lambda _, old=change.expected, new=change.actual: acceptor.row(
                    new, replacing=old
                ),
            )
        for index, row in enumerate(comparison.missing):
            _diff_row("-", row, columns, (), "missing")
            if acceptor is None:
                ui.label("")
                continue
            _action(
                "Remove",
                f"remove-row-missing-{index}",
                lambda _, row=row: acceptor.remove(row),
            )
        for index, row in enumerate(comparison.unexpected):
            _diff_row("+", row, columns, (), "added")
            if acceptor is None:
                ui.label("")
                continue
            _action(
                "Accept row",
                f"accept-row-added-{index}",
                lambda _, row=row: acceptor.row(row),
            )


def _diff_row(
    marker: str,
    row: Row,
    columns: tuple[str, ...],
    differing: tuple[str, ...],
    outcome: str,
) -> dict[str, ui.label]:
    side = "diff-removed" if marker == "-" else "diff-added"
    background = _REMOVED if marker == "-" else _ADDED
    markers = f"diff-row diff-{outcome} {side}"
    ui.label(marker).style(background).mark(markers)
    cells: dict[str, ui.label] = {}
    for name in columns:
        style = background + (";" + _DIFFERING if name in differing else "")
        cells[name] = ui.label(_text(row.get(name))).style(style).mark(markers)
    return cells


def _action(label: str, marker: str, on_click: Callable) -> None:
    ui.button(label, on_click=on_click).props("flat dense no-caps").mark(marker)


def _text(value: object) -> str:
    return "" if value is None else str(value)
