from pathlib import Path
from urllib.parse import quote

from nicegui import ui

from sql_test.integrations.app.case_load import case_grid_rows, load_case
from sql_test.integrations.app.case_save import SaveError, case_exists, save_case
from sql_test.integrations.app.compare_view import compare_section
from sql_test.integrations.app.engine_access import catalog
from sql_test.integrations.app.engine_access import run as run_case
from sql_test.integrations.app.flags_session import effective_flags
from sql_test.integrations.app.grid import apply_grid_action, type_grid_rows
from sql_test.integrations.app.grid_view import EditorActions, editor_view, sheet_css
from sql_test.integrations.app.lineage_view import lineage_css, lineage_view
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
from sql_test.integrations.config import AppFlags
from sql_test.integrations.discover import Discovery, discover


def open_workbench(
    repository: Path, query: dict[str, list[str]]
) -> WorkbenchState | None:
    """The workbench a deep link asks for, or None when the link names nothing."""
    repo_catalog = catalog(repository)
    result = discover(repository, repo_catalog)
    # Durable only here: tab_id is unset until the socket connects (see Workbench.build).
    flags = AppFlags.load(repository)
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
        if target in result.sources:
            return None
        if target not in result.models:
            return None
    else:
        return None
    view = query.get("view", [DEFAULT_VIEW])[0]
    saved = (
        load_case(repository, target, case_name, repo_catalog)
        if case_name is not None
        else None
    )
    grid_rows: dict[str, list[dict[str, str | None]]] = {}
    mock_params = tuple(sorted({name for name in query.get("mock", []) if name}))
    if saved is not None:
        grid_rows = case_grid_rows(saved)
    if saved is not None and not mock_params:
        requested = tuple(sorted(str(relation) for relation in saved.mocks))
    else:
        requested = mock_params
    mocks = frontier_mocks(repo_catalog, target, requested)
    target_cases = tuple(case.name for case in result.cases if case.target == target)
    return WorkbenchState(
        repository=repository,
        catalog=repo_catalog,
        target=target,
        case_name=case_name,
        target_cases=target_cases,
        mocks=mocks,
        grid_rows=apply_grid_action("", mocks, grid_rows),
        flags=flags,
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
            on_rebuild=self.refresh_grids,
            on_add_row=self.add_row,
            on_delete_row=self.delete_row,
            on_duplicate_row=self.duplicate_row,
            on_run=self.run,
            on_save=self.save,
        )

    def build(self) -> None:
        ui.add_css(lineage_css())
        ui.add_css(sheet_css())
        ui.link("← sql-test", "/").mark("home-link")
        ui.label("Workbench").classes("text-h5")
        self.summary = ui.column().classes("gap-0")
        self.body = ui.column().classes("w-full")
        self.status = ui.column().classes("gap-0")
        self.panes = (
            ui.row()
            .classes("w-full items-start gap-4 flex-wrap")
            .mark("workbench-panes")
        )
        with self.panes:
            self.setup = (
                ui.column().classes("w-full flex-1 min-w-80").mark("workbench-setup")
            )
            self.outcome = (
                ui.column().classes("w-full flex-1 min-w-80").mark("workbench-outcome")
            )
        self.refresh()
        # Session flag overrides are keyed by tab_id, which arrives on handshake.
        ui.context.client.on_connect(self._sync_session_flags)

    def _sync_session_flags(self) -> None:
        flags = effective_flags(self.state.repository)
        if flags == self.state.flags:
            return
        self.state.flags = flags
        self.refresh()

    def refresh(self) -> None:
        self.refresh_summary()
        self.refresh_body()
        self.refresh_status()
        reading_sql = self.state.view == "sql"
        self.panes.set_visibility(not reading_sql)
        if reading_sql:
            self.setup.clear()
            self.outcome.clear()
            return
        self.refresh_setup()
        self.refresh_outcome()

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
            if state.target_cases:
                with ui.row().classes("gap-2 items-baseline").mark("target-cases"):
                    ui.label("Cases:")
                    for name in state.target_cases:
                        href = (
                            f"/workbench?case="
                            f"{quote(f'{state.target}/{name}', safe='')}"
                        )
                        ui.link(name, href).mark(f"target-case-{state.target}/{name}")
            if state.mocks:
                with ui.row().classes("gap-1 items-center").mark("mocks"):
                    ui.label("Mocks:")
                    for index, name in enumerate(state.mocks):
                        if index:
                            ui.label(",")
                        ui.button(
                            name,
                            on_click=lambda _, name=name: self.focus_grid(name),
                        ).props("flat dense").classes("focus-grid-link").mark(
                            f"focus-grid-{name}"
                        )

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
                lineage_view(
                    self.state,
                    self.toggle_mock,
                    self.focus_grid,
                    on_peek=self.peek_sql,
                    on_close_peek=self.clear_sql_peek,
                )
            else:
                sql_view(self.state.catalog, self.state.target)

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

    def refresh_setup(self) -> None:
        self.setup.clear()
        with self.setup:
            editor_view(self.state, self.actions)

    def refresh_outcome(self) -> None:
        self.outcome.clear()
        with self.outcome:
            result_view(self.state, self.show_result_view, self.accept_expected)

    def refresh_grids(self) -> None:
        """Rebuild mock and Expected grids after NULL / paste / row shape changes."""
        self.refresh_setup()

    def reload_catalog(self) -> None:
        """Replace the catalog with one built from the checkout as it is now."""
        state = self.state
        try:
            state.catalog = catalog(state.repository)
        except Exception as error:  # noqa: BLE001 — show failures in the page
            state.message = Message(
                f"Could not reload the repository: {error}", ok=False
            )
            return
        state.mocks = frontier_mocks(state.catalog, state.target, state.mocks)
        state.grid_rows = apply_grid_action("", state.mocks, state.grid_rows)

    def show_view(self, name: str) -> None:
        self.reload_catalog()
        self.state.view = name
        if name != "lineage":
            self.state.sql_peek = None
        self.state.flags = effective_flags(self.state.repository)
        self.refresh()

    def peek_sql(self, name: str) -> None:
        """Show producer SQL for a lineage node without leaving the graph."""
        self.state.flags = effective_flags(self.state.repository)
        if not self.state.flags.sql_peek:
            return
        self.state.sql_peek = name
        self.refresh_body()

    def clear_sql_peek(self) -> None:
        self.state.sql_peek = None
        self.refresh_body()

    def show_result_view(self, name: str) -> None:
        self.state.result_view = name
        self.refresh_outcome()

    def toggle_mock(self, name: str) -> None:
        state = self.state
        self.reload_catalog()
        before = set(state.mocks)
        requested = toggled_mocks(state.mocks, name)
        state.mocks = frontier_mocks(state.catalog, state.target, requested)
        state.grid_rows = apply_grid_action("", state.mocks, state.grid_rows)
        self._reset_results()
        self.refresh()
        added = set(state.mocks) - before
        if name in added:
            self.focus_grid(name)
        elif added:
            self.focus_grid(next(iter(sorted(added))))

    def focus_grid(self, table: str) -> None:
        """Expand the named mock, scroll it into view, and focus its first cell."""
        state = self.state
        if table not in state.mocks:
            return
        schema = state.catalog.schema(state.catalog.resolve(table))
        if not schema:
            return
        rows = state.grid_rows.setdefault(table, [{}])
        if not rows:
            rows.append({})
        state.expanded_grids.add(table)
        state.grid_focus = (table, 0, schema[0].name)
        self.refresh_setup()

    def add_row(self, table: str) -> None:
        self._grid_action(f"add:{table}")

    def delete_row(self, table: str, index: int) -> None:
        self._grid_action(f"delete:{table}:{index}")

    def duplicate_row(self, table: str, index: int) -> None:
        self._grid_action(f"duplicate:{table}:{index}")

    def _grid_action(self, action: str) -> None:
        state = self.state
        state.grid_rows = apply_grid_action(action, state.mocks, state.grid_rows)
        self._reset_results()
        self.refresh()

    def _reset_results(self) -> None:
        self.state.run_result = None
        self.state.panel = None
        self.state.message = None

    def run(self) -> None:
        state = self.state
        self._reset_results()
        self.reload_catalog()
        mocked = {name: state.grid_rows.get(name, []) for name in state.mocks}
        try:
            typed, state.engine_types = type_grid_rows(state.catalog, mocked)
            state.grid_rows.update(typed)
            result = run_case(state.catalog, state.target, state.mocks, state.grid_rows)
            panel = compare_section(
                state.catalog,
                state.target,
                state.grid_rows.get("expected", [{}]),
                result.rows,
                ordered=result.ordered,
            )
            state.run_result, state.panel = result, panel
            if not panel.passed:
                state.result_view = "diff"
            elif state.result_view not in RESULT_VIEWS:
                state.result_view = DEFAULT_RESULT_VIEW
            state.message = Message("Run complete", ok=True)
        except Exception as error:  # noqa: BLE001 — show failures in the page
            state.message = Message(f"Could not run: {error}", ok=False)
        self.refresh()

    def accept_expected(self, rows: list[dict[str, str | None]]) -> None:
        state = self.state
        state.grid_rows["expected"] = rows
        if state.run_result is not None:
            state.panel = compare_section(
                state.catalog,
                state.target,
                rows,
                state.run_result.rows,
                ordered=state.run_result.ordered,
            )
        state.message = Message("Accepted actual as expected", ok=True)
        self.refresh_setup()
        self.refresh_outcome()
        self.refresh_status()

    def save(self, *, overwrite: bool = False) -> None:
        state = self.state
        self.reload_catalog()
        previous = state.case_name
        name = state.case_draft.strip() or previous or ""
        try:
            if not overwrite and case_exists(
                state.repository, state.target, name, state.catalog
            ):
                # UAT-9: confirm before replacing CSVs in an existing folder.
                self._confirm_overwrite(name)
                return
            folder = save_case(
                state.repository,
                state.target,
                name,
                state.mocks,
                state.grid_rows,
                state.catalog,
                previous_name=previous,
            )
            state.case_name = name
            state.case_draft = name
            state.highlight_case_name = False
            state.message = Message(
                f"Saved case {state.target}/{name}",
                ok=True,
                marker="saved",
                detail=str(folder),
            )
        except SaveError as error:
            missing_name = not name or "/" in name or name in {".", ".."}
            state.highlight_case_name = missing_name
            detail = "Enter a Case name above, then Save again." if missing_name else ""
            state.message = Message(
                f"Could not save: {error}",
                ok=False,
                detail=detail,
            )
        except Exception as error:  # noqa: BLE001 — show failures in the page
            state.message = Message(f"Could not save: {error}", ok=False)
        self.refresh()

    def _confirm_overwrite(self, name: str) -> None:
        """UAT-9: ask before replacing an existing case folder's CSVs."""
        with ui.dialog() as dialog, ui.card().classes("gap-2"):
            ui.label(
                f"Case {self.state.target}/{name} already exists. "
                "Save will replace its mock and expected CSVs."
            ).mark("save-overwrite-prompt")
            with ui.row().classes("gap-2"):
                ui.button("Cancel", on_click=dialog.close).props("flat").mark(
                    "save-overwrite-cancel"
                )
                ui.button(
                    "Overwrite",
                    on_click=lambda: (dialog.close(), self.save(overwrite=True)),
                ).props("unelevated color=negative").mark("save-overwrite-confirm")
        dialog.open()
