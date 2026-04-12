from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from .enums import EntryMode, SessionState, UserGoal


@dataclass(slots=True)
class QueryPlan:
    entry_mode: EntryMode
    product: str | None = None
    version_spec: str | None = None
    vuln_id: str | None = None
    risk_levels: list[str] = field(default_factory=list)
    require_public_poc: bool | None = None
    require_solution: bool | None = None
    malicious_only: bool | None = None
    source_hint: str | None = None
    user_goal: UserGoal = UserGoal.TRIAGE


@dataclass(slots=True)
class VersionRange:
    lower: str | None = None
    lower_inclusive: bool = True
    upper: str | None = None
    upper_inclusive: bool = True


@dataclass(slots=True)
class ProductImpact:
    product_name: str
    ecosystem: str | None = None
    affected_ranges: list[VersionRange] = field(default_factory=list)
    fixed_versions: list[str] = field(default_factory=list)
    known_versions: list[str] = field(default_factory=list)


@dataclass(slots=True)
class VulnRecord:
    record_id: str
    cve_id: str | None
    vuln_name: str | None
    description: str
    risk_level: str | None
    cvss_score: float | None
    has_public_poc: bool
    has_solution: bool
    is_malicious: bool
    product_impacts: list[ProductImpact] = field(default_factory=list)
    references: list[str] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class QuerySummary:
    entry_label: str
    target_label: str | None
    initial_candidate_count: int
    filtered_count: int
    highest_risk: str | None
    has_public_poc: bool | None
    has_solution: bool | None
    min_fixed_version_global: str | None
    min_fixed_version_same_branch: str | None
    conclusion: str


@dataclass(slots=True)
class CachedQueryResult:
    cache_id: str
    query_plan: QueryPlan
    matched_records: list[VulnRecord]
    summary: QuerySummary
    created_at: datetime


@dataclass(slots=True)
class FilterSpec:
    risk_levels: list[str] | None = None
    has_public_poc: bool | None = None
    has_solution: bool | None = None
    malicious_only: bool | None = None
    cve_ids: list[str] | None = None
    limit: int | None = None


@dataclass(slots=True)
class VulnSession:
    session_id: str
    state: SessionState
    planned_args: QueryPlan | None
    last_query_result: CachedQueryResult | None
    last_report_markdown: str | None
    last_filter_spec: FilterSpec | None
    created_at: datetime
    updated_at: datetime
    metadata: dict[str, Any]

