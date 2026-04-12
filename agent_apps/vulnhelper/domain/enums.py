from __future__ import annotations

from enum import Enum


class SessionState(str, Enum):
    IDLE = "idle"
    WAITING_FOR_CONFIRMATION = "waiting_for_confirmation"
    EXECUTING_QUERY = "executing_query"
    REPORT_READY = "report_ready"
    DRILLDOWN_READY = "drilldown_ready"
    FAILED = "failed"


class EntryMode(str, Enum):
    PRODUCT_VERSION = "product_version"
    IDENTIFIER = "identifier"
    FILTER_ONLY = "filter_only"
    MALICIOUS_PACKAGE = "malicious_package"


class UserGoal(str, Enum):
    IMPACT_CHECK = "impact_check"
    FIX_VERSION = "fix_version"
    TRIAGE = "triage"
    DETAIL_SEARCH = "detail_search"


class FixStrategy(str, Enum):
    GLOBAL_MIN = "global_min"
    SAME_BRANCH = "same_branch"
    UNKNOWN = "unknown"

