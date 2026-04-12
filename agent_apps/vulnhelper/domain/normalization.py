from __future__ import annotations

import re
from typing import Sequence


CONFIRM_WORDS = {"确认", "同意", "执行", "查吧", "可以", "yes", "ok", "okay", "go"}


def normalize_package_name(name: str) -> str:
    value = name.strip().lower()
    value = re.sub(r"\s+", "-", value)
    return value


def normalize_vuln_id(raw: str) -> str:
    return raw.strip().upper()


def normalize_risk_levels(values: Sequence[str] | None) -> list[str]:
    mapping = {
        "critical": "critical",
        "high": "high",
        "medium": "moderate",
        "moderate": "moderate",
        "low": "low",
        "严重": "critical",
        "高危": "high",
        "中危": "moderate",
        "低危": "low",
    }
    normalized: list[str] = []
    for value in values or ():
        item = mapping.get(value.strip().lower())
        if item and item not in normalized:
            normalized.append(item)
    return normalized


def is_confirmation_text(text: str) -> bool:
    normalized = text.strip().lower()
    return normalized in CONFIRM_WORDS or normalized.startswith("确认")
