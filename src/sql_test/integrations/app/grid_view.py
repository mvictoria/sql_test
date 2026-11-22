from collections.abc import Callable
from dataclasses import dataclass

from nicegui import ui

from sql_test.engine import Column, Schema
from sql_test.integrations.app.compare_view import target_schema
from sql_test.integrations.app.grid import (
    Cell,
    cell_error,
    next_grid_cell,
    paste_into_grid,
    previous_grid_cell,
)
from sql_test.integrations.app.state import WorkbenchState

_NULL_HINT = "Ctrl+; sets NULL on the focused cell. Type to replace a NULL."
_PASTE_JS = """
(e) => {
    const data = e.clipboardData;
    const text = data?.getData('text/plain') || data?.getData('text') || '';
    if (text.includes('\\t') || text.includes('\\n') || text.includes('\\r')) {
        e.preventDefault();
        emit({text});
    }
}
"""
_CLEAR_NULL_JS = """
(e) => {
    if (e.ctrlKey || e.metaKey || e.altKey) return;
    if (typeof e.key !== 'string' || e.key.length !== 1) return;
    e.preventDefault();
    emit({key: e.key});
}
"""
_SET_NULL_JS = """
(e) => {
    if (!(e.ctrlKey || e.metaKey) || e.key !== ';') return;
    e.preventDefault();
    emit({});
}
"""


@dataclass(frozen=True)
class EditorActions:
    on_edit: Callable[[], None]
    on_rebuild: Callable[[], None]
    on_add_row: Callable[[str], None]
    on_delete_row: Callable[[str, int], None]
    on_duplicate_row: Callable[[str, int], None]
    on_run: Callable[[], None]
    on_save: Callable[[], None]


def editor_view(state: WorkbenchState, actions: EditorActions) -> None:
    """Setup pane: case name, collapsible mocks and Expected, sticky Run/Save."""
    expected_schema = target_schema(state.catalog, state.target)
    if not state.mocks and expected_schema is None:
        return
    _case_name(state)
    if state.mocks:
        ui.label("Mock editor").classes("text-subtitle1")
        ui.label(_NULL_HINT).classes("text-caption text-grey-8").mark("null-hint")
        repo_catalog = state.catalog
        for name in state.mocks:
            schema = repo_catalog.schema(repo_catalog.resolve(name))
            if schema is None:
                ui.label(f"{name}: no schema").classes("text-grey-7")
                continue
            _collapsible_grid(name, name, schema, state, actions)
    ui.label(_NULL_HINT).classes("text-caption text-grey-8").mark("null-hint")
    if expected_schema is None:
        ui.label("Expected").classes("text-subtitle1").mark("grid-expected")
        ui.label("No schema for the table under test").classes("text-grey-7")
    else:
        if state.grid_rows.get("expected") == []:
            ui.label("Expects no rows").classes("text-caption text-grey-8").mark(
                "expected-no-rows"
            )
        _collapsible_grid("expected", "Expected", expected_schema, state, actions)
    with ui.row().classes(
        "sticky bottom-0 z-10 w-full bg-white py-2 gap-2 items-center border-t"
    ):
        ui.button("Run", on_click=actions.on_run).mark("run")
        ui.button("Save case", on_click=actions.on_save).mark("save")


def _collapsible_grid(
    name: str,
    title: str,
    schema: Schema,
    state: WorkbenchState,
    actions: EditorActions,
) -> None:
    rows = state.grid_rows.setdefault(name, [{}])
    caption = _rows_caption(rows)
    open_ = name in state.expanded_grids
    expansion = (
        ui.expansion(
            f"{title} · {caption}",
            value=open_,
            on_value_change=lambda event, table=name: _set_expanded(
                state, table, bool(event.value)
            ),
        )
        .classes("w-full")
        .mark(f"grid-expand-{name} grid-{name}")
    )
    if state.grid_focus is not None and state.grid_focus[0] == name:
        expansion.run_method("scrollIntoView", {"block": "center", "inline": "nearest"})
    with expansion:
        grid_view(name, schema, state, actions)


def _set_expanded(state: WorkbenchState, name: str, open_: bool) -> None:
    if open_:
        state.expanded_grids.add(name)
    else:
        state.expanded_grids.discard(name)


def _rows_caption(rows: list[dict]) -> str:
    count = len(rows)
    return "1 row" if count == 1 else f"{count} rows"


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
        field = (
            ui.input(
                value="" if value is None else value,
                placeholder="NULL" if is_null else "",
                on_change=lambda event, row=row, key=key, column=column, invalid=invalid, error_label=error_label: (
                    _edit(row, key, event.value, column, invalid, error_label, actions)
                ),
            )
            .props("dense outlined")
            .tooltip(_NULL_HINT)
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
        set_null = lambda _, row=row, key=key, field=field, table=table, index=index: (
            _set_null(row, key, actions, field=field, table=table, index=index)
        )
        # Chord for User tests; JS emit so real browsers see Ctrl/Cmd+;.
        field.on("keydown.ctrl.exact.;.prevent", set_null)
        field.on("keydown.meta.exact.;.prevent", set_null)
        field.on(
            "keydown",
            lambda event, row=row, key=key, field=field, table=table, index=index: (
                _set_null(row, key, actions, field=field, table=table, index=index)
                if _is_set_null_event(event)
                else None
            ),
            js_handler=_SET_NULL_JS,
        )
        field.on(
            "paste",
            lambda event, index=index, key=key: _paste(
                table, state, actions, columns, index, key, event.args
            ),
            js_handler=_PASTE_JS,
        )
        if is_null:
            field.props("readonly")
            field.on(
                "keydown",
                lambda event, row=row, key=key: _clear_null_on_type(
                    event.args, row, key, actions
                ),
                js_handler=_CLEAR_NULL_JS,
            )


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


def _paste(
    table: str,
    state: WorkbenchState,
    actions: EditorActions,
    columns: list[str],
    row: int,
    column: str,
    args: object,
) -> None:
    text = _paste_text(args)
    if text is None or not _tabular_clipboard(text):
        return
    rows = state.grid_rows.setdefault(table, [{}])
    state.grid_rows[table] = paste_into_grid(
        rows, columns, start_row=row, start_column=column, clipboard=text
    )
    actions.on_rebuild()


def _paste_text(args: object) -> str | None:
    if isinstance(args, dict):
        value = args.get("text")
        return value if isinstance(value, str) else None
    return None


def _tabular_clipboard(text: str) -> bool:
    return "\t" in text or "\n" in text or "\r" in text


def _edit(
    row: dict[str, Cell],
    column: str,
    value: str | None,
    schema_column: Column,
    invalid_marker: str,
    error_label: ui.label,
    actions: EditorActions,
) -> None:
    # Ignore empty on_change while NULL (e.g. clearing the input for display).
    if (value or "") == "" and column in row and row[column] is None:
        return
    row[column] = value or ""
    message = cell_error(schema_column, row[column])
    error_label.set_text(message or "")
    error_label.mark(invalid_marker if message else "")
    actions.on_edit()


def _set_null(
    row: dict[str, Cell],
    column: str,
    actions: EditorActions,
    *,
    field: ui.input,
    table: str,
    index: int,
) -> None:
    """Ctrl+; only sets NULL; leave NULL by typing (empty string stays "")."""
    if column in row and row[column] is None:
        return
    row[column] = None
    # Clear the visible text and show the NULL placeholder on this input before
    # rebuild. set_value fires on_change; _edit must keep None (see guard above).
    # Without this paint, a mid-handler grid clear often leaves the browser
    # looking empty until a later full refresh (Run).
    field.set_value("")
    field.props("readonly placeholder=NULL")
    field.mark(f"cell-{table}.{index}.{column} null-{table}.{index}.{column}")
    field.update()
    actions.on_rebuild()


def _clear_null_on_type(
    args: object,
    row: dict[str, Cell],
    column: str,
    actions: EditorActions,
) -> None:
    key = _keydown_character(args)
    if key is None:
        return
    row[column] = key
    actions.on_rebuild()


def _keydown_character(args: object) -> str | None:
    if not isinstance(args, dict):
        return None
    key = args.get("key")
    if not isinstance(key, str) or len(key) != 1:
        return None
    return key


def _is_set_null_event(event: object) -> bool:
    """Chord handlers and JS emit({}) set NULL; ignore other keydowns."""
    args = getattr(event, "args", None)
    if args is None or args == {} or args is True:
        return True
    if not isinstance(args, dict):
        return False
    if args.get("key") != ";":
        return False
    return bool(args.get("ctrlKey") or args.get("metaKey") or args.get("ctrl"))


def _case_name(state: WorkbenchState) -> None:
    # Keep draft in sync so rename edits are what Save uses (APP-33).
    if state.case_name and not state.case_draft:
        state.case_draft = state.case_name
    field = ui.input(
        "Case name",
        value=state.case_draft,
        on_change=lambda event: setattr(state, "case_draft", event.value or ""),
    ).mark("case-name")
    if state.highlight_case_name:
        field.classes(add="case-name-needed")
        field.props("outlined color=negative")
        field.mark("case-name case-name-needed")
        field.run_method("focus")
        state.highlight_case_name = False
