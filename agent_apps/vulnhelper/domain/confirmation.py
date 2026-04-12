from __future__ import annotations

from .models import QueryPlan


def build_confirmation_target(plan: QueryPlan) -> str:
    parts = [part for part in [plan.product, plan.version_spec] if part]
    if plan.vuln_id:
        parts.insert(0, plan.vuln_id)
    return " ".join(parts) if parts else "未明确对象"

