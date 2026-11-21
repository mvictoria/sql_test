from sql_test.engine import Catalog, Relation
from sql_test.integrations.app.engine_access import plan as build_plan


def frontier_mocks(
    repo_catalog: Catalog, target: str, requested: tuple[str, ...]
) -> tuple[str, ...]:
    """Keep only a mock frontier: drop any mock the run would never read."""
    if not requested:
        return ()
    unused = {
        str(relation)
        for relation in build_plan(repo_catalog, target, requested, {}).unused
    }
    return tuple(
        sorted(name for name in requested if str(Relation.parse(name)) not in unused)
    )


def toggled_mocks(mocks: tuple[str, ...], name: str) -> tuple[str, ...]:
    """Mock `name` if it is not mocked yet, unmock it otherwise."""
    current = set(mocks)
    return tuple(sorted(current - {name} if name in current else current | {name}))
