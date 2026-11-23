from sql_test.engine import Catalog, Kind, Relation
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


def delta_editors(
    repo_catalog: Catalog, target: str, mocks: tuple[str, ...]
) -> tuple[str, ...]:
    """For a merge target, every history mock also gets a CDC delta editor."""
    if not mocks:
        return ()
    relation = repo_catalog.resolve(target)
    if not any(
        operation.kind is Kind.MERGE for operation in repo_catalog.producers(relation)
    ):
        return ()
    return mocks
