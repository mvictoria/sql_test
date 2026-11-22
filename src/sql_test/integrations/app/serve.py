import socket
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
from sql_test.integrations.discover import discover

LOCAL_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})


class PortInUseError(Exception):
    """The app port is already bound; do not print a false serving line."""


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
    _ensure_port_free(host, port)
    repository = repository.resolve()
    register_app(repository, executor)
    print(f"sql-test app serving {repository} at http://{host}:{port}/")
    ui.run(host=host, port=port, reload=False, show=False, title="sql-test")


def _ensure_port_free(host: str, port: int) -> None:
    """Raise PortInUseError before any success banner if the port cannot bind."""
    family = socket.AF_INET6 if ":" in host and host != "localhost" else socket.AF_INET
    bind_host = "127.0.0.1" if host == "localhost" else host
    probe = socket.socket(family, socket.SOCK_STREAM)
    try:
        # No SO_REUSEADDR: match a real listen conflict (another app serving).
        probe.bind((bind_host, port))
    except OSError as error:
        raise PortInUseError(f"port {port} is already in use") from error
    finally:
        probe.close()


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
    if source := _source_target(repository, query):
        _source_not_target_page(source)
        return
    state = open_workbench(repository, query)
    if state is None:
        ui.link("← sql-test", "/").mark("home-link")
        ui.label("Not found").classes("text-h5").mark("not-found")
        return
    Workbench(state).build()


def _source_target(repository: Path, query: dict[str, list[str]]) -> str | None:
    """Return the named source when the deep link asks to use it as table under test."""
    if query.get("case") or not query.get("target"):
        return None
    name = query["target"][0]
    return name if name in discover(repository).sources else None


def _source_not_target_page(name: str) -> None:
    ui.link("← sql-test", "/").mark("home-link")
    ui.label(f"{name} is a source").classes("text-h5").mark("source-not-target")
    ui.label(
        "Sources aren't tables under test. Open a model that reads this table, "
        "or mock it from that model's lineage."
    ).mark("source-not-target-detail")


def _guarded(build: Callable[[], None]) -> None:
    try:
        build()
    except Exception as error:  # noqa: BLE001 — always answer the browser
        ui.label("Something went wrong").classes("text-h5").mark("error")
        ui.label(str(error)).mark("error-detail")
        ui.link("← sql-test", "/")
