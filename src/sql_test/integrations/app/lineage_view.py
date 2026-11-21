from collections.abc import Callable

from nicegui import ui

from sql_test.engine.planner.plan import Plan, State
from sql_test.engine.relation import Relation
from sql_test.integrations.app.engine_access import plan as build_plan
from sql_test.integrations.app.state import WorkbenchState

_STATE_LABEL = {
    State.GIVEN: "mocked",
    State.EXECUTED: "will execute",
    State.SOURCE: "source",
    State.PRUNED: "pruned",
}
_STATE_MARKER = {
    State.GIVEN: "mocked",
    State.EXECUTED: "executed",
    State.SOURCE: "source",
    State.PRUNED: "pruned",
}

_CSS = """
.lineage-panel {
  --ink: #1a2332;
  --muted: #5c6b7a;
  --surface: #f4f7fb;
  --mocked: #2f5aa8;
  --mocked-soft: #e8f0fc;
  --executed: #1f7a4d;
  --executed-soft: #e6f6ee;
  --source: #b86a12;
  --source-soft: #fff4e4;
  --target: #0f6e6a;
  --target-soft: #e4f6f4;
  --needs: #8a93a0;
  --needs-soft: #eef1f4;
  --ready: #1f7a4d;
  --blocked: #b45309;
  background:
    radial-gradient(1200px 280px at 10% -10%, #e8f2ff 0%, transparent 55%),
    radial-gradient(900px 240px at 90% 0%, #e7f7f3 0%, transparent 50%),
    var(--surface);
  border: 1px solid #e2e8f0;
  border-radius: 16px;
  padding: 1.25rem 1.35rem 1.5rem;
}
.lineage-panel .lineage-title {
  font-family: "IBM Plex Sans", "Segoe UI", sans-serif;
  font-weight: 650;
  letter-spacing: -0.02em;
  color: var(--ink);
  font-size: 1.05rem;
}
.lineage-status {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  border-radius: 999px;
  padding: 0.28rem 0.75rem;
  font-size: 0.82rem;
  font-weight: 600;
  margin: 0.55rem 0 0.7rem;
}
.lineage-status.ready {
  color: var(--ready);
  background: var(--executed-soft);
}
.lineage-status.blocked {
  color: var(--blocked);
  background: #fff1e0;
}
.lineage-legend {
  display: flex;
  flex-wrap: wrap;
  gap: 0.45rem;
  margin: 0 0 1rem;
}
.lineage-chip {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  border-radius: 999px;
  padding: 0.18rem 0.55rem;
  font-size: 0.72rem;
  font-weight: 600;
  letter-spacing: 0.02em;
  text-transform: uppercase;
  background: white;
  border: 1px solid #e2e8f0;
  color: var(--muted);
}
.lineage-chip .dot {
  width: 0.55rem;
  height: 0.55rem;
  border-radius: 50%;
}
.lineage-chip .dot.mocked { background: var(--mocked); }
.lineage-chip .dot.executed { background: var(--executed); }
.lineage-chip .dot.source { background: var(--source); }
.lineage-chip .dot.target { background: var(--target); }
.lineage-chip .dot.needs { background: var(--needs); }
.lineage-graph {
  width: 100%;
  overflow-x: auto;
}
.lineage-graph .mermaid {
  min-height: 12rem;
}
.lineage-hit-targets {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip: rect(0 0 0 0);
}
"""


def lineage_css() -> str:
    return _CSS


def lineage_view(state: WorkbenchState, on_toggle: Callable[[str], None]) -> None:
    plan = build_plan(state.repository, state.target, state.mocks, state.grid_rows)
    counts = None if state.run_result is None else state.run_result.counts
    visible = _visible(plan)
    with ui.element("div").classes("lineage-panel w-full"):
        ui.label("Lineage").classes("lineage-title")
        if plan.needs_rows:
            names = ", ".join(sorted(str(name) for name in plan.needs_rows))
            ui.label(f"Blocked — still need rows: {names}").classes(
                "lineage-status blocked"
            ).mark("plan-blocked")
        else:
            ui.label("Ready to run — all needs_rows covered").classes(
                "lineage-status ready"
            ).mark("plan-ready")
        with ui.row().classes("lineage-legend"):
            for kind, label in (
                ("target", "target"),
                ("mocked", "mocked"),
                ("executed", "will execute"),
                ("source", "source"),
                ("needs", "needs rows"),
            ):
                with ui.element("span").classes("lineage-chip"):
                    ui.element("span").classes(f"dot {kind}")
                    ui.label(label).classes("text-caption")
            with ui.element("span").classes("lineage-chip"):
                ui.label("click a node to mock / unmock").classes("text-caption")
        diagram = _mermaid(plan, visible, counts)
        with ui.element("div").classes("lineage-graph").mark("lineage-graph"):
            ui.mermaid(
                diagram,
                on_node_click=lambda e: _clicked(e.node_id, plan, on_toggle),
            )
        # Hit targets for User tests (mermaid SVG nodes are not clickable there).
        with ui.element("div").classes("lineage-hit-targets"):
            for relation in sorted(visible, key=str):
                _hit_target(plan, relation, counts, on_toggle)


def lineage_columns(plan: Plan) -> dict[int, list[Relation]]:
    """Visible relations grouped by depth: sources on the left, target on the right."""
    visible = _visible(plan)
    projection = _projection(plan, visible)
    columns: dict[int, list[Relation]] = {}
    for relation, depth in _depths(plan.target, projection).items():
        if relation in visible:
            columns.setdefault(depth, []).append(relation)
    for relations in columns.values():
        relations.sort(key=str)
    return columns


def _clicked(node_id: str, plan: Plan, on_toggle: Callable[[str], None]) -> None:
    if node_id == str(plan.target):
        return
    on_toggle(node_id)


def _hit_target(
    plan: Plan,
    relation: Relation,
    counts: dict[Relation, int] | None,
    on_toggle: Callable[[str], None],
) -> None:
    state = plan.states[relation]
    name = str(relation)
    is_target = relation == plan.target
    needs = relation in plan.needs_rows
    markers = [f"node-{name}", f"node-{_STATE_MARKER[state]}"]
    if is_target:
        markers.append("node-target")
    if needs:
        markers.append("needs-rows")
    button = ui.button(name).mark(" ".join(markers))
    if is_target:
        button.props("disable")
    else:
        button.on_click(lambda _, name=name: on_toggle(name))
    if counts is not None and relation in counts:
        ui.label(f"{counts[relation]} rows").mark(f"rows-{name}")
    upstreams = sorted(
        str(upstream)
        for upstream in plan.built_from.get(relation, ())
        if plan.states.get(upstream, State.PRUNED) is not State.PRUNED
    )
    if upstreams:
        ui.label("reads " + ", ".join(upstreams)).mark(f"reads-{name}")


def _mermaid(
    plan: Plan,
    visible: set[Relation],
    counts: dict[Relation, int] | None,
) -> str:
    lines = [
        "flowchart LR",
        "  classDef mocked fill:#e8f0fc,stroke:#2f5aa8,color:#1a2332",
        "  classDef executed fill:#e6f6ee,stroke:#1f7a4d,color:#1a2332",
        "  classDef source fill:#fff4e4,stroke:#b86a12,color:#1a2332",
        "  classDef target fill:#e4f6f4,stroke:#0f6e6a,stroke-width:2px,color:#1a2332",
        "  classDef needs fill:#eef1f4,stroke:#8a93a0,color:#6d7886",
    ]
    for relation in sorted(visible, key=str):
        name = str(relation)
        node_id = _node_id(name)
        kind = _class_name(plan, relation)
        label = _node_label(plan, relation, counts)
        lines.append(f'  {node_id}["{_escape(label)}"]:::{kind}')
    for downstream in sorted(visible, key=str):
        for upstream in sorted(plan.built_from.get(downstream, ()), key=str):
            if upstream not in visible:
                continue
            lines.append(f"  {_node_id(str(upstream))} --> {_node_id(str(downstream))}")
    return "\n".join(lines)


def _class_name(plan: Plan, relation: Relation) -> str:
    if relation == plan.target:
        return "target"
    if relation in plan.needs_rows:
        return "needs"
    return {
        State.GIVEN: "mocked",
        State.EXECUTED: "executed",
        State.SOURCE: "source",
        State.PRUNED: "pruned",
    }[plan.states[relation]]


def _node_label(
    plan: Plan,
    relation: Relation,
    counts: dict[Relation, int] | None,
) -> str:
    name = str(relation)
    if counts is not None and relation in counts:
        return f"{name}<br/>{counts[relation]} rows"
    if relation == plan.target:
        return f"{name}<br/>table under test"
    if relation in plan.needs_rows:
        return f"{name}<br/>needs rows"
    reason = plan.source_reasons.get(relation)
    if reason is not None:
        return f"{name}<br/>{reason.value}"
    return f"{name}<br/>{_STATE_LABEL[plan.states[relation]]}"


def _node_id(name: str) -> str:
    """Mermaid node id: keep alnum/underscore, otherwise a stable escaped form."""
    if name.replace("_", "").isalnum():
        return name
    return "n_" + "".join(f"{ord(ch):x}" for ch in name)


def _escape(text: str) -> str:
    return text.replace('"', "#quot;")


def _visible(plan: Plan) -> set[Relation]:
    return {
        relation for relation, state in plan.states.items() if state is not State.PRUNED
    }


def _projection(plan: Plan, visible: set[Relation]) -> dict[Relation, set[Relation]]:
    return {
        relation: {upstream for upstream in upstreams if upstream in visible}
        for relation, upstreams in plan.built_from.items()
        if relation in visible
    }


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
