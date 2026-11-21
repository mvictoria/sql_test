from collections.abc import Callable
from dataclasses import dataclass

from nicegui import ui

from sql_test.engine.schema import Schema
from sql_test.integrations.app.compare_view import target_schema
from sql_test.integrations.app.engine_access import catalog
from sql_test.integrations.app.state import WorkbenchState


@dataclass(frozen=True)
class EditorActions:
    on_edit: Callable[[], None]
    on_add_row: Callable[[str], None]
    on_delete_row: Callable[[str, int], None]
    on_apply: Callable[[], None]
    on_run: Callable[[], None]
    on_save: Callable[[], None]


def editor_view(state: WorkbenchState, actions: EditorActions) -> None:
    expected_schema = target_schema(state.repository, state.target)
    if not state.mocks and expected_schema is None:
        return
    _case_name(state)
    repo_catalog = catalog(state.repository)
    if state.mocks:
        ui.label("Mock editor").classes("text-subtitle1")
    for name in state.mocks:
        schema = repo_catalog.schema(repo_catalog.resolve(name))
        if schema is None:
            ui.label(f"{name}: no schema").classes("text-grey-7")
            continue
        ui.label(name).classes("text-subtitle2").mark(f"grid-{name}")
        grid_view(state, name, schema, actions)
    ui.label("Expected").classes("text-subtitle1").mark("grid-expected")
    if expected_schema is None:
        ui.label("No schema for the table under test").classes("text-grey-7")
    else:
        grid_view(state, "expected", expected_schema, actions)
    with ui.row():
        ui.button("Apply to engine", on_click=actions.on_apply).mark("apply")
        ui.button("Run", on_click=actions.on_run).mark("run")
        ui.button("Save case", on_click=actions.on_save).mark("save")


def grid_view(
    state: WorkbenchState, name: str, schema: Schema, actions: EditorActions
) -> None:
    rows = state.grid_rows.setdefault(name, [{}])
    types = state.engine_types.get(name, {})
    columns = [column.name for column in schema]
    with ui.grid(columns=f"repeat({len(columns)}, 10rem) auto").classes("items-start"):
        for column in columns:
            with ui.column().classes("gap-0"):
                ui.label(column).classes("text-caption text-weight-bold")
                if column in types:
                    ui.label(types[column]).classes("text-caption text-grey-7").mark(
                        f"engine-type-{name}.{column}"
                    )
        ui.label("")
        for index, row in enumerate(rows):
            for column in columns:
                ui.input(
                    value=row.get(column, ""),
                    on_change=lambda event, row=row, column=column: _edit(
                        row, column, event.value, actions
                    ),
                ).props("dense outlined debounce=300").mark(
                    f"cell-{name}.{index}.{column}"
                )
            ui.button(
                "Delete",
                on_click=lambda _, index=index: actions.on_delete_row(name, index),
            ).props("flat dense").mark(f"delete-{name}.{index}")
    ui.button("Add row", on_click=lambda: actions.on_add_row(name)).props(
        "flat dense"
    ).mark(f"add-row-{name}")


def _edit(
    row: dict[str, str], column: str, value: str | None, actions: EditorActions
) -> None:
    row[column] = value or ""
    actions.on_edit()


def _case_name(state: WorkbenchState) -> None:
    field = ui.input(
        "Case name",
        value=state.case_name or state.case_draft,
        on_change=lambda event: setattr(state, "case_draft", event.value or ""),
    ).mark("case-name")
    if state.case_name:
        field.props("readonly")
