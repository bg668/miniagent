from __future__ import annotations

from dataclasses import replace
from dataclasses import dataclass, field
from typing import Any

from ..agentsdk import AgentToolResult, TextContent

from ..domain.filtering import filter_cached_records
from ..domain.models import FilterSpec
from ..domain.normalization import normalize_risk_levels, normalize_vuln_id
from ..infra.session_cache import InMemoryQueryCache
from .schemas import FILTER_CACHED_RESULTS_SCHEMA


def _coerce_filter_spec(payload: dict[str, Any]) -> FilterSpec:
    cve_ids = payload.get("cve_ids")
    return FilterSpec(
        risk_levels=normalize_risk_levels(payload.get("risk_levels", [])) or None,
        has_public_poc=payload.get("has_public_poc"),
        has_solution=payload.get("has_solution"),
        malicious_only=payload.get("malicious_only"),
        cve_ids=[normalize_vuln_id(value) for value in cve_ids] if cve_ids else None,
        limit=payload.get("limit"),
    )


@dataclass
class FilterCachedResultsTool:
    query_cache: InMemoryQueryCache
    name: str = "filter_cached_results"
    label: str = "Filter Cached Results"
    description: str | None = "Filter previously cached vulnerability results in memory."
    input_schema: dict[str, Any] = field(default_factory=lambda: FILTER_CACHED_RESULTS_SCHEMA)
    prepare_arguments = None

    async def execute(self, tool_call_id: str, params: dict[str, Any], cancel_token=None, on_update=None) -> AgentToolResult:
        del tool_call_id, cancel_token, on_update
        session_id = params["session_id"]
        cached = self.query_cache.get(session_id)
        if cached is None:
            return AgentToolResult(content=[TextContent(text="No cached query result is available for this session.")], details={})

        filter_spec = _coerce_filter_spec(params["filter_spec"])
        rows = filter_cached_records(cached.matched_records, filter_spec)
        self.query_cache.put(
            session_id,
            replace(
                cached,
                matched_records=rows,
                summary=replace(cached.summary, filtered_count=len(rows)),
            ),
        )
        details = {
            "filtered_count": len(rows),
            "applied_filters": params["filter_spec"],
            "rows": [
                {
                    "cve_id": record.cve_id or record.record_id,
                    "risk_label": record.risk_level or "unknown",
                    "summary": record.description.splitlines()[0][:120],
                }
                for record in rows
            ],
        }
        return AgentToolResult(
            content=[TextContent(text=f"filter_cached_results completed: matched={len(rows)}")],
            details=details,
        )
