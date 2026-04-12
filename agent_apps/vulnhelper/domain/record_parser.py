from __future__ import annotations

import json
import re
from collections import defaultdict
from collections.abc import Mapping
from typing import Any

from .models import ProductImpact, VersionRange, VulnRecord
from .normalization import normalize_package_name
from .versioning import parse_range


RANGE_RE = re.compile(r"^(?P<name>.+?) affected range \(ECOSYSTEM\): (?P<expr>.+)$", re.IGNORECASE)
FIXED_RE = re.compile(r"^(?P<name>.+?) fixed in \(ECOSYSTEM\): (?P<version>.+)$", re.IGNORECASE)
KNOWN_RE = re.compile(r"^(?P<name>.+?) known affected versions: (?P<versions>.+)$", re.IGNORECASE)
PACKAGE_RE = re.compile(r"^(?P<name>.+?) \((?P<ecosystem>.+?)\)$")


def _load_json_list(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return []
    return [str(item) for item in value] if isinstance(value, list) else []


def _bool_from_db(value: Any) -> bool:
    return bool(int(value)) if isinstance(value, (int, str)) and str(value).isdigit() else bool(value)


def parse_vendors_products(raw: str | None) -> list[ProductImpact]:
    groups: dict[str, ProductImpact] = {}
    for item in _load_json_list(raw):
        range_match = RANGE_RE.match(item)
        if range_match:
            name = normalize_package_name(range_match.group("name"))
            impact = groups.setdefault(name, ProductImpact(product_name=name))
            impact.affected_ranges.append(parse_range(range_match.group("expr")))
            continue

        fixed_match = FIXED_RE.match(item)
        if fixed_match:
            name = normalize_package_name(fixed_match.group("name"))
            impact = groups.setdefault(name, ProductImpact(product_name=name))
            version = fixed_match.group("version").strip()
            if version not in impact.fixed_versions:
                impact.fixed_versions.append(version)
            continue

        known_match = KNOWN_RE.match(item)
        if known_match:
            name = normalize_package_name(known_match.group("name"))
            impact = groups.setdefault(name, ProductImpact(product_name=name))
            versions = [part.strip() for part in known_match.group("versions").split(",") if part.strip()]
            for version in versions:
                if version not in impact.known_versions:
                    impact.known_versions.append(version)
            continue

        package_match = PACKAGE_RE.match(item)
        if package_match:
            name = normalize_package_name(package_match.group("name"))
            impact = groups.setdefault(name, ProductImpact(product_name=name))
            impact.ecosystem = package_match.group("ecosystem").strip()
            continue

        name = normalize_package_name(item)
        groups.setdefault(name, ProductImpact(product_name=name))

    return list(groups.values())


def parse_vuln_record(row: Mapping[str, Any]) -> VulnRecord:
    references = _load_json_list(row.get("basicinfo.references"))
    product_impacts = parse_vendors_products(row.get("impact.vendors_products"))
    description = str(row.get("basicinfo.description") or "").strip()
    return VulnRecord(
        record_id=str(row.get("record_id") or ""),
        cve_id=str(row.get("basicinfo.cve_id") or "") or None,
        vuln_name=str(row.get("basicinfo.vuln_name") or "") or None,
        description=description,
        risk_level=str(row.get("evaluation.x_vpt.risk_level") or "") or None,
        cvss_score=float(row["evaluation.cvss_basic_score"]) if row.get("evaluation.cvss_basic_score") is not None else None,
        has_public_poc=_bool_from_db(row.get("intelligence.has_poc_public")),
        has_solution=_bool_from_db(row.get("intelligence.has_solution")),
        is_malicious="malicious" in description.lower() or "投毒" in description,
        product_impacts=product_impacts,
        references=references,
        raw=dict(row),
    )

