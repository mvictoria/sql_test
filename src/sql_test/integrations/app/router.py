from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Request:
    method: str
    path: str
    query: dict[str, list[str]]
    repository: Path


@dataclass(frozen=True)
class Response:
    body: str
    status: int = 200
    content_type: str = "text/html; charset=utf-8"


Handler = Callable[[Request], Response | None]


class Router:
    def __init__(self) -> None:
        self._routes: dict[tuple[str, str], Handler] = {}

    def add(self, method: str, path: str, handler: Handler) -> None:
        self._routes[(method.upper(), path)] = handler

    def dispatch(self, request: Request) -> Response | None:
        path = request.path
        if path == "/index.html":
            path = "/"
        handler = self._routes.get((request.method.upper(), path))
        if handler is None:
            return None
        return handler(request)
