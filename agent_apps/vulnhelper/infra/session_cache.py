from __future__ import annotations

from ..domain.models import CachedQueryResult


class InMemoryQueryCache:
    def __init__(self) -> None:
        self._cache: dict[str, CachedQueryResult] = {}

    def put(self, session_id: str, result: CachedQueryResult) -> None:
        self._cache[session_id] = result

    def get(self, session_id: str) -> CachedQueryResult | None:
        return self._cache.get(session_id)

    def clear(self, session_id: str) -> None:
        self._cache.pop(session_id, None)

