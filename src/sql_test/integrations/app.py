import html
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, urlencode, urlparse

from sql_test.engine import Engine
from sql_test.engine.catalog.adapters import mapped_sql_folder
from sql_test.engine.catalog.mapping import read_operations
from sql_test.engine.lineage.graph import upstream_lineage
from sql_test.engine.planner.plan import Plan, State
from sql_test.engine.relation import Relation
from sql_test.executors.duckdb import DuckDBExecutor
from sql_test.integrations.discover import MAPPING, SQLS, Discovery, discover

# Design toggle: view=lineage (default) | view=sql.
VIEWS = frozenset({"sql", "lineage"})
DEFAULT_VIEW = "lineage"


def create_server(
    repository: Path, host: str = "127.0.0.1", port: int = 8765
) -> ThreadingHTTPServer:
    repository = repository.resolve()
    if host not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("app server must bind to localhost only")

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path in {"/", "/index.html"}:
                body = _home(discover(repository)).encode()
            elif parsed.path == "/workbench":
                page = _workbench(
                    repository, discover(repository), parse_qs(parsed.query)
                )
                if page is None:
                    self.send_error(404)
                    return
                body = page.encode()
            else:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: object) -> None:
            return

    return ThreadingHTTPServer((host, port), Handler)


def serve(repository: Path, host: str = "127.0.0.1", port: int = 8765) -> None:
    server = create_server(repository, host=host, port=port)
    bound_host, bound_port = server.server_address[:2]
    assert isinstance(bound_host, str)
    assert isinstance(bound_port, int)
    print(f"sql-test app serving {repository} at http://{bound_host}:{bound_port}/")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print()
    finally:
        server.server_close()


def _home(result: Discovery) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>sql-test</title>
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 2rem; }}
    h1 {{ font-size: 1.25rem; }}
    h2 {{ font-size: 1rem; margin-top: 1.5rem; }}
    ul {{ padding-left: 1.25rem; }}
    .empty {{ color: #666; }}
  </style>
</head>
<body>
  <h1>sql-test</h1>
  {_model_section(result.models)}
  {_section("Sources", result.sources)}
  {_cases_section(result)}
</body>
</html>
"""


def _workbench(
    repository: Path, result: Discovery, query: dict[str, list[str]]
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
    mocks = _frontier_mocks(repository, target, requested_mocks)

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
        _lineage_section(repository, target, mocks, base_query)
        if view == "lineage"
        else _sql_section(repository, target)
    )
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
</body>
</html>
"""


def _workbench_query(
    base_query: dict[str, str],
    *,
    view: str,
    mocks: tuple[str, ...],
) -> str:
    params: list[tuple[str, str]] = [*(base_query.items()), ("view", view)]
    params.extend(("mock", name) for name in mocks)
    return "/workbench?" + urlencode(params)


def _view_nav(base_query: dict[str, str], current: str, mocks: tuple[str, ...]) -> str:
    links = []
    for name in ("lineage", "sql"):
        href = _workbench_query(base_query, view=name, mocks=mocks)
        cls = ' class="current"' if name == current else ""
        links.append(f'<a href="{html.escape(href)}"{cls}>{html.escape(name)}</a>')
    return f'<nav class="views">{" ".join(links)}</nav>'


def _sql_section(repository: Path, target: str) -> str:
    relation = Relation.parse(target)
    operations = [
        operation
        for operation in read_operations(repository / MAPPING, repository / SQLS)
        if operation.writes == relation
    ]
    if not operations:
        return "<h2>SQL</h2><p class='empty'>No producer SQL</p>"
    blocks = "".join(
        (
            f"<h2>{html.escape(operation.sql_file.name)}</h2>"
            f"<pre><code>{html.escape(operation.sql)}</code></pre>"
        )
        for operation in operations
    )
    return blocks


def _lineage_section(
    repository: Path,
    target: str,
    mocks: tuple[str, ...],
    base_query: dict[str, str],
) -> str:
    plan = _plan(repository, target, mocks)
    ready = not plan.needs_rows
    status = (
        '<p class="ready">Ready to run — all needs_rows covered</p>'
        if ready
        else (
            '<p class="blocked">Blocked — still need rows: '
            + ", ".join(
                f"<code>{html.escape(str(name))}</code>"
                for name in sorted(plan.needs_rows, key=str)
            )
            + "</p>"
        )
    )
    legend = (
        '<p class="legend">'
        "<span>target (purple)</span>"
        "<span>mocked (blue)</span>"
        "<span>will execute (green)</span>"
        "<span>source (amber)</span>"
        "<span>grey = needs rows</span>"
        " — pruned hidden; click a node to mock/unmock"
        "</p>"
    )
    return f"<h2>Lineage</h2>{status}{legend}{_lineage_graph(plan, mocks, base_query)}"


def _catalog(repository: Path):
    return mapped_sql_folder(repository / SQLS, repository / MAPPING)


def _plan(repository: Path, target: str, mocks: tuple[str, ...]) -> Plan:
    engine = Engine(catalog=_catalog(repository), executor=DuckDBExecutor)
    # Row count > 0 marks a mock as supplied; contents are ignored by plan().
    rows = {name: [{"_": 1}] for name in mocks}
    return engine.plan(target, rows=rows)


def _frontier_mocks(
    repository: Path, target: str, requested: tuple[str, ...]
) -> tuple[str, ...]:
    """Keep only a mock frontier: drop any mock upstream of another mock."""
    if not requested:
        return ()
    catalog = _catalog(repository)
    known = catalog.relations().keys() | {Relation.parse(name) for name in requested}
    target_relation = Relation.parse(target).resolve(known)
    projection = upstream_lineage(target_relation, catalog).projection()
    by_name = {str(relation): relation for relation in projection}
    for name in requested:
        by_name.setdefault(name, Relation.parse(name))
    kept: list[str] = []
    for name in requested:
        relation = by_name[name]
        upstream_of_another = any(
            relation in _upstream_closure(by_name[other], projection)
            for other in requested
            if other != name
        )
        if not upstream_of_another:
            kept.append(name)
    return tuple(sorted(kept))


def _upstream_closure(
    relation: Relation, projection: dict[Relation, set[Relation]]
) -> set[Relation]:
    seen: set[Relation] = set()
    stack = list(projection.get(relation, ()))
    while stack:
        current = stack.pop()
        if current in seen:
            continue
        seen.add(current)
        stack.extend(projection.get(current, ()))
    return seen


def _lineage_graph(
    plan: Plan, mocks: tuple[str, ...], base_query: dict[str, str]
) -> str:
    projection = plan.lineage.projection()
    visible = {
        relation for relation, state in plan.states.items() if state is not State.PRUNED
    }
    visible_projection = {
        relation: {upstream for upstream in upstreams if upstream in visible}
        for relation, upstreams in projection.items()
        if relation in visible
    }
    depths = _depths(plan.lineage.target, visible_projection)
    columns: dict[int, list[Relation]] = {}
    for relation, depth in depths.items():
        if relation not in visible:
            continue
        columns.setdefault(depth, []).append(relation)
    for rows in columns.values():
        rows.sort(key=str)

    node_w, node_h = 180, 52
    gap_x, gap_y = 64, 28
    max_rows = max((len(rows) for rows in columns.values()), default=1)
    width = max(len(columns), 1) * node_w + max(0, len(columns) - 1) * gap_x + 40
    height = max_rows * node_h + max(0, max_rows - 1) * gap_y + 40

    centers: dict[Relation, tuple[float, float]] = {}
    for depth, rows in sorted(columns.items()):
        x = 20 + depth * (node_w + gap_x) + node_w / 2
        col_height = len(rows) * node_h + max(0, len(rows) - 1) * gap_y
        y0 = (height - col_height) / 2 + node_h / 2
        for index, relation in enumerate(rows):
            y = y0 + index * (node_h + gap_y)
            centers[relation] = (x, y)

    edges: list[str] = []
    for downstream, upstreams in visible_projection.items():
        if downstream not in centers:
            continue
        x2, y2 = centers[downstream]
        for upstream in sorted(upstreams, key=str):
            if upstream not in centers:
                continue
            x1, y1 = centers[upstream]
            edges.append(
                f'<path class="edge" d="M{x1 + node_w / 2:.1f},{y1:.1f} '
                f"C{(x1 + x2) / 2:.1f},{y1:.1f} {(x1 + x2) / 2:.1f},{y2:.1f} "
                f'{x2 - node_w / 2:.1f},{y2:.1f}" />'
            )

    mocked = set(mocks)
    target_name = str(plan.lineage.target)
    nodes: list[str] = []
    for relation, (cx, cy) in centers.items():
        state = plan.states[relation]
        # Plan is before a run: future tense. Run-time will use executing → executed.
        label = {
            State.GIVEN: "mocked",
            State.EXECUTED: "will execute",
            State.SOURCE: "source",
            State.PRUNED: "pruned",
        }[state]
        css_state = {
            State.GIVEN: "mocked",
            State.EXECUTED: "executed",
            State.SOURCE: "source",
            State.PRUNED: "pruned",
        }[state]
        needs = relation in plan.needs_rows
        name = str(relation)
        classes = ["node", css_state]
        if name == target_name:
            classes.append("target")
            label = "table under test"
        if needs:
            classes.append("needs-rows")
        reason = plan.lineage.source_reasons.get(relation)
        subtitle = reason.value if reason else ("needs rows" if needs else label)
        x = cx - node_w / 2
        y = cy - node_h / 2
        if name == target_name:
            nodes.append(
                f'<g class="{" ".join(classes)}">'
                f'<rect x="{x:.1f}" y="{y:.1f}" width="{node_w}" height="{node_h}" rx="6" />'
                f'<text class="label" x="{cx:.1f}" y="{cy - 4:.1f}" text-anchor="middle">'
                f"{html.escape(name)}</text>"
                f'<text class="state" x="{cx:.1f}" y="{cy + 14:.1f}" text-anchor="middle">'
                f"{html.escape(subtitle)}</text>"
                f"</g>"
            )
            continue
        next_mocks = (
            tuple(sorted(mocked - {name}))
            if name in mocked
            else tuple(sorted(mocked | {name}))
        )
        href = _workbench_query(base_query, view="lineage", mocks=next_mocks)
        nodes.append(
            f'<g class="{" ".join(classes)}">'
            f'<a href="{html.escape(href)}">'
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{node_w}" height="{node_h}" rx="6" />'
            f'<text class="label" x="{cx:.1f}" y="{cy - 4:.1f}" text-anchor="middle">'
            f"{html.escape(name)}</text>"
            f'<text class="state" x="{cx:.1f}" y="{cy + 14:.1f}" text-anchor="middle">'
            f"{html.escape(subtitle)}</text>"
            f"</a></g>"
        )

    return (
        f'<svg class="graph" viewBox="0 0 {width} {height}" '
        f'role="img" aria-label="Upstream lineage graph">'
        '<defs><marker id="arrow" viewBox="0 0 10 10" refX="8" refY="5" '
        'markerWidth="6" markerHeight="6" orient="auto-start-reverse">'
        '<path d="M0 0 L10 5 L0 10 z" fill="#888" /></marker></defs>'
        f"{''.join(edges)}{''.join(nodes)}</svg>"
    )


def _depths(
    target: Relation, projection: dict[Relation, set[Relation]]
) -> dict[Relation, int]:
    memo: dict[Relation, int] = {}

    def depth(relation: Relation) -> int:
        if relation in memo:
            return memo[relation]
        upstreams = projection.get(relation, set())
        value = 0 if not upstreams else 1 + max(depth(u) for u in upstreams)
        memo[relation] = value
        return value

    depth(target)
    for relation in projection:
        depth(relation)
    return memo


def _model_section(names: tuple[str, ...]) -> str:
    if not names:
        return "<h2>Models</h2><p class='empty'>None</p>"
    items = "".join(
        f'<li><a href="/workbench?target={quote(name, safe="")}">{html.escape(name)}</a></li>'
        for name in names
    )
    return f"<h2>Models</h2><ul>{items}</ul>"


def _section(title: str, names: tuple[str, ...]) -> str:
    if not names:
        return f"<h2>{html.escape(title)}</h2><p class='empty'>None</p>"
    items = "".join(f"<li>{html.escape(name)}</li>" for name in names)
    return f"<h2>{html.escape(title)}</h2><ul>{items}</ul>"


def _cases_section(result: Discovery) -> str:
    if not result.cases:
        return "<h2>Cases</h2><p class='empty'>None</p>"
    items = "".join(
        (
            f'<li><a href="/workbench?case={quote(f"{case.target}/{case.name}", safe="")}">'
            f"{html.escape(case.target)} / {html.escape(case.name)}</a></li>"
        )
        for case in result.cases
    )
    return f"<h2>Cases</h2><ul>{items}</ul>"
