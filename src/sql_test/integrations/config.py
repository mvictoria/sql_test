import tomllib
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Self

from sql_test.engine import Catalog, mapped_sql_folder

TABLE = "sql-test"


class ConfigError(Exception):
    pass


@dataclass(frozen=True)
class RepositoryConfig:
    sqls: Path
    mapping: Path
    schemas: Path
    cases: Path

    @classmethod
    def load(cls, repository: Path) -> Self:
        root = repository.resolve()
        pyproject = root / "pyproject.toml"
        if not pyproject.is_file():
            raise ConfigError(f"{root} has no pyproject.toml")
        with pyproject.open("rb") as file:
            settings = tomllib.load(file).get("tool", {}).get(TABLE)
        if settings is None:
            raise ConfigError(f"{pyproject} has no [tool.{TABLE}] table")
        names = sorted(field.name for field in fields(cls))
        missing = [name for name in names if name not in settings]
        if missing:
            raise ConfigError(
                f"[tool.{TABLE}] in {pyproject} is missing: {', '.join(missing)}"
            )
        return cls(**{name: root / settings[name] for name in names})

    def catalog(self) -> Catalog:
        return mapped_sql_folder(
            sqls=self.sqls, mapping=self.mapping, schemas=self.schemas
        )
