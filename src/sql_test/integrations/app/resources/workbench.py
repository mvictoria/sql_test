import html
from pathlib import Path

from sql_test.engine import RunResult
from sql_test.integrations.app.engine_access import run as run_case
from sql_test.integrations.app.grid import (
    apply_grid_action,
    mock_editor,
    parse_grid_rows,
    type_grid_rows,
)
from sql_test.integrations.app.lineage import (
    frontier_mocks,
    lineage_section,
    workbench_query,
)
from sql_test.integrations.app.output import output_section
from sql_test.integrations.app.router import Request, Response
from sql_test.integrations.app.sql_view import sql_section
from sql_test.integrations.discover import Discovery, discover

VIEWS = frozenset({"sql", "lineage"})
DEFAULT_VIEW = "lineage"


def get(request: Request) -> Response | None:
    return _respond(request)


def post(request: Request) -> Response | None:
    return _respond(request)


def _respond(request: Request) -> Response | None:
    page = _workbench(request.repository, discover(request.repository), request.query)
    if page is None:
        return None
    return Response(body=page)


def _workbench(
    repository: Path,
    result: Discovery,
    query: dict[str, list[str]],
) -> str | None:
    case_name: str | None = None
    if query.get("case"):
        raw = query["case"][0]
        if "/" not in raw:
            return None
        target, case_name = raw.split("/", 1)
        if not any(c.target == target and c.name == case_name for c in result.cases):
            return None
        base_query = {"case": f"{target}/{case_name}"}
    elif query.get("target"):
        target = query["target"][0]
        if target not in result.models and target not in result.sources:
            return None
        base_query = {"target": target}
    else:
        return None

    view = query.get("view", [DEFAULT_VIEW])[0]
    if view not in VIEWS:
        view = DEFAULT_VIEW
    requested_mocks = tuple(sorted({name for name in query.get("mock", []) if name}))
    mocks = frontier_mocks(repository, target, requested_mocks)
    grid_rows = parse_grid_rows(query)
    action = query.get("action", [""])[0]
    grid_rows = apply_grid_action(action, mocks, grid_rows)
    engine_types: dict[str, dict[str, str]] = {}
    reached = ""
    run_result: RunResult | None = None
    if action == "apply":
        mocked_rows = {name: grid_rows.get(name, []) for name in mocks}
        try:
            grid_rows, engine_types = type_grid_rows(repository, mocked_rows)
            reached = '<p class="ready">Reached engine — mock rows loaded with schema types</p>'
        except Exception as error:  # noqa: BLE001 — show engine failures in the page
            reached = (
                '<p class="blocked">Could not load mocks: '
                f"{html.escape(str(error))}</p>"
            )
    elif action == "run":
        try:
            run_result = run_case(repository, target, mocks, grid_rows)
            reached = '<p class="ready">Run complete</p>'
        except Exception as error:  # noqa: BLE001 — show engine failures in the page
            reached = f'<p class="blocked">Could not run: {html.escape(str(error))}</p>'

    counts = run_result.counts if run_result is not None else None
    case_line = (
        f"<p>Case: <strong>{html.escape(case_name)}</strong></p>" if case_name else ""
    )
    mocks_line = (
        "<p>Mocks: "
        + ", ".join(f"<code>{html.escape(name)}</code>" for name in mocks)
        + "</p>"
        if mocks
        else ""
    )
    body = (
        lineage_section(repository, target, mocks, base_query, grid_rows, counts)
        if view == "lineage"
        else sql_section(repository, target)
    )
    output = output_section(run_result) if run_result is not None else ""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Workbench — {html.escape(target)}</title>
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 2rem; }}
    h1 {{ font-size: 1.25rem; }}
    h2 {{ font-size: 1rem; margin-top: 1.5rem; }}
    a {{ color: inherit; }}
    nav.views a {{ margin-right: 1rem; }}
    nav.views a.current {{ font-weight: 700; text-decoration: none; }}
    pre {{ background: #f4f4f4; padding: 1rem; overflow: auto; }}
    .empty {{ color: #666; }}
    .legend {{ font-size: 0.85rem; color: #555; margin: 0.5rem 0 1rem; }}
    .legend span {{ margin-right: 1rem; }}
    .graph {{ width: 100%; max-width: 56rem; height: auto; }}
    .graph .edge {{ stroke: #888; stroke-width: 1.5; fill: none; marker-end: url(#arrow); }}
    .graph .node rect {{ stroke-width: 1.5; }}
    .graph .node.executed rect {{ fill: #e7f6ed; stroke: #1b7a45; }}
    .graph .node.mocked rect {{ fill: #e8eefc; stroke: #3451b2; }}
    .graph .node.target rect {{ fill: #f3e8ff; stroke: #7c3aed; stroke-width: 2.5; }}
    .graph .node.source rect {{ fill: #fff6e0; stroke: #c80; }}
    .graph .node.needs-rows rect {{ fill: #f3f3f3; stroke: #ccc; }}
    .graph .node.needs-rows text {{ fill: #999; }}
    .graph .label {{ font: 12px system-ui, sans-serif; }}
    .graph .state {{ font: 10px system-ui, sans-serif; fill: #555; text-transform: uppercase; }}
    .ready {{ color: #1b7a45; }}
    .blocked {{ color: #a60; }}
    .grid {{ border-collapse: collapse; margin: 0.5rem 0 1rem; }}
    .grid th, .grid td {{ border: 1px solid #ccc; padding: 0.25rem 0.4rem; }}
    .grid th {{ background: #f4f4f4; font-size: 0.85rem; }}
    .grid input {{ width: 8rem; font: inherit; }}
    .grid-actions {{ margin: 0 0 1rem; }}
    .grid-actions button {{ margin-right: 0.5rem; }}
    .output {{ border-collapse: collapse; margin: 0.5rem 0 1rem; }}
    .output th, .output td {{ border: 1px solid #ccc; padding: 0.25rem 0.5rem; }}
    .output th {{ background: #f4f4f4; font-size: 0.85rem; }}
  </style>
</head>
<body>
  <p><a href="/">← sql-test</a></p>
  <h1>Workbench</h1>
  <p>Table under test: <strong>{html.escape(target)}</strong></p>
  {case_line}
  {mocks_line}
  {_view_nav(base_query, view, mocks)}
  {body}
  {reached}
  {output}
  {mock_editor(repository, mocks, base_query, view, grid_rows, engine_types)}
</body>
</html>
"""


def _view_nav(base_query: dict[str, str], current: str, mocks: tuple[str, ...]) -> str:
    links = []
    for name in ("lineage", "sql"):
        href = workbench_query(base_query, view=name, mocks=mocks)
        cls = ' class="current"' if name == current else ""
        links.append(f'<a href="{html.escape(href)}"{cls}>{html.escape(name)}</a>')
    return f'<nav class="views">{" ".join(links)}</nav>'
