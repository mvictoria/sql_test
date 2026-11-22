from pathlib import Path

from nicegui import ui

from sql_test.integrations.config import (
    PATH_NAMES,
    AppFlags,
    ConfigError,
    RepositoryConfig,
)


def settings_page(repository: Path, *, creating: bool = False) -> None:
    """Edit or create `[tool.sql-test]` paths and optional app flags."""
    try:
        values = RepositoryConfig.read_relative(repository)
        flags = AppFlags.load(repository)
    except ConfigError:
        values = {name: "" for name in PATH_NAMES}
        flags = AppFlags()
        creating = True

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
        sql_peek = ui.checkbox(
            "SQL peek on lineage (open a node's producer SQL under the graph)",
            value=flags.sql_peek,
        ).mark("flag-sql_peek")
        status = ui.column().classes("gap-0")
        ui.button(
            "Save",
            on_click=lambda: _save(repository, fields, sql_peek, status),
        ).mark("save-settings")


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
        ui.label("Saved").classes("text-green-9").mark("settings-saved")
        ui.link("Open home", "/").mark("home-link")
