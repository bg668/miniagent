from __future__ import annotations

import re

from .enums import EntryMode, UserGoal
from .models import FilterSpec, QueryPlan
from .normalization import normalize_package_name, normalize_risk_levels, normalize_vuln_id


VULN_ID_RE = re.compile(r"\b(?:CVE-\d{4}-\d+|GHSA-[a-z0-9-]+|MAL-\d{4}-\d+)\b", re.I)
VERSION_RE = re.compile(r"\b\d+(?:\.\d+)*(?:\.x|x)?\b", re.I)
PACKAGE_RE = re.compile(r"[A-Za-z][A-Za-z0-9._-]{1,}")
LIMIT_RE = re.compile(r"(?:前|top\s*)(\d{1,3})", re.I)

PACKAGE_STOPWORDS = {
    "a",
    "an",
    "and",
    "apache",
    "check",
    "cve",
    "detail",
    "details",
    "fix",
    "for",
    "go",
    "have",
    "impact",
    "is",
    "list",
    "look",
    "malicious",
    "me",
    "need",
    "of",
    "only",
    "poc",
    "query",
    "risk",
    "show",
    "solution",
    "the",
    "to",
    "upgrade",
    "vuln",
    "what",
}


def extract_vuln_ids(text: str) -> list[str]:
    seen: list[str] = []
    for match in VULN_ID_RE.finditer(text):
        vuln_id = normalize_vuln_id(match.group(0))
        if vuln_id not in seen:
            seen.append(vuln_id)
    return seen


def extract_version_spec(text: str) -> str | None:
    matches = VERSION_RE.findall(VULN_ID_RE.sub(" ", text))
    return matches[0] if matches else None


def extract_risk_levels(text: str) -> list[str]:
    lowered = text.lower()
    collected: list[str] = []
    if any(keyword in lowered for keyword in ("critical", "严重", "严重漏洞")):
        collected.append("critical")
    if any(keyword in lowered for keyword in ("high", "高危")):
        collected.extend(["high", "critical"])
    if any(keyword in lowered for keyword in ("medium", "moderate", "中危")):
        collected.extend(["moderate", "high", "critical"])
    if any(keyword in lowered for keyword in ("low", "低危")):
        collected.append("low")

    normalized = normalize_risk_levels(collected)
    return normalized


def wants_public_poc(text: str) -> bool | None:
    lowered = text.lower()
    if any(keyword in lowered for keyword in ("公开 poc", "公开poc", "public poc", "poc")):
        return True
    return None


def wants_solution(text: str) -> bool | None:
    lowered = text.lower()
    if any(keyword in lowered for keyword in ("修复方案", "解决方案", "修复版本", "怎么修", "如何修", "升级到", "升级")):
        return True
    return None


def wants_malicious_only(text: str) -> bool | None:
    lowered = text.lower()
    if any(keyword in lowered for keyword in ("恶意", "投毒", "malicious")):
        return True
    return None


def extract_limit(text: str) -> int | None:
    match = LIMIT_RE.search(text)
    if match is None:
        return None
    try:
        return int(match.group(1))
    except ValueError:
        return None


def _iter_package_candidates(text: str) -> list[tuple[str, int]]:
    candidates: list[tuple[str, int]] = []
    for match in PACKAGE_RE.finditer(text):
        raw = match.group(0)
        normalized = normalize_package_name(raw)
        if normalized in PACKAGE_STOPWORDS:
            continue
        if normalized in {"critical", "high", "moderate", "low"}:
            continue
        if VULN_ID_RE.fullmatch(raw):
            continue
        candidates.append((normalized, match.start()))
    return candidates


def extract_product(text: str) -> str | None:
    scrubbed = VULN_ID_RE.sub(" ", text)
    version_match = VERSION_RE.search(scrubbed)
    candidates = _iter_package_candidates(scrubbed)
    if not candidates:
        return None

    if version_match is not None:
        version_pos = version_match.start()
        before = [candidate for candidate in candidates if candidate[1] < version_pos]
        if before:
            return before[-1][0]

    return candidates[0][0]


def infer_user_goal(text: str) -> UserGoal:
    if wants_solution(text):
        return UserGoal.FIX_VERSION
    if any(keyword in text.lower() for keyword in ("详情", "细节", "detail", "details", "说明")):
        return UserGoal.DETAIL_SEARCH
    if any(keyword in text for keyword in ("影响", "受影响")):
        return UserGoal.IMPACT_CHECK
    return UserGoal.TRIAGE


def parse_query_plan(text: str) -> QueryPlan:
    vuln_ids = extract_vuln_ids(text)
    product = extract_product(text)
    version_spec = extract_version_spec(text)
    malicious_only = wants_malicious_only(text)
    return QueryPlan(
        entry_mode=EntryMode.IDENTIFIER if vuln_ids else (EntryMode.MALICIOUS_PACKAGE if malicious_only else EntryMode.PRODUCT_VERSION),
        product=product,
        version_spec=version_spec,
        vuln_id=vuln_ids[0] if vuln_ids else None,
        risk_levels=extract_risk_levels(text),
        require_public_poc=wants_public_poc(text),
        require_solution=wants_solution(text),
        malicious_only=malicious_only,
        source_hint=None,
        user_goal=infer_user_goal(text),
    )


def build_confirmation_text(plan: QueryPlan) -> str:
    target = " ".join(part for part in [plan.product, plan.version_spec or plan.vuln_id] if part) or "未明确目标"
    traits: list[str] = []
    if plan.risk_levels:
        traits.append(f"风险={','.join(plan.risk_levels)}")
    if plan.require_public_poc:
        traits.append("公开POC=是")
    if plan.require_solution:
        traits.append("修复方案=是")
    if plan.malicious_only:
        traits.append("恶意包=是")
    suffix = f"；附加过滤：{'；'.join(traits)}" if traits else ""
    return f"将按 {plan.entry_mode.value} 入口检索 {target}{suffix}。回复“确认”即可执行。"


def parse_filter_spec(text: str) -> FilterSpec:
    return FilterSpec(
        risk_levels=extract_risk_levels(text) or None,
        has_public_poc=wants_public_poc(text),
        has_solution=wants_solution(text),
        malicious_only=wants_malicious_only(text),
        cve_ids=extract_vuln_ids(text) or None,
        limit=extract_limit(text),
    )
