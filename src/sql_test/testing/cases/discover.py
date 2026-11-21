from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CaseSummary:
    target: str
    name: str
    mocks: tuple[str, ...]
    has_expected: bool


def discover_cases(cases_root: Path) -> list[CaseSummary]:
    if not cases_root.is_dir():
        return []
    found: list[CaseSummary] = []
    for target_dir in sorted(path for path in cases_root.iterdir() if path.is_dir()):
        for case_dir in sorted(path for path in target_dir.iterdir() if path.is_dir()):
            csvs = {path.stem for path in case_dir.glob("*.csv")}
            mocks = tuple(sorted(csvs - {"expected"}))
            found.append(
                CaseSummary(
                    target=target_dir.name,
                    name=case_dir.name,
                    mocks=mocks,
                    has_expected="expected" in csvs,
                )
            )
    return found


def case_folders(root: Path) -> list[Path]:
    return sorted(
        case
        for target in root.iterdir()
        if target.is_dir()
        for case in target.iterdir()
        if case.is_dir()
    )


def case_id(folder: Path) -> str:
    return f"{folder.parent.name}/{folder.name}"
