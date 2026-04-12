from __future__ import annotations

from collections.abc import Sequence

from .models import QueryPlan, QuerySummary, VulnRecord
from .versioning import select_global_min_fixed_version, select_same_branch_fixed_version


def _entry_label(plan: QueryPlan) -> str:
    if plan.vuln_id:
        return f"漏洞编号（{plan.vuln_id}）"
    if plan.product:
        return f"精确软件名（{plan.product}）"
    return "自然语言解析"


def _target_label(plan: QueryPlan) -> str | None:
    parts = [item for item in [plan.product, plan.version_spec] if item]
    return " ".join(parts) if parts else plan.vuln_id


def build_query_summary(plan: QueryPlan, initial_candidates: int, matched: Sequence[VulnRecord]) -> QuerySummary:
    fixed_versions: list[str] = []
    highest_risk: str | None = None
    risk_order = {"critical": 4, "high": 3, "moderate": 2, "low": 1}
    has_public_poc = False
    has_solution = False

    for record in matched:
        has_public_poc = has_public_poc or record.has_public_poc
        has_solution = has_solution or record.has_solution
        if record.risk_level and (
            highest_risk is None or risk_order.get(record.risk_level, 0) > risk_order.get(highest_risk, 0)
        ):
            highest_risk = record.risk_level
        for impact in record.product_impacts:
            fixed_versions.extend(impact.fixed_versions)

    filtered_count = len(matched)
    target_label = _target_label(plan)
    conclusion = "未发现直接相关的漏洞记录。" if filtered_count == 0 else f"发现 {filtered_count} 条与当前排查目标相关的漏洞记录。"
    return QuerySummary(
        entry_label=_entry_label(plan),
        target_label=target_label,
        initial_candidate_count=initial_candidates,
        filtered_count=filtered_count,
        highest_risk=highest_risk,
        has_public_poc=has_public_poc if filtered_count else None,
        has_solution=has_solution if filtered_count else None,
        min_fixed_version_global=select_global_min_fixed_version(fixed_versions),
        min_fixed_version_same_branch=select_same_branch_fixed_version(plan.version_spec, fixed_versions),
        conclusion=conclusion,
    )


def build_analysis_brief(plan: QueryPlan, summary: QuerySummary, records: Sequence[VulnRecord]) -> dict[str, object]:
    return {
        "product": plan.product,
        "version_spec": plan.version_spec,
        "matched_count": len(records),
        "highest_risk": summary.highest_risk,
        "has_public_poc": summary.has_public_poc,
        "has_solution": summary.has_solution,
        "min_fixed_version_global": summary.min_fixed_version_global,
        "min_fixed_version_same_branch": summary.min_fixed_version_same_branch,
    }

