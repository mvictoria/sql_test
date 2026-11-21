from collections.abc import Callable
from pathlib import Path

from nicegui import ui
from starlette.requests import Request

from sql_test.engine import Executor
from sql_test.integrations.app.engine_access import bind_executor
from sql_test.integrations.app.home import home_page
from sql_test.integrations.app.settings import settings_page
from sql_test.integrations.app.workbench import Workbench, open_workbench
from sql_test.integrations.config import ConfigError, RepositoryConfig

LOCAL_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})


def register_app(repository: Path, executor: Executor) -> None:
    """Register the authoring pages; each closes over the one repository."""
    repository = repository.resolve()
    bind_executor(executor)

    @ui.page("/", title="sql-test")
    def home(pipelines: str | None = None) -> None:
        _guarded(lambda: _home_or_settings(repository, pipelines))

    @ui.page("/settings", title="Settings — sql-test")
    def settings() -> None:
        _guarded(lambda: settings_page(repository))

    @ui.page("/workbench", title="Workbench — sql-test")
    def workbench(request: Request) -> None:
        query = {key: request.query_params.getlist(key) for key in request.query_params}
        _guarded(lambda: _workbench_page(repository, query))


def serve(
    repository: Path,
    executor: Executor,
    host: str = "127.0.0.1",
    port: int = 8765,
) -> None:
    if host not in LOCAL_HOSTS:
        raise ValueError("app server must bind to localhost only")
    repository = repository.resolve()
    register_app(repository, executor)
    print(f"sql-test app serving {repository} at http://{host}:{port}/")
    ui.run(host=host, port=port, reload=False, show=False, title="sql-test")


def _home_or_settings(repository: Path, pipelines: str | None) -> None:
    try:
        RepositoryConfig.load(repository)
    except ConfigError:
        settings_page(repository, creating=True)
        return
    home_page(repository, pipelines)


def _workbench_page(repository: Path, query: dict[str, list[str]]) -> None:
    try:
        RepositoryConfig.load(repository)
    except ConfigError:
        settings_page(repository, creating=True)
        return
    state = open_workbench(repository, query)
    if state is None:
        ui.link("← sql-test", "/").mark("home-link")
        ui.label("Not found").classes("text-h5").mark("not-found")
        return
    Workbench(state).build()


def _guarded(build: Callable[[], None]) -> None:
    try:
        build()
    except Exception as error:  # noqa: BLE001 — always answer the browser
        ui.label("Something went wrong").classes("text-h5").mark("error")
        ui.label(str(error)).mark("error-detail")
        ui.link("← sql-test", "/")
