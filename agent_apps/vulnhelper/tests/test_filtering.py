from agent_apps.vulnhelper.domain.enums import EntryMode, UserGoal
from agent_apps.vulnhelper.domain.filtering import filter_records
from agent_apps.vulnhelper.domain.models import ProductImpact, QueryPlan, VersionRange, VulnRecord


def test_filter_records_by_product_and_version() -> None:
    record = VulnRecord(
        record_id="r1",
        cve_id="CVE-2024-0001",
        vuln_name="demo",
        description="demo",
        risk_level="critical",
        cvss_score=9.8,
        has_public_poc=True,
        has_solution=True,
        is_malicious=False,
        product_impacts=[ProductImpact(product_name="tensorflow-cpu", affected_ranges=[VersionRange(lower="0", upper="2.5.3", upper_inclusive=False)])],
        references=[],
        raw={},
    )
    plan = QueryPlan(entry_mode=EntryMode.PRODUCT_VERSION, product="tensorflow-cpu", version_spec="2.4.1", user_goal=UserGoal.TRIAGE)
    assert filter_records([record], plan) == [record]

