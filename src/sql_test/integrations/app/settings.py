from pathlib import Path

from nicegui import ui

from sql_test.integrations.app.flags_session import (
    effective_flags,
    set_overrides,
)
from sql_test.integrations.config import (
    PATH_NAMES,
    AppFlags,
    ConfigError,
    RepositoryConfig,
)


def settings_page(repository: Path, *, creating: bool = False) -> None:
    """Edit or create `[tool.sql-test]` paths and `[tool.sql-test.flags]`."""
    try:
        values = RepositoryConfig.read_relative(repository)
        durable = AppFlags.load(repository)
        has_config = True
    except ConfigError:
        values = {name: "" for name in PATH_NAMES}
        durable = AppFlags()
        creating = True
        has_config = False

    ui.label("Repository settings").classes("text-h5").mark("settings")
    if creating:
        ui.label("Set the paths for this repository, then save.").classes("text-grey-7")
    else:
        ui.link("← sql-test", "/").mark("home-link")

    fields: dict[str, ui.input] = {}
    with ui.column().classes("gap-2 w-full max-w-xl"):
        for name in PATH_NAMES:
            fields[name] = (
                ui.input(name, value=values.get(name, ""))
                .props("dense outlined")
                .classes("w-full")
                .mark(f"path-{name}")
            )
        ui.label("App flags").classes("text-subtitle1")
        ui.label(
            "Apply keeps flags in this browser tab only. Save writes "
            "[tool.sql-test.flags] for everyone."
        ).classes("text-caption text-grey-8").mark("flags-session-hint")
        sql_peek = ui.checkbox(
            "SQL peek on lineage (open a node's producer SQL under the graph)",
            value=durable.sql_peek,
        ).mark("flag-sql_peek")
        status = ui.column().classes("gap-0")
        with ui.row().classes("gap-2"):
            if has_config:
                ui.button(
                    "Apply for this window",
                    on_click=lambda: _apply(sql_peek, status),
                ).props("outline").mark("apply-flags")
            ui.button(
                "Save",
                on_click=lambda: _save(repository, fields, sql_peek, status),
            ).mark("save-settings")

        def _pull_session_flags() -> None:
            sql_peek.set_value(effective_flags(repository).sql_peek)

        # tab_id arrives on handshake; refresh the checkbox from session overrides.
        ui.context.client.on_connect(_pull_session_flags)


def _apply(sql_peek: ui.checkbox, status: ui.column) -> None:
    set_overrides({"sql_peek": bool(sql_peek.value)})
    status.clear()
    with status:
        ui.label("Applied for this window — not written to pyproject.toml").classes(
            "text-green-9"
        ).mark("settings-flags-applied")


def _save(
    repository: Path,
    fields: dict[str, ui.input],
    sql_peek: ui.checkbox,
    status: ui.column,
) -> None:
    relative = {name: (fields[name].value or "").strip() for name in PATH_NAMES}
    flags = AppFlags(sql_peek=bool(sql_peek.value))
    status.clear()
    with status:
        try:
            RepositoryConfig.write(repository, relative, flags=flags)
        except ConfigError as error:
            ui.label(str(error)).classes("text-orange-9").mark("settings-error")
            return
        set_overrides({"sql_peek": flags.sql_peek})
        ui.label("Saved").classes("text-green-9").mark("settings-saved")
        ui.link("Open home", "/").mark("home-link")
