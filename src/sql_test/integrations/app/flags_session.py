"""Per-browser-tab flag overrides (session) over durable `[tool.sql-test.flags]`."""

from __future__ import annotations

from pathlib import Path

from nicegui import context

from sql_test.integrations.config import AppFlags

_OVERRIDES: dict[str, dict[str, bool]] = {}


def clear_all_overrides() -> None:
    """Test helper: drop every session override."""
    _OVERRIDES.clear()


def session_key() -> str:
    """Stable id for this browser tab (NiceGUI tab_id after the socket connects)."""
    try:
        client = context.client
    except RuntimeError:
        return "no-client"
    # Before handshake, tab_id is unset and client.id changes every navigation.
    # Pages paint durable flags first; on_connect (and click handlers) use tab_id.
    tab_id = getattr(client, "tab_id", None)
    if tab_id is None:
        return f"pending:{client.id}"
    return str(tab_id)


def get_overrides() -> dict[str, bool]:
    return dict(_OVERRIDES.get(session_key(), {}))


def set_overrides(overrides: dict[str, bool]) -> None:
    """Replace this tab's session overrides (does not write pyproject.toml)."""
    key = session_key()
    cleaned = {name: bool(value) for name, value in overrides.items()}
    if cleaned:
        _OVERRIDES[key] = cleaned
    else:
        _OVERRIDES.pop(key, None)


def clear_overrides() -> None:
    _OVERRIDES.pop(session_key(), None)


def effective_flags(repository: Path) -> AppFlags:
    """Durable flags from disk, with this tab's session overrides on top."""
    durable = AppFlags.load(repository)
    overrides = get_overrides()
    if not overrides:
        return durable
    return AppFlags(sql_peek=overrides.get("sql_peek", durable.sql_peek))
