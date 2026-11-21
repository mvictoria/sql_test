import ast
from pathlib import Path

import pytest

PACKAGE = Path(__file__).parent.parent / "src" / "sql_test"


def imported_modules(layer, exclude=()):
    for path in (PACKAGE / layer).rglob("*.py"):
        if any(path.is_relative_to(PACKAGE / layer / part) for part in exclude):
            continue
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.Import):
                yield from (alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                yield node.module


@pytest.mark.parametrize(
    ("layer", "forbidden"),
    [
        (
            "engine",
            [
                "sql_test.executors",
                "sql_test.testing",
                "sql_test.integrations",
                "duckdb",
            ],
        ),
        ("executors", ["sql_test.testing", "sql_test.integrations"]),
        ("testing", ["sql_test.executors", "sql_test.integrations", "duckdb"]),
    ],
)
def test_layer_does_not_import(layer, forbidden):
    assert (PACKAGE / layer).is_dir()
    imports = set(imported_modules(layer))
    assert not {
        name
        for name in imports
        for other in forbidden
        if name == other or name.startswith(f"{other}.")
    }


@pytest.mark.parametrize(
    ("layer", "exclude", "fronts"),
    [
        ("testing", (), ["sql_test.engine"]),
        (
            "integrations",
            ("app",),
            ["sql_test.engine", "sql_test.executors", "sql_test.testing"],
        ),
    ],
)
def test_layer_imports_other_layers_through_their_front_door(layer, exclude, fronts):
    imports = set(imported_modules(layer, exclude))
    assert not {
        name for name in imports for front in fronts if name.startswith(f"{front}.")
    }
