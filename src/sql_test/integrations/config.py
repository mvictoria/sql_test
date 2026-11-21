import tomllib
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Self

import tomlkit

from sql_test.engine import Catalog, mapped_sql_folder

TABLE = "sql-test"
PATH_NAMES = ("sqls", "mapping", "schemas", "cases")


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
        relative = cls.read_relative(root)
        return cls(**{name: root / relative[name] for name in PATH_NAMES})

    @classmethod
    def read_relative(cls, repository: Path) -> dict[str, str]:
        """Relative path strings from `[tool.sql-test]`, or raise ConfigError."""
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
        return {name: str(settings[name]) for name in names}

    @classmethod
    def write(cls, repository: Path, relative: dict[str, str]) -> None:
        """Write `[tool.sql-test]` paths with tomlkit; leave the rest of the file as-is."""
        root = repository.resolve()
        cls.validate(root, relative)
        pyproject = root / "pyproject.toml"
        if pyproject.is_file():
            document = tomlkit.parse(pyproject.read_text())
        else:
            document = tomlkit.document()
        tool = document.setdefault("tool", tomlkit.table())
        table = tool.setdefault(TABLE, tomlkit.table())
        for name in PATH_NAMES:
            table[name] = relative[name]
        pyproject.write_text(tomlkit.dumps(document))

    @classmethod
    def validate(cls, repository: Path, relative: dict[str, str]) -> None:
        """Paths must exist; with them the catalog must discover SQL, mapping, and schemas."""
        root = repository.resolve()
        missing = [
            name for name in PATH_NAMES if name not in relative or not relative[name]
        ]
        if missing:
            raise ConfigError(f"missing: {', '.join(missing)}")
        paths = {name: root / relative[name] for name in PATH_NAMES}
        for name, path in paths.items():
            if not path.exists():
                raise ConfigError(f"{name} path does not exist: {relative[name]}")
        try:
            catalog = mapped_sql_folder(
                sqls=paths["sqls"], mapping=paths["mapping"], schemas=paths["schemas"]
            )
        except Exception as error:
            raise ConfigError(f"catalog could not be built: {error}") from error
        if not catalog.operations:
            raise ConfigError("mapping discovers no SQL operations")
        if not catalog.relations():
            raise ConfigError("schemas discover no relations")

    def catalog(self) -> Catalog:
        return mapped_sql_folder(
            sqls=self.sqls, mapping=self.mapping, schemas=self.schemas
        )
