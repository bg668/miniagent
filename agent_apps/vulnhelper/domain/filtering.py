from __future__ import annotations

from collections.abc import Sequence

from .models import FilterSpec, QueryPlan, VulnRecord
from .normalization import normalize_package_name
from .versioning import version_in_range, version_matches_spec


def record_matches_product(record: VulnRecord, product: str) -> bool:
    target = normalize_package_name(product)
    return any(impact.product_name == target for impact in record.product_impacts)


def record_matches_version(record: VulnRecord, product: str, version_spec: str) -> bool:
    target = normalize_package_name(product)
    matched_impacts = [impact for impact in record.product_impacts if impact.product_name == target]
    if not matched_impacts:
        return False
    for impact in matched_impacts:
        if any(version_matches_spec(known, version_spec) for known in impact.known_versions):
            return True
        if any(version_in_range(version_spec, range_) for range_ in impact.affected_ranges if version_spec and version_spec[0].isdigit()):
            return True
        if version_spec.endswith(".x"):
            return bool(impact.affected_ranges or impact.known_versions)
    return False


def _matches_risk(record: VulnRecord, risk_levels: Sequence[str]) -> bool:
    return not risk_levels or (record.risk_level or "") in risk_levels


def filter_records(records: Sequence[VulnRecord], plan: QueryPlan) -> list[VulnRecord]:
    matched: list[VulnRecord] = []
    for record in records:
        if plan.vuln_id and (record.cve_id or "").upper() != plan.vuln_id.upper():
            continue
        if plan.product and not record_matches_product(record, plan.product):
            continue
        if plan.product and plan.version_spec and not record_matches_version(record, plan.product, plan.version_spec):
            continue
        if plan.risk_levels and not _matches_risk(record, plan.risk_levels):
            continue
        if plan.require_public_poc is True and not record.has_public_poc:
            continue
        if plan.require_solution is True and not record.has_solution:
            continue
        if plan.malicious_only is True and not record.is_malicious:
            continue
        matched.append(record)
    return matched


def filter_cached_records(records: Sequence[VulnRecord], filter_spec: FilterSpec) -> list[VulnRecord]:
    result = list(records)
    if filter_spec.risk_levels:
        result = [record for record in result if _matches_risk(record, filter_spec.risk_levels)]
    if filter_spec.has_public_poc is True:
        result = [record for record in result if record.has_public_poc]
    if filter_spec.has_solution is True:
        result = [record for record in result if record.has_solution]
    if filter_spec.malicious_only is True:
        result = [record for record in result if record.is_malicious]
    if filter_spec.cve_ids:
        wanted = {value.upper() for value in filter_spec.cve_ids}
        result = [record for record in result if (record.cve_id or "").upper() in wanted]
    if filter_spec.limit is not None:
        result = result[: filter_spec.limit]
    return result
