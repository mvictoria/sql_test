import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "cd_bump.py"


def _load():
    spec = importlib.util.spec_from_file_location("cd_bump", SCRIPT)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


cd_bump = _load()


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("(patch) CI-2: versioned releases", "patch"),
        ("(Patch) CI-2: versioned releases", "patch"),
        ("(MAJOR) break the API", "major"),
        ("(minor) add coverage report", "minor"),
        ("ENG-1: package skeleton", None),
        ("CI-2: versioned releases (patch)", None),
        ("(patch) notes about major and minor", "patch"),
        ("(minor) (major) ship both", "minor"),
    ],
)
def test_bump_from_title(title, expected):
    assert cd_bump.bump_from_title(title) == expected


@pytest.mark.parametrize(
    ("latest", "bump", "expected"),
    [
        (None, "patch", "v0.0.1"),
        ("", "minor", "v0.1.0"),
        ("v0.1.0", "patch", "v0.1.1"),
        ("v0.1.9", "minor", "v0.2.0"),
        ("v0.2.3", "major", "v1.0.0"),
        ("0.1.0", "patch", "v0.1.1"),
    ],
)
def test_next_tag(latest, bump, expected):
    assert cd_bump.next_tag(latest, bump) == expected
