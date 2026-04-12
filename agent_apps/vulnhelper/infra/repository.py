from __future__ import annotations

from typing import Any, Protocol

from ..domain.models import QueryPlan


class VulnRepository(Protocol):
    def list_candidates(self, plan: QueryPlan) -> list[dict[str, Any]]:
        ...

