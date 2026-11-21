from pathlib import Path

from nicegui import ui

from sql_test.integrations.app.case_load import case_grid_rows, load_case
from sql_test.integrations.app.case_save import SaveError, save_case
from sql_test.integrations.app.compare_view import compare_section
from sql_test.integrations.app.engine_access import run as run_case
from sql_test.integrations.app.grid import apply_grid_action, type_grid_rows
from sql_test.integrations.app.grid_view import EditorActions, editor_view
from sql_test.integrations.app.lineage_view import lineage_view
from sql_test.integrations.app.mocks import frontier_mocks, toggled_mocks
from sql_test.integrations.app.result_view import result_view
from sql_test.integrations.app.sql_view import sql_view
from sql_test.integrations.app.state import (
    DEFAULT_RESULT_VIEW,
    DEFAULT_VIEW,
    RESULT_VIEWS,
    VIEWS,
    Message,
    WorkbenchState,
)
from sql_test.integrations.discover import Discovery, discover


def open_workbench(
    repository: Path, query: dict[str, list[str]]
) -> WorkbenchState | None:
    """The workbench a deep link asks for, or None when the link names nothing."""
    result = discover(repository)
    case_name: str | None = None
    if query.get("case"):
        raw = query["case"][0]
        if "/" not in raw:
            return None
        target, case_name = raw.split("/", 1)
        if not _has_case(result, target, case_name):
            return None
    elif query.get("target"):
        target = query["target"][0]
        if target not in result.models and target not in result.sources:
            return None
    else:
        return None
    view = query.get("view", [DEFAULT_VIEW])[0]
    saved = load_case(repository, target, case_name) if case_name is not None else None
    grid_rows: dict[str, list[dict[str, str]]] = {}
    mock_params = tuple(sorted({name for name in query.get("mock", []) if name}))
    if saved is not None:
        grid_rows = case_grid_rows(saved)
    if saved is not None and not mock_params:
        requested = tuple(sorted(str(relation) for relation in saved.mocks))
    else:
        requested = mock_params
    mocks = frontier_mocks(repository, target, requested)
    return WorkbenchState(
        repository=repository,
        target=target,
        case_name=case_name,
        mocks=mocks,
        grid_rows=apply_grid_action("", mocks, grid_rows),
        view=view if view in VIEWS else DEFAULT_VIEW,
    )


def _has_case(result: Discovery, target: str, name: str) -> bool:
    return any(case.target == target and case.name == name for case in result.cases)


class Workbench:
    """One open workbench page: its state, and the containers its actions rebuild."""

    def __init__(self, state: WorkbenchState) -> None:
        self.state = state
        self.actions = EditorActions(
            on_edit=self.refresh_lineage,
            on_add_row=self.add_row,
            on_delete_row=self.delete_row,
            on_apply=self.apply,
            on_run=self.run,
            on_save=self.save,
        )

    def build(self) -> None:
        ui.link("← sql-test", "/").mark("home-link")
        ui.label("Workbench").classes("text-h5")
        self.summary = ui.column().classes("gap-0")
        self.body = ui.column().classes("w-full")
        self.status = ui.column().classes("gap-0")
        self.result = ui.column().classes("w-full")
        self.editor = ui.column().classes("w-full")
        self.refresh()

    def refresh(self) -> None:
        self.refresh_summary()
        self.refresh_body()
        self.refresh_status()
        self.refresh_result()
        self.refresh_editor()

    def refresh_summary(self) -> None:
        state = self.state
        self.summary.clear()
        with self.summary:
            with ui.row().classes("gap-1"):
                ui.label("Table under test:")
                ui.label(state.target).classes("text-weight-bold").mark("target")
            if state.case_name:
                with ui.row().classes("gap-1"):
                    ui.label("Case:")
                    ui.label(state.case_name).classes("text-weight-bold").mark(
                        "case-label"
                    )
            if state.mocks:
                ui.label("Mocks: " + ", ".join(state.mocks)).mark("mocks")

    def refresh_body(self) -> None:
        self.body.clear()
        with self.body:
            with ui.row():
                for name in VIEWS:
                    button = ui.button(
                        name, on_click=lambda _, name=name: self.show_view(name)
                    ).mark(f"view-{name}")
                    button.props("unelevated" if name == self.state.view else "outline")
            if self.state.view == "lineage":
                lineage_view(self.state, self.toggle_mock)
            else:
                sql_view(self.state.repository, self.state.target)

    def refresh_lineage(self) -> None:
        """Cheap refresh for typing: Ready / Blocked follows the filled rows."""
        if self.state.view == "lineage":
            self.refresh_body()

    def refresh_status(self) -> None:
        self.status.clear()
        message = self.state.message
        if message is None:
            return
        with self.status:
            colour = "text-green-9" if message.ok else "text-orange-9"
            ui.label(message.text).classes(colour).mark(
                f"status-{'ok' if message.ok else 'error'} {message.marker}"
            )
            if message.detail:
                ui.label(message.detail).classes("text-caption text-grey-7").mark(
                    "status-detail"
                )

    def refresh_result(self) -> None:
        self.result.clear()
        with self.result:
            result_view(self.state, self.show_result_view)

    def refresh_editor(self) -> None:
        self.editor.clear()
        with self.editor:
            editor_view(self.state, self.actions)

    def show_view(self, name: str) -> None:
        self.state.view = name
        self.refresh_body()

    def show_result_view(self, name: str) -> None:
        self.state.result_view = name
        self.refresh_result()

    def toggle_mock(self, name: str) -> None:
        state = self.state
        requested = toggled_mocks(state.mocks, name)
        state.mocks = frontier_mocks(state.repository, state.target, requested)
        state.grid_rows = apply_grid_action("", state.mocks, state.grid_rows)
        self._reset_results()
        self.refresh()

    def add_row(self, table: str) -> None:
        self._grid_action(f"add:{table}")

    def delete_row(self, table: str, index: int) -> None:
        self._grid_action(f"delete:{table}:{index}")

    def _grid_action(self, action: str) -> None:
        state = self.state
        state.grid_rows = apply_grid_action(action, state.mocks, state.grid_rows)
        self._reset_results()
        self.refresh()

    def _reset_results(self) -> None:
        self.state.run_result = None
        self.state.panel = None
        self.state.message = None

    def apply(self) -> None:
        state = self.state
        self._reset_results()
        mocked = {name: state.grid_rows.get(name, []) for name in state.mocks}
        try:
            typed, state.engine_types = type_grid_rows(state.repository, mocked)
            state.grid_rows.update(typed)
            state.message = Message(
                "Reached engine — mock rows loaded with schema types", ok=True
            )
        except Exception as error:  # noqa: BLE001 — show engine failures in the page
            state.message = Message(f"Could not load mocks: {error}", ok=False)
        self.refresh()

    def run(self) -> None:
        state = self.state
        self._reset_results()
        try:
            result = run_case(
                state.repository, state.target, state.mocks, state.grid_rows
            )
            panel = compare_section(
                state.repository,
                state.target,
                state.grid_rows.get("expected", [{}]),
                result.rows,
            )
            state.run_result, state.panel = result, panel
            if not panel.passed:
                state.result_view = "diff"
            elif state.result_view not in RESULT_VIEWS:
                state.result_view = DEFAULT_RESULT_VIEW
            state.message = Message("Run complete", ok=True)
        except Exception as error:  # noqa: BLE001 — show engine failures in the page
            state.message = Message(f"Could not run: {error}", ok=False)
        self.refresh()

    def save(self) -> None:
        state = self.state
        name = state.case_name or state.case_draft.strip()
        try:
            folder = save_case(
                state.repository, state.target, name, state.mocks, state.grid_rows
            )
            state.case_name = name
            state.message = Message(
                f"Saved case {state.target}/{name}",
                ok=True,
                marker="saved",
                detail=str(folder),
            )
        except SaveError as error:
            state.message = Message(f"Could not save: {error}", ok=False)
        except Exception as error:  # noqa: BLE001 — show engine failures in the page
            state.message = Message(f"Could not save: {error}", ok=False)
        self.refresh()
