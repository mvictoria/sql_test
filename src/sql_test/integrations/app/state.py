from dataclasses import dataclass, field
from pathlib import Path

from sql_test.engine import RunResult
from sql_test.integrations.app.compare_view import DiffPanel

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
    target: str
    case_name: str | None = None
    case_draft: str = ""
    mocks: tuple[str, ...] = ()
    grid_rows: dict[str, list[dict[str, str | None]]] = field(default_factory=dict)
    engine_types: dict[str, dict[str, str]] = field(default_factory=dict)
    view: str = DEFAULT_VIEW
    result_view: str = DEFAULT_RESULT_VIEW
    run_result: RunResult | None = None
    panel: DiffPanel | None = None
    message: Message | None = None
