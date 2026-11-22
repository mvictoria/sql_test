import tomllib
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Self

import tomlkit
from tomlkit.items import Table

from sql_test.engine import Catalog, mapped_sql_folder

TABLE = "sql-test"
FLAGS = "flags"
PATH_NAMES = ("sqls", "mapping", "schemas", "cases")


class ConfigError(Exception):
    pass


@dataclass(frozen=True)
class AppFlags:
    """Optional app toggles under `[tool.sql-test.flags]` — absent keys stay off."""

    sql_peek: bool = False

    @classmethod
    def load(cls, repository: Path) -> Self:
        root = repository.resolve()
        pyproject = root / "pyproject.toml"
        if not pyproject.is_file():
            return cls()
        with pyproject.open("rb") as file:
            settings = tomllib.load(file).get("tool", {}).get(TABLE) or {}
        flags = settings.get(FLAGS) or {}
        if not isinstance(flags, dict):
            flags = {}
        return cls(sql_peek=bool(flags.get("sql_peek", False)))


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
    def write(
        cls,
        repository: Path,
        relative: dict[str, str],
        *,
        flags: AppFlags | None = None,
    ) -> None:
        """Write `[tool.sql-test]` paths with tomlkit; leave the rest of the file as-is.

        When `flags` is set, also write `[tool.sql-test.flags]`; otherwise leave it alone.
        """
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
        if flags is not None:
            _write_flags(table, flags)
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


def _write_flags(table: Table, flags: AppFlags) -> None:
    if flags.sql_peek:
        existing = table.get(FLAGS)
        if not isinstance(existing, Table):
            existing = tomlkit.table()
            table[FLAGS] = existing
        existing["sql_peek"] = True
        return
    if FLAGS not in table:
        return
    flags_table = table[FLAGS]
    if isinstance(flags_table, Table) and "sql_peek" in flags_table:
        del flags_table["sql_peek"]
    if isinstance(flags_table, Table) and len(flags_table) == 0:
        del table[FLAGS]
