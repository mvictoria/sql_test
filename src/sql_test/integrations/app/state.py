from dataclasses import dataclass, field
from pathlib import Path

from sql_test.engine import Catalog, RunResult
from sql_test.integrations.app.compare_view import DiffPanel
from sql_test.integrations.config import AppFlags

VIEWS = ("lineage", "sql")
DEFAULT_VIEW = "lineage"
RESULT_VIEWS = ("output", "diff")
DEFAULT_RESULT_VIEW = "output"


@dataclass(frozen=True)
class Message:
    text: str
    ok: bool
    marker: str = ""
    detail: str = ""


@dataclass
class WorkbenchState:
    """Everything the workbench page remembers between clicks."""

    repository: Path
    catalog: Catalog
    target: str
    case_name: str | None = None
    case_draft: str = ""
    highlight_case_name: bool = False
    target_cases: tuple[str, ...] = ()
    mocks: tuple[str, ...] = ()
    deltas: tuple[str, ...] = ()
    grid_rows: dict[str, list[dict[str, str | None]]] = field(default_factory=dict)
    engine_types: dict[str, dict[str, str]] = field(default_factory=dict)
    grid_focus: tuple[str, int, str] | None = None
    expanded_grids: set[str] = field(default_factory=set)
    flags: AppFlags = field(default_factory=AppFlags)
    sql_peek: str | None = None
    view: str = DEFAULT_VIEW
    result_view: str = DEFAULT_RESULT_VIEW
    run_result: RunResult | None = None
    panel: DiffPanel | None = None
    message: Message | None = None
