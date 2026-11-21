from collections.abc import Callable
from dataclasses import dataclass

from nicegui import ui

from sql_test.engine import Column, Schema
from sql_test.integrations.app.compare_view import target_schema
from sql_test.integrations.app.grid import (
    Cell,
    cell_error,
    next_grid_cell,
    previous_grid_cell,
)
from sql_test.integrations.app.state import WorkbenchState


@dataclass(frozen=True)
class EditorActions:
    on_edit: Callable[[], None]
    on_rebuild: Callable[[], None]
    on_add_row: Callable[[str], None]
    on_delete_row: Callable[[str, int], None]
    on_duplicate_row: Callable[[str, int], None]
    on_apply: Callable[[], None]
    on_run: Callable[[], None]
    on_save: Callable[[], None]


def editor_view(state: WorkbenchState, actions: EditorActions) -> None:
    expected_schema = target_schema(state.catalog, state.target)
    if not state.mocks and expected_schema is None:
        return
    _case_name(state)
    repo_catalog = state.catalog
    if state.mocks:
        ui.label("Mock editor").classes("text-subtitle1")
    for name in state.mocks:
        schema = repo_catalog.schema(repo_catalog.resolve(name))
        if schema is None:
            ui.label(f"{name}: no schema").classes("text-grey-7")
            continue
        ui.label(name).classes("text-subtitle2").mark(f"grid-{name}")
        grid_view(name, schema, state, actions)
    ui.label("Expected").classes("text-subtitle1").mark("grid-expected")
    if expected_schema is None:
        ui.label("No schema for the table under test").classes("text-grey-7")
    else:
        if state.grid_rows.get("expected") == []:
            ui.label("Expects no rows").classes("text-caption text-grey-8").mark(
                "expected-no-rows"
            )
        grid_view("expected", expected_schema, state, actions)
    with ui.row():
        ui.button("Apply to engine", on_click=actions.on_apply).mark("apply")
        ui.button("Run", on_click=actions.on_run).mark("run")
        ui.button("Save case", on_click=actions.on_save).mark("save")


def grid_view(
    name: str, schema: Schema, state: WorkbenchState, actions: EditorActions
) -> None:
    rows = state.grid_rows.setdefault(name, [{}])
    types = state.engine_types.get(name, {})
    columns = [column.name for column in schema]
    by_name = {column.name: column for column in schema}
    fields: dict[tuple[int, str], ui.input] = {}
    with ui.grid(columns=f"repeat({len(columns)}, 11rem) auto auto").classes(
        "items-start"
    ):
        for column in columns:
            with ui.column().classes("gap-0"):
                ui.label(column).classes("text-caption text-weight-bold")
                if column in types:
                    ui.label(types[column]).classes("text-caption text-grey-7").mark(
                        f"engine-type-{name}.{column}"
                    )
        ui.label("")
        ui.label("")
        for index, row in enumerate(rows):
            for column in columns:
                _cell(
                    name, index, row, by_name[column], state, actions, columns, fields
                )
            ui.button(
                "Duplicate",
                on_click=lambda _, index=index: actions.on_duplicate_row(name, index),
            ).props("flat dense tabindex=-1").mark(f"duplicate-{name}.{index}")
            ui.button(
                "Delete",
                on_click=lambda _, index=index: actions.on_delete_row(name, index),
            ).props("flat dense tabindex=-1").mark(f"delete-{name}.{index}")
    ui.button("Add row", on_click=lambda: actions.on_add_row(name)).props(
        "flat dense"
    ).mark(f"add-row-{name}")


def _cell(
    table: str,
    index: int,
    row: dict[str, Cell],
    column: Column,
    state: WorkbenchState,
    actions: EditorActions,
    columns: list[str],
    fields: dict[tuple[int, str], ui.input],
) -> None:
    key = column.name
    value = row.get(key)
    is_null = key in row and value is None
    error = cell_error(column, value)
    invalid = f"invalid-{table}.{index}.{key}"
    markers = f"cell-{table}.{index}.{key}"
    if is_null:
        markers = f"{markers} null-{table}.{index}.{key}"
    with ui.column().classes("gap-0"):
        error_label = ui.label(error or "").classes("text-caption text-negative")
        if error:
            error_label.mark(invalid)
        with ui.row().classes("items-center no-wrap gap-1"):
            field = (
                ui.input(
                    value="" if value is None else value,
                    placeholder="NULL" if is_null else "",
                    on_change=lambda event, row=row, key=key, column=column, invalid=invalid, error_label=error_label: (
                        _edit(
                            row, key, event.value, column, invalid, error_label, actions
                        )
                    ),
                )
                .props("dense outlined debounce=300")
                .mark(markers)
            )
            fields[(index, key)] = field
            if state.grid_focus == (table, index, key):
                field.classes(add="grid-focus")
                field.run_method("focus")
                state.grid_focus = None
            field.on(
                "keydown.exact.tab.prevent",
                lambda _, index=index, key=key: _move_grid_focus(
                    table,
                    state,
                    actions,
                    columns,
                    fields,
                    index,
                    key,
                    reverse=False,
                ),
            )
            field.on(
                "keydown.shift.tab.prevent",
                lambda _, index=index, key=key: _move_grid_focus(
                    table,
                    state,
                    actions,
                    columns,
                    fields,
                    index,
                    key,
                    reverse=True,
                ),
            )
            if is_null:
                field.props("readonly")
            toggle = (
                ui.button(
                    "NULL",
                    on_click=lambda _, row=row, key=key, is_null=is_null: _toggle_null(
                        row, key, is_null, actions
                    ),
                )
                .props("flat dense tabindex=-1")
                .mark(f"null-toggle-{table}.{index}.{key}")
            )
            if is_null:
                toggle.props("unelevated")


def _move_grid_focus(
    table: str,
    state: WorkbenchState,
    actions: EditorActions,
    columns: list[str],
    fields: dict[tuple[int, str], ui.input],
    row: int,
    column: str,
    *,
    reverse: bool,
) -> None:
    if reverse:
        target = previous_grid_cell(columns, row, column)
        if target is None:
            return
        _focus_cell(fields, *target)
        return
    row_count = max((r for r, _ in fields), default=-1) + 1
    target = next_grid_cell(columns, row, column, row_count)
    if target is not None:
        _focus_cell(fields, *target)
        return
    if not columns:
        return
    state.grid_focus = (table, row_count, columns[0])
    actions.on_add_row(table)


def _focus_cell(fields: dict[tuple[int, str], ui.input], row: int, column: str) -> None:
    for field in fields.values():
        field.classes(remove="grid-focus")
    field = fields.get((row, column))
    if field is None:
        return
    field.classes(add="grid-focus")
    field.run_method("focus")


def _edit(
    row: dict[str, Cell],
    column: str,
    value: str | None,
    schema_column: Column,
    invalid_marker: str,
    error_label: ui.label,
    actions: EditorActions,
) -> None:
    row[column] = value or ""
    message = cell_error(schema_column, row[column])
    error_label.set_text(message or "")
    error_label.mark(invalid_marker if message else "")
    actions.on_edit()


def _toggle_null(
    row: dict[str, Cell],
    column: str,
    currently_null: bool,
    actions: EditorActions,
) -> None:
    row[column] = "" if currently_null else None
    actions.on_rebuild()


def _case_name(state: WorkbenchState) -> None:
    field = ui.input(
        "Case name",
        value=state.case_name or state.case_draft,
        on_change=lambda event: setattr(state, "case_draft", event.value or ""),
    ).mark("case-name")
    if state.case_name:
        field.props("readonly")
