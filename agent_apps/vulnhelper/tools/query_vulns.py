from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any
from uuid import uuid4

from ..agentsdk import AgentToolResult, TextContent

from ..domain.enums import EntryMode, UserGoal
from ..domain.filtering import filter_records
from ..domain.models import CachedQueryResult, QueryPlan
from ..domain.normalization import normalize_risk_levels
from ..domain.record_parser import parse_vuln_record
from ..domain.summarizer import build_query_summary
from ..infra.clock import utc_now
from ..infra.repository import VulnRepository
from ..infra.session_cache import InMemoryQueryCache
from .schemas import QUERY_VULNS_SCHEMA


def _coerce_query_plan(payload: dict[str, Any]) -> QueryPlan:
    return QueryPlan(
        entry_mode=EntryMode(payload.get("entry_mode", EntryMode.PRODUCT_VERSION.value)),
        product=payload.get("product"),
        version_spec=payload.get("version_spec"),
        vuln_id=payload.get("vuln_id"),
        risk_levels=normalize_risk_levels(payload.get("risk_levels", [])),
        require_public_poc=payload.get("require_public_poc"),
        require_solution=payload.get("require_solution"),
        malicious_only=payload.get("malicious_only"),
        source_hint=payload.get("source_hint"),
        user_goal=UserGoal(payload.get("user_goal", UserGoal.TRIAGE.value)),
    )


@dataclass
class QueryVulnsTool:
    repository: VulnRepository
    query_cache: InMemoryQueryCache
    name: str = "query_vulns"
    label: str = "Query Vulns"
    description: str | None = "Query the local vulnerability database using an approved plan."
    input_schema: dict[str, Any] = field(default_factory=lambda: QUERY_VULNS_SCHEMA)
    prepare_arguments = None

    async def execute(self, tool_call_id: str, params: dict[str, Any], cancel_token=None, on_update=None) -> AgentToolResult:
        del tool_call_id, cancel_token, on_update
        session_id = params["session_id"]
        plan = _coerce_query_plan(params["plan"])
        rows = self.repository.list_candidates(plan)
        parsed_records = [parse_vuln_record(row) for row in rows]
        matched = filter_records(parsed_records, plan)
        summary = build_query_summary(plan, initial_candidates=len(parsed_records), matched=matched)
        cached_result = CachedQueryResult(
            cache_id=str(uuid4()),
            query_plan=plan,
            matched_records=matched,
            summary=summary,
            created_at=utc_now(),
        )
        self.query_cache.put(session_id, cached_result)
        details = {
            "cache_id": cached_result.cache_id,
            "summary": asdict(summary),
            "filtered_count": len(matched),
        }
        return AgentToolResult(
            content=[TextContent(text=f"query_vulns completed: cache_id={cached_result.cache_id}, matched={len(matched)}")],
            details=details,
        )
