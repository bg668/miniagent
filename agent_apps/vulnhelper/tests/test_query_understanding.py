from agent_apps.vulnhelper.domain.enums import EntryMode, UserGoal
from agent_apps.vulnhelper.domain.query_understanding import parse_filter_spec, parse_query_plan


def test_parse_query_plan_extracts_product_version_and_filters() -> None:
    plan = parse_query_plan("tensorflow-cpu 2.4.1 有没有公开 POC 的高危漏洞，怎么修？")

    assert plan.entry_mode == EntryMode.PRODUCT_VERSION
    assert plan.product == "tensorflow-cpu"
    assert plan.version_spec == "2.4.1"
    assert plan.require_public_poc is True
    assert plan.require_solution is True
    assert plan.user_goal == UserGoal.FIX_VERSION
    assert "high" in plan.risk_levels


def test_parse_query_plan_does_not_treat_cve_year_as_version() -> None:
    plan = parse_query_plan("CVE-2024-53949 apache-superset 修复版本是什么？")

    assert plan.entry_mode == EntryMode.IDENTIFIER
    assert plan.vuln_id == "CVE-2024-53949"
    assert plan.product == "apache-superset"
    assert plan.version_spec is None


def test_parse_filter_spec_extracts_common_drilldown_constraints() -> None:
    spec = parse_filter_spec("只看高危并且有修复方案的 CVE-2024-53949 前1条")

    assert spec.has_solution is True
    assert spec.cve_ids == ["CVE-2024-53949"]
    assert spec.limit == 1
    assert spec.risk_levels == ["high", "critical"]
