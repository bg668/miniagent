from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from packaging.version import InvalidVersion, Version

from .models import VersionRange


@dataclass(slots=True)
class ParsedBranchSpec:
    raw: str
    prefix: str


def parse_version(value: str) -> Version | None:
    try:
        return Version(value.strip())
    except InvalidVersion:
        return None


def parse_range(expr: str) -> VersionRange:
    parts = [part.strip() for part in expr.split(",") if part.strip()]
    range_ = VersionRange()
    for part in parts:
        if part.startswith(">="):
            range_.lower = part[2:].strip()
            range_.lower_inclusive = True
        elif part.startswith(">"):
            range_.lower = part[1:].strip()
            range_.lower_inclusive = False
        elif part.startswith("<="):
            range_.upper = part[2:].strip()
            range_.upper_inclusive = True
        elif part.startswith("<"):
            range_.upper = part[1:].strip()
            range_.upper_inclusive = False
    return range_


def parse_branch_spec(spec: str) -> ParsedBranchSpec | None:
    raw = spec.strip()
    if raw.endswith(".x"):
        return ParsedBranchSpec(raw=raw, prefix=raw[:-2] + ".")
    if raw.endswith("x"):
        return ParsedBranchSpec(raw=raw, prefix=raw[:-1])
    return None


def version_in_range(version: str, range_: VersionRange) -> bool:
    current = parse_version(version)
    if current is None:
        return False

    if range_.lower:
        lower = parse_version(range_.lower)
        if lower is not None:
            if current < lower or (current == lower and not range_.lower_inclusive):
                return False

    if range_.upper:
        upper = parse_version(range_.upper)
        if upper is not None:
            if current > upper or (current == upper and not range_.upper_inclusive):
                return False

    return True


def version_matches_spec(version: str, version_spec: str) -> bool:
    branch = parse_branch_spec(version_spec)
    if branch is not None:
        return version.startswith(branch.prefix)
    if "," in version_spec or version_spec.startswith((">", "<")):
        return version_in_range(version, parse_range(version_spec))
    return version == version_spec


def select_global_min_fixed_version(versions: Sequence[str]) -> str | None:
    parsed = [(parse_version(value), value) for value in versions]
    valid = [(parsed_version, raw) for parsed_version, raw in parsed if parsed_version is not None]
    if not valid:
        return None
    valid.sort(key=lambda item: item[0])
    return valid[0][1]


def select_same_branch_fixed_version(current: str | None, versions: Sequence[str]) -> str | None:
    if not current:
        return None
    branch = parse_branch_spec(current)
    if branch is None:
        if current.count(".") >= 1:
            prefix = ".".join(current.split(".")[:2]) + "."
        else:
            prefix = current + "."
    else:
        prefix = branch.prefix

    same_branch = [value for value in versions if value.startswith(prefix)]
    return select_global_min_fixed_version(same_branch)

