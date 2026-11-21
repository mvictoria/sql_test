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
        ("CI-2: versioned releases (patch)", "patch"),
        ("break the API (major)", "major"),
        ("add coverage report (minor)", "minor"),
        ("ENG-1: package skeleton", None),
        ("fix typo (patch) in docs", "patch"),
    ],
)
def test_bump_from_title(title, expected):
    assert cd_bump.bump_from_title(title) == expected


def test_bump_from_title_rejects_conflicting_tokens():
    with pytest.raises(ValueError, match="conflicting"):
        cd_bump.bump_from_title("ship it (minor) (major)")


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
