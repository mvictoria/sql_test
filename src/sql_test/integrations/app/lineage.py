import html
from pathlib import Path
from urllib.parse import urlencode

from sql_test.engine.planner.plan import Plan, State
from sql_test.engine.relation import Relation
from sql_test.integrations.app.engine_access import plan as build_plan


def workbench_query(
    base_query: dict[str, str],
    *,
    view: str,
    mocks: tuple[str, ...],
) -> str:
    params: list[tuple[str, str]] = [*(base_query.items()), ("view", view)]
    params.extend(("mock", name) for name in mocks)
    return "/workbench?" + urlencode(params)


def frontier_mocks(
    repository: Path, target: str, requested: tuple[str, ...]
) -> tuple[str, ...]:
    """Keep only a mock frontier: drop any mock the run would never read."""
    if not requested:
        return ()
    unused = {
        str(relation)
        for relation in build_plan(repository, target, requested, {}).unused
    }
    return tuple(
        sorted(name for name in requested if str(Relation.parse(name)) not in unused)
    )


def lineage_section(
    repository: Path,
    target: str,
    mocks: tuple[str, ...],
    base_query: dict[str, str],
    grid_rows: dict[str, list[dict[str, str]]],
    counts: dict[Relation, int] | None = None,
) -> str:
    plan = build_plan(repository, target, mocks, grid_rows)
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
    return (
        f"<h2>Lineage</h2>{status}{legend}"
        f"{lineage_graph(plan, mocks, base_query, counts)}"
    )


def lineage_graph(
    plan: Plan,
    mocks: tuple[str, ...],
    base_query: dict[str, str],
    counts: dict[Relation, int] | None = None,
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
        count = None if counts is None else counts.get(relation)
        if count is not None:
            subtitle = f"{count} rows"
        count_attrs = (
            ""
            if count is None
            else (f' data-row-count="{count}" data-relation="{html.escape(name)}"')
        )
        x = cx - node_w / 2
        y = cy - node_h / 2
        if name == target_name:
            nodes.append(
                f'<g class="{" ".join(classes)}"{count_attrs}>'
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
        href = workbench_query(base_query, view="lineage", mocks=next_mocks)
        nodes.append(
            f'<g class="{" ".join(classes)}"{count_attrs}>'
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
