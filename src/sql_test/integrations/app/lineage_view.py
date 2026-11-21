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
_STATE_STYLE = {
    "executed": "background:#e7f6ed;border:1.5px solid #1b7a45",
    "mocked": "background:#e8eefc;border:1.5px solid #3451b2",
    "source": "background:#fff6e0;border:1.5px solid #c80",
    "target": "background:#f3e8ff;border:2.5px solid #7c3aed",
    "needs-rows": "background:#f3f3f3;border:1.5px solid #ccc;color:#999",
}


def lineage_view(state: WorkbenchState, on_toggle: Callable[[str], None]) -> None:
    plan = build_plan(state.repository, state.target, state.mocks, state.grid_rows)
    counts = None if state.run_result is None else state.run_result.counts
    ui.label("Lineage").classes("text-subtitle1")
    if plan.needs_rows:
        names = ", ".join(sorted(str(name) for name in plan.needs_rows))
        ui.label(f"Blocked — still need rows: {names}").classes("text-orange-9").mark(
            "plan-blocked"
        )
    else:
        ui.label("Ready to run — all needs_rows covered").classes("text-green-9").mark(
            "plan-ready"
        )
    ui.label(
        "target (purple) · mocked (blue) · will execute (green) · source (amber)"
        " · grey = needs rows — pruned hidden; click a node to mock/unmock"
    ).classes("text-caption text-grey-8")
    columns = lineage_columns(plan)
    with ui.row().classes("items-center no-wrap gap-6").mark("lineage-graph"):
        for position, (_, relations) in enumerate(sorted(columns.items())):
            if position:
                ui.icon("arrow_forward").classes("text-grey-6")
            with ui.column().classes("gap-3"):
                for relation in relations:
                    _node(plan, relation, counts, on_toggle)


def lineage_columns(plan: Plan) -> dict[int, list[Relation]]:
    """Visible relations grouped by depth: sources on the left, target on the right."""
    visible = {
        relation for relation, state in plan.states.items() if state is not State.PRUNED
    }
    projection = {
        relation: {upstream for upstream in upstreams if upstream in visible}
        for relation, upstreams in plan.built_from.items()
        if relation in visible
    }
    columns: dict[int, list[Relation]] = {}
    for relation, depth in _depths(plan.target, projection).items():
        if relation in visible:
            columns.setdefault(depth, []).append(relation)
    for relations in columns.values():
        relations.sort(key=str)
    return columns


def _node(
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
    style = _STATE_STYLE[_STATE_MARKER[state]]
    if is_target:
        markers.append("node-target")
        style = _STATE_STYLE["target"]
    if needs:
        markers.append("needs-rows")
        if not is_target:
            style = _STATE_STYLE["needs-rows"]
    reason = plan.source_reasons.get(relation)
    subtitle = (
        reason.value if reason else ("needs rows" if needs else _STATE_LABEL[state])
    )
    if is_target:
        subtitle = "table under test"
    count = None if counts is None else counts.get(relation)
    if count is not None:
        subtitle = f"{count} rows"
    card = ui.card().classes("w-52 gap-0 p-3").style(style).mark(" ".join(markers))
    if not is_target:
        card.classes("cursor-pointer").on("click", lambda _, name=name: on_toggle(name))
    with card:
        ui.label(name).classes("text-body2 text-weight-medium")
        subtitle_label = ui.label(subtitle).classes("text-caption uppercase")
        if count is not None:
            subtitle_label.mark(f"rows-{name}")
        upstreams = sorted(
            str(upstream)
            for upstream in plan.built_from.get(relation, ())
            if plan.states.get(upstream, State.PRUNED) is not State.PRUNED
        )
        if upstreams:
            ui.label("reads " + ", ".join(upstreams)).classes(
                "text-caption text-grey-7"
            ).mark(f"reads-{name}")


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
